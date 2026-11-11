import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from awkit.channel import Channel
from awkit.channel_delivery import PAGE_SIZE, SEGMENT_CHARS, Delivery
from support import child_env


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "channel.sqlite3"
        self.local = Channel(self.path, project=self.path.parent)
        self.local.export()
        self.main = Delivery(self.path, "main", "local-test")
        self.remote = Delivery(self.path, "reviewer", "cloud-test")

    def test_lost_send_response_retry_conflict_and_closure(self):
        first = self.main.post(self.main.instance, "attempt-1", "notice", "한국어 응답")
        self.local.post("main", "reviewer", "close", "finished")
        resumed = Delivery(self.path, "main", "local-test")
        retried = resumed.post(resumed.instance, "attempt-1", "notice", "한국어 응답")
        self.assertEqual(first["message_id"], retried["message_id"])
        self.assertTrue(retried["duplicate"])
        self.assertEqual(len(self.local.export()), 2)
        with self.assertRaisesRegex(ValueError, "another payload"):
            resumed.post(resumed.instance, "attempt-1", "notice", "changed")
        with self.assertRaisesRegex(ValueError, "closed"):
            resumed.post(resumed.instance, "attempt-2", "notice", "late")

    def test_lost_read_ack_response_and_restart(self):
        self.local.post("main", "reviewer", "notice", "first")
        first = self.remote.read()
        resumed = Delivery(self.path, "reviewer", "cloud-test")
        self.assertEqual(first, resumed.read())
        self.local.post("main", "reviewer", "notice", "second")
        self.assertEqual(first, resumed.read())
        resumed.ack(first["receipt"])
        second = resumed.read()
        self.assertEqual(second["segment"]["message"]["body"], "second")
        self.assertTrue(resumed.ack(first["receipt"])["duplicate"])
        self.assertEqual(second, resumed.read())
        resumed.ack(second["receipt"])
        with self.assertRaisesRegex(ValueError, "stale"):
            resumed.ack(first["receipt"])
        self.assertIsNone(resumed.read()["segment"])

    def test_oversized_legacy_message_all_segments_and_embedded_nul(self):
        body = "한글\x00" * (SEGMENT_CHARS * 3)
        message_id = self.local.post("main", "reviewer", "notice", body)
        parts = []
        while True:
            delivery = Delivery(self.path, "reviewer", "cloud-test")
            result = delivery.read()
            segment = result["segment"]
            self.assertEqual(segment["message"]["id"], message_id)
            self.assertEqual(segment["total_chars"], len(body))
            self.assertLessEqual(len(segment["message"]["body"]), SEGMENT_CHARS)
            parts.append(segment["message"]["body"])
            self.assertEqual(result, delivery.read())
            delivery.ack(result["receipt"])
            if segment["complete"]:
                break
        self.assertEqual("".join(parts), body)
        self.assertIsNone(delivery.read()["segment"])
        self.assertEqual(delivery.message(message_id, SEGMENT_CHARS)["segment"]["offset"], SEGMENT_CHARS)

    def test_acknowledged_unanswered_request_can_be_recovered(self):
        message_id = self.local.post("main", "reviewer", "review", "review this", snap="a" * 40)
        self.remote.ack(self.remote.read()["receipt"])
        self.assertIsNone(self.remote.read()["segment"])
        recovered = Delivery(self.path, "reviewer", "cloud-test").requests()
        self.assertEqual([r["id"] for r in recovered["requests"]], [message_id])
        self.assertNotIn("body", recovered["requests"][0])
        self.assertEqual(self.remote.message(message_id)["segment"]["message"]["body"], "review this")
        reply = self.remote.post(self.remote.instance, "answer", "re", "reviewed", reply_to=message_id)
        self.assertEqual(self.remote.requests()["requests"], [])
        self.local.post("main", "reviewer", "rebut", "check again", reply_to=reply["message_id"])
        self.assertEqual(self.remote.requests()["requests"][0]["kind"], "rebut")

    def test_recovery_pages_and_message_access_are_bound(self):
        for n in range(PAGE_SIZE + 2):
            self.local.post("main", "reviewer", "question", str(n))
        page = self.remote.requests()
        self.assertEqual(len(page["requests"]), PAGE_SIZE)
        self.assertEqual(len(self.remote.requests(page["next_after"])["requests"]), 2)
        with self.assertRaisesRegex(ValueError, "Incoming message"):
            self.main.message("M-001")
        other_path = self.path.with_name("other.sqlite3")
        Channel(other_path, project=other_path.parent).export()
        other = Delivery(other_path, "reviewer", "cloud-test")
        with self.assertRaisesRegex(ValueError, "stale"):
            other.ack(self.remote.read()["receipt"])
        self.assertNotEqual(other.instance, self.remote.instance)

    def test_missing_replaced_and_invalid_channel_never_recreated(self):
        old_id = self.remote.instance
        self.path.rename(self.path.with_name("archived.sqlite3"))
        with self.assertRaises(sqlite3.OperationalError):
            self.remote.read()
        self.assertFalse(self.path.exists())
        with self.assertRaises(FileNotFoundError):
            Delivery(self.path, "reviewer", "cloud-test")
        Channel(self.path, project=self.path.parent).export()
        with self.assertRaisesRegex(ValueError, "instance"):
            self.remote.read()
        rebound = Delivery(self.path, "reviewer", "cloud-test")
        self.assertNotEqual(old_id, rebound.instance)
        with self.assertRaisesRegex(ValueError, "instance"):
            self.remote.read()
        with self.assertRaisesRegex(ValueError, "absolute"):
            Delivery(Path("relative.sqlite3"), "main", "test")
        invalid = self.path.with_name("unrelated.sqlite3")
        sqlite3.connect(invalid).close()
        with self.assertRaisesRegex(ValueError, "schema-2"):
            Delivery(invalid, "main", "test")
        with closing(sqlite3.connect(invalid)) as conn:
            self.assertEqual(conn.execute("SELECT name FROM sqlite_master").fetchall(), [])

    def test_concurrent_retries_and_consumers(self):
        def send(_):
            return Delivery(self.path, "main", "sender").post(self.main.instance, "same", "notice", "once")["message_id"]
        with ThreadPoolExecutor(max_workers=6) as pool:
            ids = list(pool.map(send, range(12)))
        self.assertEqual(set(ids), {"M-001"})
        self.assertEqual(len(self.local.export()), 1)
        def receive(_):
            return Delivery(self.path, "reviewer", "shared").read()
        with ThreadPoolExecutor(max_workers=6) as pool:
            reads = list(pool.map(receive, range(12)))
        self.assertTrue(all(r == reads[0] for r in reads))
        first = self.remote.read()
        other = Delivery(self.path, "reviewer", "independent")
        second = other.read()
        with self.assertRaisesRegex(ValueError, "stale"):
            other.ack(first["receipt"])
        self.remote.ack(first["receipt"])
        self.assertEqual(other.read(), second)

    def test_legacy_cli_positions_and_schema_remain_compatible(self):
        self.main.post(self.main.instance, "compat", "notice", "unchanged CLI")
        remote = self.remote.read()
        command = [sys.executable, "-m", "awkit", "channel", "--db", str(self.path)]
        result = subprocess.run(command + ["wait", "reviewer", "new", "--consumer", "cloud-test", "--max", "0", "--json"],
                                capture_output=True, text=True, encoding="utf-8", env=child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]["body"], "unchanged CLI")
        self.assertEqual(self.remote.read(), remote)
        result = subprocess.run(command + ["post", "reviewer", "main", "notice", "--body", "legacy write"],
                                capture_output=True, text=True, env=child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)

    def test_invalid_send_rolls_back_key_and_close_is_delivered(self):
        with self.assertRaises(ValueError):
            self.main.post(self.main.instance, "retry", "re", "missing parent", reply_to="R-999")
        self.main.post(self.main.instance, "retry", "notice", "valid")
        with self.assertRaisesRegex(ValueError, "65536"):
            self.main.post(self.main.instance, "large", "notice", "한" * 30000)
        with self.assertRaises(ValueError):
            self.remote.post(self.remote.instance, "close", "close", "not allowed")
        self.local.post("main", "reviewer", "close", "finished")
        first = self.remote.read()
        self.assertTrue(first["closed"])
        self.remote.ack(first["receipt"])
        close = self.remote.read()
        self.assertEqual(close["segment"]["message"]["kind"], "close")
        self.remote.ack(close["receipt"])
        self.assertTrue(self.remote.read()["closed"])

    def test_retry_cannot_cross_rebound_channel(self):
        self.local.post("main", "reviewer", "review", "unit A", snap="a" * 40)
        old_id = self.remote.instance
        self.remote.post(old_id, "verdict", "re", "verdict for A", reply_to="M-001")
        self.path.rename(self.path.with_name("unit-a.sqlite3"))
        unit_b = Channel(self.path, project=self.path.parent)
        unit_b.post("main", "reviewer", "review", "unit B", snap="b" * 40)
        rebound = Delivery(self.path, "reviewer", "cloud-test")
        with self.assertRaisesRegex(ValueError, "Caller channel_id"):
            rebound.post(old_id, "verdict", "re", "verdict for A", reply_to="M-001")
        self.assertEqual(len(unit_b.export()), 1)
        self.assertEqual(len(rebound.requests()["requests"]), 1)

    def test_concurrent_process_retries_keep_one_message(self):
        code = ("from awkit.channel_delivery import Delivery; import sys; "
                "d=Delivery(sys.argv[1],'main','process'); "
                "print(d.post(sys.argv[2],'retry','notice','once')['message_id'])")
        processes = [subprocess.Popen([sys.executable, "-c", code, str(self.path), self.main.instance],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=child_env()) for _ in range(6)]
        try:
            for process in processes:
                out, err = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, err)
                self.assertEqual(out.strip(), b"M-001")
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        self.assertEqual(len(self.local.export()), 1)
