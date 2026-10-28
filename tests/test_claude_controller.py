"""Provider availability and independently owned connection generations."""

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from awkit.session_http import SessionServer
from awkit.sessions import SessionController


class FakeClaude:
    def __init__(self, store, **kwargs):
        self.store = store
        self.generation = store.metadata()["generation"]
        self.alive = True
        self.initial_selection = store.metadata().get("model_selection")
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

    def test_common_creation_records_request_before_claude_construction(self):
        view = self.create(model="sonnet", reasoning_effort="medium")
        ident = view["session"]["id"]
        selected = self.controller.claude_clients[ident].initial_selection
        self.assertEqual(selected, dict(requested="sonnet", requested_effort="medium", creation=None, latest=None, state="requested"))
        self.assertIsNone(selected["latest"])
        status = self.controller.status()
        providers = status["capabilities"]["providers"]
        self.assertEqual(providers["claude"]["effort"]["values"], ["low", "medium", "high", "xhigh", "max"])
        self.assertIsNone(providers["codex"]["effort"]["values"])
        self.assertEqual(providers["claude"]["model"]["admission"], "submitted-request")
        self.assertEqual(providers["codex"]["model"]["admission"], "exact-receipt")
        self.assertTrue(status["sessions"][0]["can_send"])

    def test_http_claude_creation_and_unsupported_foreign_actions_share_validation(self):
        server = SessionServer(self.controller)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def post(action, **args):
            message = urllib.request.Request(server.url + "/api/command", data=json.dumps(dict(action=action, args=args)).encode(),
                headers={"Authorization": "Bearer " + server.token, "Content-Type": "application/json"})
            with urllib.request.urlopen(message) as response:
                return json.load(response)["result"]

        with patch("awkit.sessions.availability", return_value={"available": True}):
            view = post("create", name="HTTP Claude", responsibility="Invented", provider="claude", model="sonnet", reasoning_effort="medium")
        self.assertEqual(view["session"]["model_selection"]["requested"], "sonnet")
        self.assertEqual(view["session"]["model_selection"]["requested_effort"], "medium")
        self.assertFalse(post("discover", provider="claude")["available"])
        for action, args in (("enroll", dict(provider="claude", name="Foreign", thread_id="fictional")),
                             ("update", dict(ident=view["session"]["id"], body="Never sent"))):
            with self.subTest(action=action), self.assertRaises(urllib.error.HTTPError) as rejected:
                post(action, **args)
            self.assertEqual(rejected.exception.code, 400)
            rejected.exception.close()
        self.assertEqual(len(self.controller._stores), 1)
        self.assertIsNone(self.controller.provider)

    def test_unsupported_claude_effort_and_actions_refuse_before_native_work(self):
        for args in (dict(reasoning_effort="high"), dict(model="sonnet", reasoning_effort="custom"),
                     dict(model="sonnet", reasoning_effort=3)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.create(**args)
        self.assertEqual(self.controller._stores, {})
        page = self.controller.discover(provider="claude")
        self.assertFalse(page["available"])
        self.assertIn("transcripts", page["reason"])
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.controller.enroll(name="Foreign", thread_id="not-even-inspected", provider="claude")
        self.assertEqual(self.controller._stores, {})
        view = self.create()
        with self.assertRaisesRegex(ValueError, "steering is unavailable"):
            self.controller.update_turn(view["session"]["id"], key="never", body="Never sent")

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
