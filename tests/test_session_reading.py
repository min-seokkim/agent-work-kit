"""Read-only current-work projections on real local stores and the ordinary HTTP/CLI route."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from awkit.channel import Channel
from awkit.session_http import SessionServer, request
from awkit.session_reading import dispositions, project
from awkit.session_store import SessionStore
from awkit.sessions import SessionController


class StoredReadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = SessionStore.create(self.root, name="Worker", project=self.root, responsibility="Fictional work",
                                         generation="g1", permissions={})
        self.store.update(native_id="native-1", state="idle")

    def view(self, declarations=None):
        value = self.store.snapshot()
        value["dispositions"] = dispositions(value)
        project(value, declarations)
        return value

    def test_reservation_submission_acknowledgement_result_and_handling_stay_separate(self):
        message = self.store.post("one", "Return an invented ticket")
        self.assertEqual(self.view()["current_work"][0]["dispatch_state"], "queued")
        self.store.claim("g1")
        self.assertIn("reserved locally", self.view()["current_work"][0]["state"])
        self.store.rpc_intent("g1", 5)
        self.assertIn("submission attempted", self.view()["current_work"][0]["state"])
        self.store.bind_turn("g1", "turn-1")
        self.assertIn("acknowledged", self.view()["current_work"][0]["state"])
        self.store.bind_turn("g1", "turn-1", executing=True)
        self.assertIn("turn started", self.view()["current_work"][0]["state"])
        self.store.finish("g1", "turn-1", "completed", "Invented returned ticket")
        view = self.view()
        work = view["current_work"][0]
        self.assertEqual(work["request_id"], message["id"])
        self.assertEqual(work["reply_id"], view["messages"][-1]["id"])
        self.assertEqual(work["handling"]["state"], "unrecorded")
        declaration = dict(source=dict(relationship="worker", message=work["reply_id"]), state="pending",
                           action="Inspect this returned ticket", id="handle-ticket")
        declared = dict(report=dict(obligations=[declaration]), view_links=dict(worker=view["session"]["id"]))
        before = self.store.path.read_bytes()
        work = self.view(declared)["current_work"][0]
        self.assertEqual(work["handling"]["declarations"], [declaration])
        self.assertEqual(self.view(dict(error="unreadable record"))["current_work"][0]["handling"]["state"], "unavailable")
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_latest_public_item_is_exact_and_survives_tool_noise_and_recovery(self):
        message = self.store.post("one", "Fictional assignment")
        claim = self.store.claim("g1")
        self.store.bind_turn("g1", "turn-1", executing=True)
        params = dict(threadId="native-1", turnId="turn-1", item=dict(id="public-1", type="agentMessage",
                      phase="commentary", text="I will compare the two invented inputs."))
        self.store.event("g1", "item/completed", params)
        for i in range(40):
            self.store.event("g1", "item/completed", dict(threadId="native-1", turnId="turn-1",
                             item=dict(id=f"tool-{i}", type="commandExecution", text="Fixture tool output")))
        for changes, generation in ((dict(turnId="wrong-turn"), "g1"), (dict(threadId="other-thread"), "g1"),
                                    ({}, "unrelated-generation"), (dict(item=dict(type="agentMessage", phase="final_answer", text="Final only")), "g1"),
                                    (dict(item=dict(type="reasoning", text="Invented ineligible item")), "g1")):
            self.store.event(generation, "item/completed", {**params, **changes})
        view = self.view()
        public = view["current_work"][0]["public_update"]
        self.assertEqual(public["text"], params["item"]["text"])
        self.assertEqual((public["request_id"], public["attempt_id"], public["generation"]), (message["id"], claim["id"], "g1"))
        self.assertEqual(len(view["events"]), 30)
        self.assertNotIn(public["seq"], [row["seq"] for row in view["events"]])
        self.store.reconnect("g2")
        self.assertEqual(self.view()["current_work"][0]["public_update"], public)
        self.assertEqual(self.view()["current_work"][0]["dispatch_state"], "unresolved")

    def test_failed_report_and_queued_cancelled_work_do_not_imply_running(self):
        self.store.post("first", "Fictional failed task")
        self.store.claim("g1")
        self.store.bind_turn("g1", "turn-1", executing=True)
        self.store.event("g1", "item/completed", dict(threadId="native-1", turnId="turn-1",
                         item=dict(type="agentMessage", phase="commentary", text="Partial public report")))
        self.store.finish("g1", "turn-1", "failed", "")
        self.assertEqual(self.view()["current_work"][0]["dispatch_state"], "failed")
        self.store.post("second", "A new explicit queued assignment")
        cancelled = self.store.post("third", "An explicitly cancelled assignment")
        self.store.cancel(cancelled["id"])
        states = {row["dispatch_state"] for row in self.view()["current_work"]}
        self.assertEqual(states, {"queued", "cancelled"})
        failed = self.view()["dispositions"][0]
        self.assertEqual(failed["dispatch_state"], "failed")
        self.assertEqual(failed["public_update"]["text"], "Partial public report")
        self.assertIn("no reply", failed["state"])

    def test_submitted_decisions_are_not_new_responses_and_controls_are_unchanged(self):
        for i in range(9):
            ident = self.store.add_decision("g1", i, "claude/permission", dict(threadId="native-1"), ["allow", "deny"])
            self.store.answer_intent("g1", ident, "allow")
        view = self.store.snapshot()
        for decision in view["decisions"]:
            decision["can_answer"] = False
        before = copy.deepcopy(view["decisions"])
        project(view, None)
        self.assertEqual(view["decision_summary"], dict(responses_needed=0, submitted_unconfirmed=9, unavailable=0))
        self.assertEqual(view["decisions"], before)
        view["decisions"].extend([dict(state="pending", can_answer=True, response=None),
                                  dict(state="route unavailable", can_answer=False, response=None)])
        project(view, None)
        self.assertEqual(view["decision_summary"], dict(responses_needed=1, submitted_unconfirmed=9, unavailable=1))

    def test_claude_does_not_borrow_codex_commentary(self):
        self.store.post("one", "Fictional work")
        self.store.claim("g1")
        self.store.bind_turn("g1", "turn-1", executing=True)
        self.store.event("g1", "item/completed", dict(threadId="native-1", turnId="turn-1",
                         item=dict(type="agentMessage", phase="commentary", text="Not supported for Claude")))
        self.store.update(provider="claude")
        self.assertIsNone(self.view()["current_work"][0]["public_update"])

    def test_existing_linked_reply_without_a_native_attempt_is_not_a_queue(self):
        message = self.store.post("old", "An existing assignment with no native attempt record")
        reply = self.store.channel.post("reviewer", "main", "re", "Existing linked reply", reply_to=message["id"])
        work = self.view()["current_work"][0]
        self.assertEqual(work["dispatch_state"], "returned")
        self.assertEqual(work["reply_id"], reply)
        self.assertIn("native dispatch unrecorded", work["state"])
        self.assertFalse(work["can_cancel"])

    def test_current_active_assignment_precedes_an_older_unresolved_attempt(self):
        old = self.store.post("old", "Earlier uncertain assignment")
        self.store.claim("g1")
        self.store.bind_turn("g1", "old-turn")
        self.store.uncertain("g1", "Invented lost response")
        self.store.reconnect("g2")
        self.store.update(generation="g2", state="idle")
        current = self.store.post("new", "A separate explicit assignment after observed idle")
        self.store.claim("g2")
        self.store.bind_turn("g2", "new-turn", executing=True)
        work = self.view()["current_work"]
        self.assertEqual([row["request_id"] for row in work], [current["id"], old["id"]])
        self.assertEqual([row["dispatch_state"] for row in work], ["executing", "unresolved"])


class OrdinaryReadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.controller = SessionController(self.root, [sys.executable, str(Path(__file__).with_name("session_provider_fixture.py"))])
        self.addCleanup(self.controller.close)
        self.server = SessionServer(self.controller)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        (self.controller.directory / "controller.json").write_text(json.dumps(dict(schema=1, project=str(self.root),
             url=self.server.url, token=self.server.token)), encoding="utf-8")

    def wait(self, predicate):
        end = time.monotonic() + 15
        while time.monotonic() < end:
            view = request(self.root, "status")["sessions"][0]
            if predicate(view):
                return view
            time.sleep(.025)
        self.fail("Offline fixture did not settle")

    def test_http_and_cli_expose_public_update_without_mutating_or_overriding_stale_activity(self):
        self.controller.create(name="Worker", responsibility="Invented public progress")
        message = self.controller.send("Worker", key="held", body="HOLD")
        self.wait(lambda view: view["attempts"] and view["attempts"][0]["state"] == "executing")
        store = self.controller._store("Worker")
        attempt = store.snapshot()["attempts"][0]
        store.event(attempt["generation"], "item/completed", dict(threadId=attempt["native_id"], turnId=attempt["turn_id"],
                    item=dict(type="agentMessage", phase="commentary", text="Public fixture file plan: compare A and B.")))
        for i in range(40):
            store.event(attempt["generation"], "fixture/tool", dict(threadId=attempt["native_id"], turnId=attempt["turn_id"], index=i))
        store.update(observed_at="2000-01-01T00:00:00+00:00")
        before = hashlib.sha256(store.path.read_bytes()).digest()
        serial = self.controller.provider._serial
        view = request(self.root, "status")["sessions"][0]
        self.assertEqual(view["execution_state"], "unknown")
        self.assertEqual(view["current_work"][0]["request_id"], message["message"]["id"])
        self.assertEqual(view["current_work"][0]["public_update"]["text"], "Public fixture file plan: compare A and B.")
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"), PYTHONUTF8="1")
        cli = subprocess.run([sys.executable, "-m", "awkit", "session", "--project", str(self.root), "status"], env=env, capture_output=True, timeout=15)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["sessions"][0]["current_work"], view["current_work"])
        self.assertEqual(hashlib.sha256(store.path.read_bytes()).digest(), before)
        self.assertEqual(self.controller.provider._serial, serial)

    def test_pending_native_fixture_remains_respondable_without_submission(self):
        self.controller.create(name="Worker", responsibility="Fictional pending decision")
        self.controller.send("Worker", key="approval", body="ASK_APPROVAL")
        before = self.wait(lambda view: bool(view["decisions"]))
        view = request(self.root, "status")["sessions"][0]
        self.assertEqual(view["decision_summary"], dict(responses_needed=1, submitted_unconfirmed=0, unavailable=0))
        self.assertTrue(view["decisions"][0]["can_answer"])
        self.assertIsNone(view["decisions"][0]["response"])
        self.assertEqual(view["decisions"], before["decisions"])

    def test_ordinary_status_keeps_mixed_dispositions_and_explicit_older_handling_visible(self):
        generation = self.controller.generation
        store = SessionStore.create(self.controller.directory, name="Recorded fixture", project=self.root,
                                    responsibility="No native provider", generation=generation, permissions={})
        store.update(native_id="fictional-native", state="idle")
        self.controller._stores[store.metadata()["id"]] = store
        first = store.post("first", "Return an invented result")
        store.claim(generation)
        store.bind_turn(generation, "first-turn")
        store.finish(generation, "first-turn", "completed", "Returned invented result")
        second = store.post("second", "An independent failed task")
        store.claim(generation)
        store.bind_turn(generation, "second-turn")
        store.finish(generation, "second-turn", "failed", "")
        current = store.post("third", "Current reserved fixture")
        record = self.root / "task.json"
        record.write_text(json.dumps(dict(schema=1, session="planning-native", relationships=[dict(
            id="worker", channel=str(store.path), local_role="main", counterpart="fictional-native")],
            obligations=[dict(id="handle-first", source=dict(relationship="worker", message=first["id"]),
                              responsible_session="planning-native", action="Inspect the returned result", state="pending",
                              evidence=[dict(relationship="worker", message=store.snapshot()["messages"][1]["id"])])])), encoding="utf-8")
        self.controller.record = record

        def reading():
            return request(self.root, "status")["sessions"][0]

        self.assertEqual(reading()["dispositions"][-1]["dispatch_state"], "queued")
        store.claim(generation)
        self.assertIn("reserved locally", reading()["dispositions"][-1]["state"])
        store.rpc_intent(generation, 42)
        self.assertIn("submission attempted", reading()["dispositions"][-1]["state"])
        store.bind_turn(generation, "current-turn")
        self.assertIn("acknowledged", reading()["dispositions"][-1]["state"])
        store.uncertain(generation, "Invented transport uncertainty")
        queued = store.post("fourth", "A separate queued request")
        before = store.path.read_bytes()
        view = reading()
        visible = {row["request_id"]:row for row in view["current_work"]}
        self.assertEqual(view["current_work"][0]["request_id"], current["id"])
        self.assertEqual(set(visible), {first["id"], second["id"], current["id"], queued["id"]})
        self.assertEqual(visible[first["id"]]["handling"]["declarations"][0]["state"], "pending")
        self.assertEqual(visible[second["id"]]["handling"]["state"], "unrecorded")
        self.assertEqual(visible[current["id"]]["dispatch_state"], "uncertain")
        self.assertEqual(visible[queued["id"]]["dispatch_state"], "queued")
        self.assertEqual(store.path.read_bytes(), before)
        self.assertIsNone(self.controller.provider)

    def test_old_history_never_claims_a_native_queue_and_reads_preserve_bytes_and_cursors(self):
        path = self.root / "history.sqlite3"
        channel = Channel(path)
        old = channel.post("main", "reviewer", "question", "An old recorded request")
        newer = channel.post("main", "reviewer", "question", "An unrelated later request")
        channel.post("reviewer", "main", "re", "A reply only to the later request", reply_to=newer)
        channel.find("reviewer", "new")
        self.controller.register_history(channel=str(path), main_name="A", reviewer_name="B")
        before = path.read_bytes()
        view = request(self.root, "status")["sessions"][0]
        self.assertEqual(view["current_work"][0]["dispatch_state"], "history")
        self.assertIn("native execution unavailable", view["dispositions"][0]["state"])
        self.assertIn(old, view["unanswered"])
        self.assertIsNone(view["dispositions"][0]["reply_id"])
        self.assertFalse(view["dispositions"][0]["can_cancel"])
        self.assertFalse(view["can_send"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(channel.find("reviewer", "new")[0], 1)
