"""Durable admission and compatibility; no live provider is called."""

import concurrent.futures
import hashlib
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from awkit.channel import Channel
from awkit.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = SessionStore.create(self.root, name="Research", project=self.root,
                                         responsibility="Compare invented facts", generation="generation-a",
                                         permissions={"requested": "read-only"})
        self.store.update(native_id="native-a", state="idle")

    def test_cancel_and_dispatch_reservation_serialize_on_the_same_database(self):
        request = self.store.post("cancel-race", "A single contested assignment")
        barrier = threading.Barrier(2)

        def cancel():
            alias = SessionStore(self.store.path)
            barrier.wait()
            return alias.cancel(request["id"])

        def claim():
            alias = SessionStore(self.store.path)
            barrier.wait()
            return alias.claim("generation-a")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            cancelled, claimed = pool.submit(cancel), pool.submit(claim)
            disposition, attempt = cancelled.result(), claimed.result()
        view = self.store.snapshot()
        if disposition["disposition"] == "before-dispatch":
            self.assertIsNone(attempt)
            self.assertEqual(view["attempts"], [])
        else:
            self.assertEqual(attempt["request"]["id"], request["id"])
            self.assertEqual(len(view["attempts"]), 1)
        self.assertEqual(len(view["cancellations"]), 1)
        self.assertEqual(view["messages"], [request])

    def test_duplicate_client_submission_is_one_authoritative_message(self):
        def post(_):
            return SessionStore(self.store.path).post("same-key", "Preserve this fact.")["id"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(post, range(8)))
        self.assertEqual(set(ids), {"M-001"})
        self.assertEqual(len(self.store.snapshot()["messages"]), 1)
        with self.assertRaisesRegex(ValueError, "different message"):
            self.store.post("same-key", "A different assignment")

    def test_aliases_share_identity_and_admission(self):
        alias = self.root / "alias.sqlite3"
        try:
            os.link(self.store.path, alias)
        except OSError as exc:
            self.skipTest(str(exc))
        other = SessionStore(alias)
        self.assertEqual(self.store.metadata()["id"], other.metadata()["id"])
        self.store.post("work", "One request")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda store: store.claim("generation-a"), [self.store, other]))
        self.assertEqual(sum(claim is not None for claim in claims), 1)

    def test_legacy_post_is_dispatchable_but_notice_does_not_start_work(self):
        channel = Channel(self.store.path)
        channel.post("main", "reviewer", "notice", "No response required.")
        self.assertIsNone(self.store.claim("generation-a"))
        request = channel.post("main", "reviewer", "question", "Answer this.")
        claim = self.store.claim("generation-a")
        self.assertEqual(claim["request"]["id"], request)
        self.assertEqual(self.store.snapshot()["unanswered"], [request])

    def test_uncertain_admission_survives_reopening_and_blocks_further_work(self):
        self.store.post("one", "First")
        self.store.post("two", "Second")
        claim = self.store.claim("generation-a")
        self.store.uncertain("generation-a", "interrupted after possible write")
        reopened = SessionStore(self.store.path)
        self.assertIsNone(reopened.claim("generation-a"))
        self.assertIsNone(reopened.claim("generation-b"))
        reopened.update(state="idle")  # A stale observation cannot bypass the durable attempt.
        self.assertIsNone(reopened.claim("generation-a"))
        self.assertEqual(reopened.snapshot()["attempts"][0]["id"], claim["id"])

    def test_turn_bound_after_connection_loss_stays_uncertain(self):
        # A provider can answer turn/start and exit before the response is handled.
        self.store.post("one", "First")
        self.store.claim("generation-a")
        self.store.uncertain("generation-a", "Provider connection lost")
        self.assertTrue(self.store.bind_turn("generation-a", "turn-1"))
        self.assertTrue(self.store.bind_turn("generation-a", "turn-1", executing=True))
        attempt = self.store.snapshot()["attempts"][0]
        self.assertEqual((attempt["state"], attempt["turn_id"]), ("uncertain", "turn-1"))
        self.assertEqual(self.store.metadata()["state"], "unknown")
        self.assertFalse(self.store.bind_turn("generation-a", "other-turn"))

    def test_native_completion_publishes_one_linked_reply_and_preserves_cursors(self):
        request = self.store.post("one", "First")["id"]
        self.store.channel.find("reviewer", "new")
        before = self._cursors()
        self.store.claim("generation-a")
        self.assertFalse(self.store.bind_turn("wrong-generation", "turn-1"))
        self.assertTrue(self.store.bind_turn("generation-a", "turn-1", executing=True))
        self.assertFalse(self.store.bind_turn("generation-a", "wrong-turn"))
        self.assertTrue(self.store.finish("generation-a", "turn-1", "completed", "Actual native reply"))
        self.assertFalse(self.store.finish("generation-a", "turn-1", "completed", "Duplicate native reply"))
        snapshot = self.store.snapshot()
        self.assertEqual(len(snapshot["messages"]), 2)
        self.assertEqual(snapshot["messages"][1]["reply_to"], request)
        self.assertEqual(snapshot["attempts"][0]["outcome"], "completed")
        self.assertNotIn("task_success", snapshot["attempts"][0])
        self.assertEqual(self._cursors(), before)
        self.assertEqual(self.store.channel.find("main", "request")[0], 1)

    def test_pending_decisions_cannot_be_reanswered_or_downgrade_resolution(self):
        ident = self.store.add_decision("generation-a", 7, "item/fileChange/requestApproval",
                                        {"threadId": "native-a", "turnId": "turn-1"}, ["accept", "decline"])
        with self.assertRaises(ValueError):
            self.store.answer_intent("generation-b", ident, {"decision": "accept"})
        self.store.answer_intent("generation-a", ident, {"decision": "decline"})
        with self.assertRaises(ValueError):
            self.store.answer_intent("generation-a", ident, {"decision": "accept"})
        self.store.decision_state(ident, "resolved")
        self.store.decision_state(ident, "sent")
        self.assertEqual(self.store.snapshot()["decisions"][0]["state"], "resolved")

    def test_existing_channels_remain_schema_one_and_browsing_does_not_migrate(self):
        path = self.root / "ordinary.sqlite3"
        channel = Channel(path)
        channel.post("main", "reviewer", "question", "Existing request")
        before = hashlib.sha256(path.read_bytes()).digest()
        with self.assertRaisesRegex(ValueError, "not a managed"):
            SessionStore(path)
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before)
        with closing(sqlite3.connect(self.store.path)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(channel.find("reviewer", "request")[1][0]["body"], "Existing request")
        empty = self.root / "empty.sqlite3"
        empty.touch()
        with self.assertRaises(ValueError):
            SessionStore(empty)
        self.assertEqual(empty.stat().st_size, 0)

    def _cursors(self):
        with closing(sqlite3.connect(self.store.path)) as conn:
            return conn.execute("SELECT * FROM cursors ORDER BY role").fetchall()
