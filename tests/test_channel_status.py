import copy
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from awkit.channel import Channel
from awkit.channel_status import observe, render
from support import child_env


class ChannelStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record_path = self.root / "records" / "task.json"
        self.record_path.parent.mkdir()
        self.ab = Channel(self.root / "ab.sqlite3")
        self.ac = Channel(self.root / "ac.sqlite3")
        self.record = dict(schema=1, session="fiction-A", relationships=[
            dict(id="ab", channel="../ab.sqlite3", local_role="reviewer", counterpart="fiction-B"),
            dict(id="ac", channel="../ac.sqlite3", local_role="main", counterpart="fiction-C", task="sample"),
        ], obligations=[])

    def save(self):
        self.record_path.write_text(json.dumps(self.record), encoding="utf-8")

    def cli(self, *args, expected=0, cwd=None):
        result = subprocess.run([sys.executable, "-m", "awkit", "channel", *args], cwd=cwd,
                                env=child_env(), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def status(self, expected=0):
        self.save()
        result = self.cli("status", "--record", str(self.record_path), "--json", expected=expected)
        return json.loads(result.stdout)

    def obligation(self, ident, relationship, message, state="pending", evidence=(), **kwargs):
        row = dict(id=ident, source=dict(relationship=relationship, message=message),
                   responsible_session="fiction-A", action="record sample disposition", state=state,
                   evidence=[dict(relationship=rel, message=msg) for rel, msg in evidence], **kwargs)
        self.record["obligations"].append(row)
        return row

    def fixture(self):
        self.ab.post("main", "reviewer", "question", "Choose a label.")
        self.ab.find("reviewer", "new")
        self.ac.post("main", "reviewer", "draft", "Return a sample.")
        self.ac.post("reviewer", "main", "re", "v1", reply_to="M-001")
        self.ac.post("reviewer", "main", "notice", "Revision v2.")
        self.ac.post("reviewer", "main", "notice", "Information only.")
        self.ac.post("reviewer", "main", "notice", "Forward v2.")
        self.ac.find("main", "new")
        self.ab.post("main", "reviewer", "question", "What is v2?")
        self.ab.post("reviewer", "main", "notice", "Explicit answer to M-002: cobalt.")
        self.ac.post("main", "reviewer", "close", "Contribution unit closed.")

    def test_two_channels_roles_cursors_notices_return_and_closed_unit(self):
        self.fixture()
        self.obligation("answer", "ab", "M-002", "done", [("ab", "R-001")])
        self.obligation("integrate", "ac", "R-002", revision="v2")
        self.obligation("forward", "ac", "R-004")
        result = self.status()
        relationships = {row["id"]: row for row in result["relationships"]}
        self.assertEqual((result["schema"], result["session"]), (1, "fiction-A"))
        self.assertEqual((relationships["ab"]["state"], relationships["ac"]["state"]), ("open", "closed"))
        unanswered = [row["source"] for row in result["protocol"] if row["observation"] == "protocol-unanswered"]
        self.assertEqual(unanswered, [dict(relationship="ab", message="M-001"), dict(relationship="ab", message="M-002")])
        returned = [row for row in result["protocol"] if row["observation"] == "returned-response"]
        self.assertEqual(returned[0]["source"], dict(relationship="ac", message="R-001"))
        self.assertEqual(returned[0]["disposition"], "disposition-unrecorded")
        self.assertEqual(result["obligations"][0]["support"], "references-resolved")
        self.assertEqual(result["obligations"][1]["revision"], "v2")
        self.assertEqual(result["diagnostics"], [])
        self.assertFalse(any(row["kind"] == "notice" for row in result["protocol"]))
        text = self.cli("status", "--record", str(self.record_path)).stdout
        for expected in ("fiction-B | local reviewer", "fiction-C | local main", "ab:M-002", "next: reply to request",
                         "disposition-unrecorded", "pending", "semantic completion is not verified"):
            self.assertIn(expected, text)
        notice_row = next(row for row in result["protocol"] if row["source"] == dict(relationship="ab", message="M-002"))
        self.assertEqual(notice_row["declarations"], ["answer"])
        self.assertEqual(notice_row["next_protocol_action"], "reconcile protocol and declaration evidence before another reply")
        self.assertIn("evidence: ab:R-001 (resolved)", text)
        self.assertIn("Protocol: unanswered incoming=2 | awaiting replies=0 | returned responses without disposition=1", text)
        self.assertIn("Declared state: pending=2 | unsupported=0 | conflicting=0 | unavailable channels=0", text)

    def test_reversed_roles_and_rebut_remain_requests(self):
        self.ab.post("main", "reviewer", "question", "Question.")
        self.ab.post("reviewer", "main", "re", "Answer.", reply_to="M-001")
        self.ab.post("main", "reviewer", "rebut", "Reconsider.", reply_to="R-001")
        self.ac.post("main", "reviewer", "question", "Other question.")
        self.record["relationships"][0].update(local_role="main", counterpart="fiction-A")
        self.record["relationships"][1].update(local_role="reviewer", counterpart="fiction-A")
        result = self.status()
        self.assertTrue(any(row["source"] == dict(relationship="ab", message="M-002")
                            and row["observation"] == "awaiting-reply" for row in result["protocol"]))
        self.assertTrue(any(row["source"] == dict(relationship="ac", message="M-001")
                            and row["observation"] == "protocol-unanswered" for row in result["protocol"]))
        self.record["relationships"][0]["local_role"] = "reviewer"
        result = self.status()
        self.assertTrue(any(row["kind"] == "rebut" and row["observation"] == "protocol-unanswered"
                            for row in result["protocol"]))

    def test_declared_disposition_does_not_suppress_protocol_or_verify_semantics(self):
        self.fixture()
        self.obligation("inspect", "ac", "R-001", "no-action", [("ac", "R-003")], reason="Superseded by v2.")
        self.obligation("unsupported-done", "ab", "M-001", "done")
        self.obligation("missing-evidence", "ab", "M-002", "done", [("ac", "R-999")])
        self.obligation("wrong-channel", "ab", "M-002", "no-action", [("ac", "R-999")])
        self.obligation("missing-source", "ac", "M-999")
        result = self.status()
        self.assertEqual(result["protocol"][-1]["disposition"], "declared")
        self.assertEqual([row["support"] for row in result["obligations"]],
                         ["references-resolved", "unsupported", "unsupported", "unsupported", "unsupported"])
        self.assertTrue(any(row["source"]["message"] == "M-001" and row["observation"] == "protocol-unanswered"
                            for row in result["protocol"]))
        # Resolved IDs establish reference existence only, including deliberately unrelated notice evidence.
        self.assertEqual(result["obligations"][0]["evidence_resolution"][0]["status"], "resolved")

    def test_conflicting_declarations_are_visible_and_exit_zero(self):
        self.fixture()
        self.obligation("first", "ab", "M-002", "done", [("ab", "R-001")])
        self.obligation("second", "ab", "M-002")
        result = self.status()
        self.assertEqual(result["obligations"][0]["conflicts"], ["second"])
        text = self.cli("status", "--record", str(self.record_path)).stdout
        self.assertIn("conflicts: second", text)
        self.assertIn("conflicting-declarations", text)
        self.assertIn("conflicting=2", text)

    def test_notice_only_pending_declaration_appears_in_summary(self):
        self.ab.post("main", "reviewer", "notice", "Forward this sample.")
        self.ac.post("reviewer", "main", "notice", "Information only.")
        self.obligation("forward", "ab", "M-001")
        result = self.status()
        self.assertEqual(result["protocol"], [])
        text = self.cli("status", "--record", str(self.record_path)).stdout
        self.assertIn("Protocol: unanswered incoming=0 | awaiting replies=0 | returned responses without disposition=0", text)
        self.assertIn("Declared state: pending=1 | unsupported=0 | conflicting=0 | unavailable channels=0", text)
        self.assertIn("Declared forward | ab:M-001", text)

    def test_omitted_evidence_normalizes_to_empty_and_unsupported_dispositions_are_visible(self):
        self.fixture()
        self.obligation("missing-proof", "ac", "R-001", "done").pop("evidence")
        self.obligation("pending", "ab", "M-001").pop("evidence")
        result = self.status()
        self.assertEqual(result["obligations"][0]["evidence"], [])
        self.assertEqual(result["obligations"][0]["support"], "unsupported")
        returned = next(row for row in result["protocol"] if row["observation"] == "returned-response")
        self.assertEqual(returned["declaration_details"][0]["support"], "unsupported")
        text = self.cli("status", "--record", str(self.record_path)).stdout
        declared = next(line for line in text.splitlines() if line.startswith("Declared missing-proof |"))
        self.assertIn("| done |", declared)
        self.assertIn("support: unsupported", declared)
        self.assertIn("evidence: none", text)

    def test_human_output_groups_outstanding_before_history_without_changing_report(self):
        self.ab.post("main", "reviewer", "question", "Settled question.")
        self.ab.post("reviewer", "main", "re", "Answer.", reply_to="M-001")
        self.ab.post("main", "reviewer", "question", "New question.")
        self.ab.post("main", "reviewer", "question", "Another settled question.")
        self.ab.post("reviewer", "main", "re", "Another answer.", reply_to="M-003")
        self.ac.post("main", "reviewer", "notice", "Sample notice.")
        self.ac.post("main", "reviewer", "question", "Waiting for a result.")
        self.obligation("settled", "ab", "M-001", "done", [("ab", "R-001")])
        self.obligation("notice-first", "ac", "M-001")
        self.obligation("question", "ab", "M-002")
        self.obligation("notice-second", "ac", "M-001")
        report = self.status()
        before = copy.deepcopy(report)
        text = render(report)
        history = text.index("Recorded history:")
        self.assertLess(text.index("ab:M-002 |"), history)
        self.assertLess(text.index("ac:M-002 |"), history)
        self.assertGreater(text.index("ab:M-001 |"), history)
        self.assertLess(text.index("ab:M-002 |"), text.index("ac:M-002 |"))
        self.assertLess(text.index("ab:M-001 |"), text.index("ab:M-003 |"))
        self.assertLess(text.index("Declared notice-first |"), text.index("Declared question |"))
        self.assertLess(text.index("Declared question |"), text.index("Declared notice-second |"))
        self.assertLess(text.index("Declared notice-second |"), history)
        self.assertGreater(text.index("Declared settled |"), history)
        waiting = next(line for line in text.splitlines() if line.startswith("ac:M-002 |"))
        self.assertIn("await linked response", waiting)
        self.assertNotIn("send", waiting)
        self.assertEqual(len(re.findall(r"^(?:ab|ac):[MR]-[0-9]+ \|", text, re.M)), len(report["protocol"]))
        for row in report["obligations"]:
            self.assertEqual(sum(line.startswith(f"Declared {row['id']} |") for line in text.splitlines()), 1)
        self.assertEqual(report, before)
        self.assertEqual(render(report), text)

    def test_human_output_keeps_unsupported_conflicting_and_unavailable_early(self):
        self.fixture()
        self.obligation("unsupported", "ac", "R-001", "done")
        self.obligation("conflicting", "ac", "R-001")
        self.record["relationships"].append(dict(id="unavailable", channel="../missing.sqlite3",
                                                 local_role="main", counterpart="fiction-D"))
        report = self.status(expected=1)
        text = render(report)
        attention = text.index("Outstanding protocol and declarations:")
        history = text.index("Recorded history:")
        self.assertLess(text.index("Diagnostic:"), attention)
        self.assertLess(text.index("unavailable: fiction-D | local main | unavailable"), attention)
        self.assertLess(text.index("Declared unsupported |"), history)
        self.assertLess(text.index("Declared conflicting |"), history)
        returned = next(line for line in text.splitlines() if line.startswith("ac:R-001 |"))
        self.assertLess(text.index(returned), history)
        self.assertIn("unsupported", returned)
        self.assertIn("channel closed", returned)
        self.assertIn("conflicts: conflicting", text)
        for row in report["protocol"]:
            self.assertIn(row["next_protocol_action"], text)

    def test_all_settled_human_output_retains_history_and_completion_limit(self):
        self.ab.post("main", "reviewer", "question", "Question.")
        self.ab.post("reviewer", "main", "re", "Answer.", reply_to="M-001")
        self.ac.post("main", "reviewer", "notice", "Information only.")
        self.ac.post("main", "reviewer", "close", "Closed.")
        self.obligation("settled", "ab", "M-001", "done", [("ab", "R-001")])
        self.obligation("info", "ac", "M-001", "no-action", [("ac", "M-001")])
        report = self.status()
        text = render(report)
        self.assertIn("No outstanding protocol or declaration is recorded.", text)
        self.assertIn("semantic completion is not verified", text)
        self.assertLess(text.index("Recorded history:"), text.index("ab:M-001 |"))
        for row in report["obligations"]:
            self.assertEqual(sum(line.startswith(f"Declared {row['id']} |") for line in text.splitlines()), 1)
            self.assertGreater(text.index(f"Declared {row['id']} |"), text.index("Recorded history:"))
        self.assertIn("fiction-C | local main | closed", text)

    def test_unavailable_only_report_does_not_imply_settled_work(self):
        report = self.status(expected=1)
        self.assertEqual(report["protocol"], [])
        self.assertEqual(report["obligations"], [])
        text = render(report)
        self.assertIn("Unavailable channel evidence leaves outstanding work unknown.", text)
        self.assertNotIn("No outstanding protocol or declaration is recorded.", text)
        self.assertTrue(all(row["state"] == "unavailable" for row in report["relationships"]))

    def test_aliases_deduplicate_rows_and_resolve_declarations(self):
        self.fixture()
        alias = dict(self.record["relationships"][0], id="alias", channel=str(self.ab.path))
        self.record["relationships"].append(alias)
        self.obligation("alias-evidence", "alias", "M-002", "done", [("alias", "R-001")])
        result = self.status()
        self.assertEqual(result["relationships"][-1]["alias_of"], "ab")
        self.assertEqual(len([row for row in result["protocol"] if row["observation"] == "protocol-unanswered"]), 2)
        self.assertEqual(result["obligations"][0]["support"], "references-resolved")
        alias["local_role"] = "main"
        self.save()
        self.assertIn("Conflicting roles", self.cli("status", "--record", str(self.record_path), expected=2).stderr)
        alias["local_role"] = "reviewer"
        alias["counterpart"] = "different"
        self.save()
        self.cli("status", "--record", str(self.record_path), expected=2)

    def test_hardlink_aliases_are_same_channel_within_invocation(self):
        self.fixture()
        link = self.root / "channel-hardlink.sqlite3"
        try:
            os.link(self.ab.path, link)
        except OSError as error:
            self.skipTest(f"Hard links unavailable on this filesystem: {error}")
        alias = dict(self.record["relationships"][0], id="hardlink", channel=str(link))
        self.record["relationships"].append(alias)
        result = self.status()
        self.assertEqual(result["relationships"][-1]["alias_of"], "ab")
        self.assertEqual(len([row for row in result["protocol"] if row["observation"] == "protocol-unanswered"]), 2)
        alias["counterpart"] = "conflicting"
        self.save()
        self.cli("status", "--record", str(self.record_path), expected=2)

    def test_missing_database_preserves_partial_rows_and_creates_nothing(self):
        self.ab.post("main", "reviewer", "question", "Question.")
        missing = self.root / "not-created" / "missing.sqlite3"
        self.record["relationships"][1]["channel"] = str(missing)
        self.obligation("unavailable", "ac", "M-001", "done", [("ac", "R-001")])
        result = self.status(expected=1)
        self.assertEqual(len(result["protocol"]), 1)
        self.assertEqual(result["relationships"][1]["state"], "unavailable")
        self.assertEqual(result["obligations"][0]["support"], "unsupported")
        self.assertFalse(missing.parent.exists())

    def test_closed_channel_retains_pending_incoming_and_outgoing_requests(self):
        self.ab.post("main", "reviewer", "question", "Incoming question.")
        self.ab.post("reviewer", "main", "question", "Outgoing question.")
        self.ab.post("main", "reviewer", "close", "Closed with unresolved requests.")
        self.ac.post("main", "reviewer", "notice", "Other channel.")
        self.ab.find("reviewer", "new")
        result = self.status()
        self.assertEqual([row["observation"] for row in result["protocol"]],
                         ["protocol-unanswered", "awaiting-reply"])
        self.assertTrue(all(row["channel_state"] == "closed" for row in result["protocol"]))

    def test_unreadable_channel_keeps_other_channel_rows(self):
        self.ab.post("main", "reviewer", "question", "Question.")
        self.ac.path.write_bytes(b"not a SQLite database")
        before = self.ac.path.read_bytes()
        result = self.status(expected=1)
        self.assertEqual(result["diagnostics"][0]["kind"], "channel-unavailable")
        self.assertEqual(result["protocol"][0]["source"], dict(relationship="ab", message="M-001"))
        self.assertEqual(self.ac.path.read_bytes(), before)

    def test_unsupported_schema_and_shape_are_not_migrated(self):
        self.ab.post("main", "reviewer", "question", "Question.")
        for version, schema in ((0, ""), (7, ""), (1, "CREATE TABLE messages (id TEXT)"),
                                (1, "CREATE VIEW messages AS SELECT 1 AS seq")):
            with self.subTest(version=version, schema=schema):
                path = self.root / f"invalid-{version}-{len(schema)}.sqlite3"
                with closing(sqlite3.connect(path)) as conn:
                    conn.execute(f"PRAGMA user_version={version}")
                    if schema:
                        conn.execute(schema)
                before = path.read_bytes()
                self.record["relationships"][1]["channel"] = str(path)
                result = self.status(expected=1)
                self.assertEqual(len(result["protocol"]), 1)
                self.assertEqual(path.read_bytes(), before)

    def test_repeated_calls_preserve_database_bytes_messages_and_cursors(self):
        self.fixture()
        self.save()
        before = {path: path.read_bytes() for path in (self.ab.path, self.ac.path)}
        exports = [channel.export() for channel in (self.ab, self.ac)]
        def cursors(channel):
            with closing(sqlite3.connect(channel.path)) as conn:
                return conn.execute("SELECT * FROM cursors ORDER BY role").fetchall()
        positions = [cursors(channel) for channel in (self.ab, self.ac)]
        first = self.status()
        self.assertEqual(first, self.status())
        self.cli("status", "--record", str(self.record_path))
        self.assertEqual([channel.export() for channel in (self.ab, self.ac)], exports)
        self.assertEqual([cursors(channel) for channel in (self.ab, self.ac)], positions)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        with patch.object(Channel, "_prepare", side_effect=AssertionError("must not prepare")):
            self.assertEqual(observe(self.record_path)[1], 0)

    def test_record_paths_are_anchored_before_resolve(self):
        self.fixture()
        self.save()
        result = self.cli("status", "--record", "records/task.json", "--json", cwd=self.root)
        report = json.loads(result.stdout)
        self.assertEqual(report["relationships"][0]["channel"], str(self.ab.path.resolve()))

    def test_invalid_records_and_explicit_db_exit_two(self):
        self.fixture()
        valid = copy.deepcopy(self.record)
        invalid = [None, {}, dict(valid, schema=2), dict(valid, schema=True), dict(valid, session=""),
                   dict(valid, relationships={}), dict(valid, obligations={}),
                   dict(valid, relationships=valid["relationships"] * 2)]
        for field, value in (("local_role", "owner"), ("counterpart", ""), ("channel", 12)):
            record = copy.deepcopy(valid)
            record["relationships"][0][field] = value
            invalid.append(record)
        self.obligation("sample", "ab", "M-001")
        obligation_record = copy.deepcopy(self.record)
        invalid.append(dict(obligation_record, obligations=obligation_record["obligations"] * 2))
        for field, value in (("source", {"relationship": "unknown", "message": "M-001"}),
                             ("source", {"relationship": "ab", "message": "../M-001"}),
                             ("source", None), ("evidence", "ab:M-001"), ("state", "finished"),
                             ("responsible_session", ""), ("action", "")):
            record = copy.deepcopy(obligation_record)
            record["obligations"][0][field] = value
            invalid.append(record)
        for record in invalid:
            with self.subTest(record=record):
                self.record_path.write_text(json.dumps(record), encoding="utf-8")
                self.cli("status", "--record", str(self.record_path), expected=2)
        self.record_path.write_text("{invalid json", encoding="utf-8")
        self.cli("status", "--record", str(self.record_path), expected=2)
        self.record = valid
        self.save()
        absent = self.root / "explicit-db.sqlite3"
        self.cli("--db", str(absent), "status", "--record", str(self.record_path), expected=2)
        self.cli("--db", ".awkit/channel.sqlite3", "status", "--record", str(self.record_path), expected=2)
        self.assertFalse(absent.exists())
        self.cli("status", expected=2)

    def test_existing_commands_keep_default_database(self):
        self.cli("post", "main", "reviewer", "notice", "--body", "sample", cwd=self.root)
        self.assertTrue((self.root / ".awkit" / "channel.sqlite3").is_file())


if __name__ == "__main__":
    unittest.main()
