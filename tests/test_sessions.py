"""Controller acceptance with an offline provider; live acceptance is recorded separately."""

import sys
import tempfile
import time
import unittest
from pathlib import Path

from awkit.sessions import SessionController

FIXTURE = Path(__file__).with_name("session_provider_fixture.py")


class SessionControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.controller = SessionController(self.project, [sys.executable, str(FIXTURE)])
        self.addCleanup(self.controller.close)

    def create(self):
        result = self.controller.create(name="Research", responsibility="Read invented facts")
        self.assertEqual(result["session"]["state"], "idle", result)
        return result["session"]

    def wait_for(self, predicate, *, timeout=35):
        # Admission alone has a 30s RPC budget; six seconds also counted durable I/O.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            views = self.controller.status()["sessions"]
            if views and predicate(views[0]):
                return views[0]
            time.sleep(0.025)
        self.fail(f"Controller condition timed out: {self.controller.status()}")

    def test_two_tasks_after_idle_share_native_identity_and_retained_context(self):
        session = self.create()
        first = self.controller.send(session["id"], key="first", body="An invented otter is named Cedar.", entry="human")
        one = self.wait_for(lambda view: len(view["messages"]) == 2)
        self.assertEqual(one["session"]["state"], "idle")
        self.assertEqual(one["attempts"][0]["request_id"], first["message"]["id"])
        self.controller.send(session["id"], key="notice", body="Informational only", kind="notice")
        self.controller.send(session["id"], key="second", body="recall")
        two = self.wait_for(lambda view: len(view["messages"]) == 5)
        self.assertEqual(two["session"]["native_id"], session["native_id"])
        self.assertIn("Cedar", two["messages"][-1]["body"])
        self.assertEqual(len(two["attempts"]), 2)
        self.assertEqual(len({row["turn_id"] for row in two["attempts"]}), 2)
        self.assertTrue(all(row["rpc_id"] for row in two["attempts"]))

    def test_early_events_are_reconciled_only_to_the_response_turn(self):
        session = self.create()
        self.controller.send(session["id"], key="early", body="EARLY")
        view = self.wait_for(lambda value: len(value["messages"]) == 2)
        self.assertEqual(view["messages"][-1]["body"], "Fixture reply: EARLY")
        self.assertEqual(view["attempts"][0]["state"], "returned")

    def test_approval_requires_explicit_choice_on_the_original_connection(self):
        session = self.create()
        self.controller.send(session["id"], key="approval", body="ASK_APPROVAL")
        view = self.wait_for(lambda value: bool(value["decisions"]))
        decision = view["decisions"][0]
        self.assertEqual(decision["state"], "pending")
        self.assertEqual(len(view["messages"]), 1)
        with self.assertRaises(ValueError):
            self.controller.decide(session["id"], decision["id"], "invented-choice")
        self.controller.decide(session["id"], decision["id"], "decline")
        view = self.wait_for(lambda value: len(value["messages"]) == 2)
        self.assertEqual(view["decisions"][0]["state"], "resolved")
        self.assertIn("decline", view["messages"][-1]["body"])

    def test_disconnection_preserves_uncertainty_and_never_replays(self):
        session = self.create()
        self.controller.send(session["id"], key="disconnect", body="DISCONNECT")
        view = self.wait_for(lambda value: value["attempts"] and value["attempts"][0]["state"] == "uncertain")
        self.assertFalse(view["can_send"])
        self.assertIsNone(view["attempts"][0]["reply_id"])
        with self.assertRaises(ValueError):
            self.controller.send(session["id"], key="another", body="Do not resend")
        self.assertEqual(len(self.controller.status()["sessions"][0]["messages"]), 1)

    def test_another_live_controller_cannot_take_ownership(self):
        with self.assertRaisesRegex(ValueError, "Another controller"):
            SessionController(self.project, [sys.executable, str(FIXTURE)])

    def test_wrong_turn_cannot_finish_a_current_assignment(self):
        session = self.create()
        self.controller.send(session["id"], key="approval", body="ASK_APPROVAL")
        self.wait_for(lambda value: bool(value["decisions"]))
        self.controller._message(dict(method="turn/completed", params=dict(threadId=session["native_id"],
                                   turn=dict(id="wrong-turn", status="completed", items=[dict(type="agentMessage",
                                             id="foreign", text="Not this assignment")]))))
        view = self.controller.status()["sessions"][0]
        self.assertEqual(len(view["messages"]), 1)
        self.assertEqual(view["attempts"][0]["state"], "executing")
