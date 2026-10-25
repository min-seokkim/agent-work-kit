"""Recipient, restart and unavailable-provider boundaries without live accounts."""

import sys
import tempfile
import time
import unittest
from pathlib import Path

from awkit.channel import Channel
from awkit.sessions import SessionController


class SessionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.command = [sys.executable, str(Path(__file__).with_name("session_provider_fixture.py"))]
        self.controller = SessionController(self.project, self.command)
        self.addCleanup(self.controller.close)

    def test_client_key_cannot_be_rebound_to_another_recipient(self):
        first = self.controller.create(name="Research", responsibility="Invented work")["session"]
        second = self.controller.create(name="Builder", responsibility="Other invented work")["session"]
        self.assertNotEqual(first["native_id"], second["native_id"])
        self.controller.send(first["id"], key="one-client-key", body="A bounded request")
        with self.assertRaisesRegex(ValueError, "different recipient"):
            self.controller.send(second["id"], key="one-client-key", body="A bounded request")
        self.assertEqual(self.controller._store(second["id"]).snapshot()["messages"], [])

    def test_existing_channel_post_starts_idle_managed_session_without_extra_wake(self):
        result = self.controller.create(name="Research", responsibility="Invented work")
        path = result["channel"]
        request_id = Channel(path).post("main", "reviewer", "question", "Direct existing channel request")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            view = self.controller.status()["sessions"][0]
            if len(view["messages"]) == 2:
                self.assertEqual(view["messages"][1]["reply_to"], request_id)
                self.assertIn("Direct existing channel request", view["messages"][1]["body"])
                return
            time.sleep(0.025)
        self.fail(str(self.controller.status()))

    def test_restart_reconnects_same_identity_without_dispatching_history(self):
        first = self.controller.create(name="Research", responsibility="Invented work")["session"]
        self.controller.close()
        reopened = SessionController(self.project, self.command)
        self.addCleanup(reopened.close)
        view = reopened.status()["sessions"][0]
        self.assertEqual(view["session"]["native_id"], first["native_id"])
        self.assertEqual(view["session"]["state"], "idle")  # Last observation, not a current runtime claim.
        self.assertEqual(view["execution_state"], "unknown")
        self.assertFalse(view["connected"])
        self.assertIsNone(reopened.provider)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            view = reopened.status()["sessions"][0]
            if view["can_send"]:
                break
            time.sleep(0.025)
        self.assertTrue(view["can_send"], view)
        self.assertEqual(view["session"]["native_id"], first["native_id"])
        self.assertEqual(view["messages"], [])
        self.assertEqual(view["attempts"], [])

    def test_missing_provider_does_not_prevent_reading_registered_history(self):
        self.controller.close()
        controller = SessionController(self.project, [str(self.project / "missing-codex")])
        self.addCleanup(controller.close)
        path = self.project / "history.sqlite3"
        Channel(path).post("main", "reviewer", "notice", "Existing complete history")
        controller.register_history(channel=path, main_name="Planning", reviewer_name="Research")
        state = controller.status()
        self.assertFalse(state["capabilities"]["codex_executable_available"])
        self.assertEqual(state["sessions"][0]["messages"][0]["body"], "Existing complete history")
        self.assertIsNone(controller.provider)
