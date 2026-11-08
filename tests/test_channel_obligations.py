"""Channel closure, withdrawal and independent readers on real SQLite files."""

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from awkit.channel import Channel
from awkit.channel_status import _read_channel, observe
from support import child_env


class ChannelObligationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "channel.sqlite3"
        self.channel = Channel(self.path)

    def cli(self, *args, expected=0, path=None):
        result = subprocess.run(
            [sys.executable, "-m", "awkit", "channel", "--db", str(path or self.path), *args],
            env=child_env(), capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def post(self, sender, kind, target=None, expected=0):
        return self.cli("post", sender, "reviewer" if sender == "main" else "main", kind,
                        "--body", "decision-needed: sample" if kind == "re" else "sample notice",
                        *(["--reply-to", target] if target else []), expected=expected)

    def wait(self, role, mode, *args, expected=0, path=None):
        return self.cli("wait", role, mode, *args, "--max", "0", expected=expected, path=path)

    def test_withdraw_replace_and_acknowledge(self):
        self.post("main", "review")
        self.post("reviewer", "re", "M-001")
        self.post("main", "re", "R-001")
        self.post("reviewer", "withdraw", "R-001")
        self.post("main", "re", "R-001")
        self.assertIn("M-001", self.wait("reviewer", "request").stdout)
        self.wait("main", "reply", "M-001", expected=1)
        self.wait("reviewer", "reply", "R-001", expected=1)
        self.assertIn("R-002", self.wait("main", "new", "--consumer", "main-session").stdout)
        error = self.post("main", "close", expected=2).stderr
        self.assertIn("unanswered-request: M-001", error)
        self.assertIn("unresolved-withdrawal: R-002", error)
        self.assertNotIn("unacknowledged-verdict:", error)
        self.assertEqual(self.post("reviewer", "re", "M-001").stdout.strip(), "R-003")
        error = self.post("main", "close", expected=2).stderr
        self.assertIn("unacknowledged-verdict: R-003", error)
        self.assertNotIn("unresolved-withdrawal:", error)
        self.post("main", "re", "R-003")
        self.post("main", "close")
        self.wait("reviewer", "request", expected=3)
        self.assertIn("close", self.wait("reviewer", "peek").stdout)

    def test_rebuttal_and_closed_channel(self):
        self.post("main", "review")
        self.post("reviewer", "re", "M-001")
        self.post("main", "rebut", "R-001")
        error = self.post("main", "close", expected=2).stderr
        self.assertIn("unanswered-rebuttal: M-002", error)
        self.assertIn("unacknowledged-verdict: R-001", error)
        self.post("reviewer", "re", "M-002")
        self.post("main", "re", "R-001")
        self.post("main", "close")
        self.assertIn("closed", self.post("reviewer", "notice", expected=2).stderr)

    def test_consumers_peek_and_new_file(self):
        self.post("reviewer", "notice")
        legacy = self.wait("main", "new")
        self.assertIn("shared role cursor", legacy.stderr)
        self.wait("main", "new", expected=1)
        self.assertIn("sample notice", self.wait("main", "peek").stdout)
        self.assertIn("sample notice", self.wait("main", "new", "--consumer", "main-session").stdout)
        before = self.path.read_bytes()
        self.wait("main", "peek")
        self.wait("reviewer", "request", expected=1)
        self.wait("main", "reply", "M-999", expected=1)
        self.assertEqual(self.path.read_bytes(), before)
        self.wait("main", "new", "--consumer", "main-session", expected=1)
        self.wait("main", "new", "--consumer", "observer")
        other = self.root / "other.sqlite3"
        Channel(other).post("reviewer", "main", "notice", "new file")
        self.wait("main", "new", "--consumer", "main-session", path=other)
        self.wait("main", "peek", "--consumer", "observer", expected=2)
        self.wait("main", "new", "--consumer", " ", expected=2)

    def test_all_blocker_ids_and_request_kinds(self):
        for kind in ("review", "final", "scout", "test", "draft", "question"):
            self.channel.post("main", "reviewer", kind, "request")
        with self.assertRaisesRegex(ValueError, "unanswered-request: M-001, M-002, M-003, M-004, M-005, M-006"):
            self.channel.post("main", "reviewer", "close", "done")
        for number in range(1, 7):
            self.channel.post("reviewer", "main", "re", "No findings", reply_to=f"M-{number:03d}")
        with self.assertRaisesRegex(ValueError, "unacknowledged-verdict: R-001, R-002"):
            self.channel.post("main", "reviewer", "close", "done")
        for number in (1, 2):
            self.channel.post("main", "reviewer", "re", "Applied", reply_to=f"R-{number:03d}")
        self.channel.post("main", "reviewer", "close", "done")

    def test_withdrawal_targets_and_later_replacement(self):
        self.post("main", "review")
        self.post("reviewer", "re", "M-001")
        self.post("reviewer", "re", "M-001")
        self.post("main", "re", "R-002")
        self.post("reviewer", "notice")
        for sender, target in (("main", "R-001"), ("reviewer", "M-001"),
                               ("reviewer", "R-003"), ("reviewer", "R-999")):
            self.post(sender, "withdraw", target, expected=2)
        self.post("reviewer", "re", "R-001", expected=2)
        self.post("reviewer", "withdraw", "R-001")
        # A response that predates withdrawal cannot resolve it.
        self.assertIn("unresolved-withdrawal: R-004", self.post("main", "close", expected=2).stderr)
        self.post("reviewer", "re", "M-001")
        self.post("reviewer", "withdraw", "R-005")
        error = self.post("main", "close", expected=2).stderr
        self.assertIn("unresolved-withdrawal: R-004, R-006", error)

    def test_schema_one_migration_preserves_actual_file_and_shared_position(self):
        old_schema = """
            CREATE TABLE messages (
                seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
                sender TEXT NOT NULL, receiver TEXT NOT NULL, kind TEXT NOT NULL,
                reply_to TEXT, snap TEXT, at TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE cursors (role TEXT PRIMARY KEY, seq INTEGER NOT NULL);
        """
        with closing(sqlite3.connect(self.path)) as conn:
            conn.executescript(old_schema)
            conn.execute("PRAGMA user_version=1")
            conn.execute("INSERT INTO messages VALUES (1,'R-001','reviewer','main','notice',NULL,NULL,'sample','first')")
            conn.execute("INSERT INTO messages VALUES (2,'M-001','main','reviewer','notice',NULL,NULL,'sample','second')")
            conn.executemany("INSERT INTO cursors VALUES (?,?)", [("main", 1), ("reviewer", 2)])
            conn.commit()
        before = self.path.read_bytes()
        rows, cursors = _read_channel(self.path, include_cursors=True)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(rows), 2)
        record = self.root / "legacy-record.json"
        record.write_text(json.dumps(dict(schema=1, session="reader", relationships=[dict(
            id="legacy", channel=str(self.path), local_role="main", counterpart="reviewer")])), encoding="utf-8")
        report, code = observe(record)
        self.assertEqual(code, 0)
        self.assertEqual(report["relationships"][0]["cursors"], cursors)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(cursors[0], dict(role="main", consumer="", seq=1))
        self.wait("main", "new", expected=1)
        self.wait("reviewer", "new", expected=1)
        self.wait("main", "new", "--consumer", "resumed")
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT role,seq FROM cursors WHERE consumer='' ORDER BY role").fetchall(),
                             [("main", 1), ("reviewer", 2)])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 2)

    def test_status_matches_closure_and_withdrawn_evidence(self):
        self.post("main", "final")
        self.post("reviewer", "re", "M-001")
        record = self.root / "task.json"
        value = dict(schema=1, session="sample", relationships=[dict(
            id="unit", channel=str(self.path), local_role="main", counterpart="review-session")],
            obligations=[dict(id="applied", source=dict(relationship="unit", message="R-001"),
                              responsible_session="sample", action="apply", state="done",
                              evidence=[dict(relationship="unit", message="R-001")])])
        record.write_text(json.dumps(value), encoding="utf-8")
        report, code = observe(record)
        self.assertEqual(code, 0)
        self.assertEqual(report["protocol"][-1]["disposition"], "disposition-unrecorded")
        value["relationships"][0]["local_role"] = "reviewer"
        record.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(observe(record)[0]["protocol"][-1]["disposition"], "disposition-unrecorded")
        value["relationships"][0]["local_role"] = "main"
        record.write_text(json.dumps(value), encoding="utf-8")
        self.post("main", "re", "R-001")
        self.assertEqual(observe(record)[0]["protocol"][-1]["disposition"], "acknowledged")
        self.post("reviewer", "withdraw", "R-001")
        self.wait("main", "new", "--consumer", "observer")
        before = self.path.read_bytes()
        report, code = observe(record)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(report["obligations"][0]["source_status"], "withdrawn")
        relation = report["relationships"][0]
        self.assertEqual(relation["close_blockers"]["unresolved-withdrawal"], ["R-002"])
        self.assertEqual(relation["close_blockers"]["unacknowledged-verdict"], [])
        self.assertEqual(relation["cursors"], [dict(role="main", consumer="observer", seq=4)])

    def test_concurrent_post_and_close_share_one_transaction(self):
        # Each ordering pauses the lock holder and starts a competing process.
        # Pausing inside protocol_state also proves close holds its write lock during inspection.
        for first in ("post", "close"):
            with self.subTest(first=first):
                path = self.root / f"race-{first}.sqlite3"
                Channel(path).export()
                setup = "import sys; from pathlib import Path; import awkit.channel as m; c=m.Channel(Path(sys.argv[1]))\n"
                gate = "print('ready', flush=True); sys.stdin.readline()\n"
                if first == "post":
                    leader_code = setup + "with c.transaction() as conn:\n c._post(conn,'main','reviewer','review','request')\n " + gate
                    follower_action = "c.post('main','reviewer','close','done')"
                    expected = "unanswered-request: M-001"
                else:
                    leader_code = setup + ("original=m.protocol_state\ndef paused(rows):\n " + gate
                                           + " return original(rows)\nm.protocol_state=paused\n"
                                           + "c.post('main','reviewer','close','done')\n")
                    follower_action = "c.post('main','reviewer','review','request')"
                    expected = "closed"
                follower_code = setup + "print('ready', flush=True)\n" + follower_action
                processes = []
                try:
                    for code in (leader_code, follower_code):
                        process = subprocess.Popen([sys.executable, "-c", code, str(path)], env=child_env(),
                                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                   stderr=subprocess.PIPE, text=True)
                        processes.append(process)
                        self.assertEqual(process.stdout.readline().strip(), "ready")
                    out, err = processes[0].communicate("release\n", timeout=15)
                    self.assertEqual(processes[0].returncode, 0, out + err)
                    out, err = processes[1].communicate(timeout=15)
                    self.assertNotEqual(processes[1].returncode, 0)
                    self.assertIn(expected, err)
                    self.assertEqual(len(Channel(path).export()), 1)
                finally:
                    for process in processes:
                        if process.poll() is None:
                            process.kill()
                        process.communicate()


if __name__ == "__main__":
    unittest.main()
