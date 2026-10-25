"""Provider availability and independently owned connection generations."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from awkit.sessions import SessionController


class FakeClaude:
    def __init__(self, store, **kwargs):
        self.store = store
        self.generation = store.metadata()["generation"]
        self.alive = True
        store.update(state="idle", native_id=store.metadata().get("native_id") or store.metadata()["requested_native_id"])

    def close(self):
        self.alive = False


class ClaudeControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.controller = SessionController(Path(self.tmp.name), [sys.executable], claude_factory=FakeClaude)
        self.addCleanup(self.controller.close)

    def create(self, name="Claude worker", **kwargs):
        with patch("awkit.sessions.availability", return_value={"available": True}):
            return self.controller.create(name=name, provider="claude", responsibility="Invented work", **kwargs)

    def test_missing_extra_does_not_create_an_uncertain_native_conversation(self):
        with patch("awkit.sessions.availability", return_value={"available": False, "reason": "optional dependency missing"}):
            with self.assertRaisesRegex(ValueError, "optional dependency missing"):
                self.controller.create(name="Unavailable", provider="claude", responsibility="Invented work")
        self.assertEqual(self.controller.status()["sessions"], [])
        self.assertIsNone(self.controller.provider)

    def test_incompatible_creation_policies_cannot_cross_providers(self):
        with self.assertRaisesRegex(ValueError, "sandbox choices cannot"):
            self.create(sandbox="workspace-write")
        with self.assertRaisesRegex(ValueError, "cannot be transferred to Codex"):
            self.controller.create(name="Codex", responsibility="Invented", permission_mode="default")
        self.assertEqual(self.controller.status()["sessions"], [])

    def test_codex_disconnect_does_not_mark_live_claude_unknown(self):
        view = self.create()
        self.controller._message(dict(method="awkit/connectionError", params={"reason": "offline Codex failure"}))
        current = self.controller._store(view["session"]["id"]).metadata()
        self.assertEqual(current["state"], "idle")
        self.assertTrue(self.controller.status()["sessions"][0]["connected"])

    def test_stopped_controller_cannot_start_a_late_claude_reconnect(self):
        view = self.create()
        client = self.controller.claude_clients[view["session"]["id"]]
        self.controller.close()
        with self.assertRaisesRegex(ValueError, "controller is stopping"):
            self.controller.resume(view["session"]["id"])
        self.assertFalse(client.alive)
        self.assertIs(self.controller.claude_clients[view["session"]["id"]], client)

    def test_one_claude_reconnect_cannot_invalidate_another_callback(self):
        first, second = self.create("One"), self.create("Two")
        one, two = (self.controller._store(v["session"]["id"]) for v in (first, second))
        callback = two.add_decision(two.metadata()["generation"], "callback", "claude/permission",
                                    {"tool_use_id": "tool-two"}, ["allow", "deny"])
        self.controller.claude_clients[one.metadata()["id"]].alive = False
        self.controller.resume(one.metadata()["id"])
        state = self.controller.status()["sessions"]
        other = next(v for v in state if v["session"]["id"] == two.metadata()["id"])
        self.assertEqual(other["decisions"][0]["id"], callback)
        self.assertTrue(other["decisions"][0]["can_answer"])
        self.assertNotEqual(one.metadata()["generation"], two.metadata()["generation"])
