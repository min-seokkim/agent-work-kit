"""Explicit model admission through real controllers with deterministic native fixtures."""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from awkit.codex_enrollment import EXECUTABLE_SHA256, VERSION
from awkit.codex_session import ProviderError, ProviderRejected
from awkit.session_store import SessionStore
from awkit.sessions import SessionController


class ModelProvider:
    def __init__(self, controller, state):
        self.controller, self.state = controller, state
        self.project = controller.project
        self.command = tuple(controller.command)
        self.alive = True
        self.initialization = {}
        self.process = SimpleNamespace(pid=123)
        self.calls = []
        self.start_overrides = {}
        self.resume_overrides = {}
        self.reject_start = self.reject_turn = False
        self.lose_response = False
        self.before_start = None

    def call(self, method, params, *, on_request=None):
        if on_request:
            on_request("fixture-rpc-" + str(len(self.calls) + 1))
        self.calls.append((method, params))
        if method == "thread/start":
            if self.before_start:
                self.before_start()
            if self.reject_start:
                raise ProviderRejected("fixture rejected model", {"code": -1})
            self.state.update(id="fixture-thread", model=params.get("model", "native-default"), provider="fixture-provider",
                              memory="", count=0)
            if self.lose_response:
                raise ProviderError("fixture response lost")
            return self.result(self.start_overrides)
        if method == "thread/resume":
            if params["threadId"] != self.state["id"]:
                raise AssertionError("resume changed identity")
            return self.result(self.resume_overrides)
        if method == "thread/read":
            return dict(thread=dict(id=self.state["id"], cwd=str(self.project), canAcceptDirectInput=True,
                                    status={"type": "active" if self.state.get("holding") else "idle"}))
        if method == "turn/steer":
            return dict(turnId=params["expectedTurnId"])
        if method == "turn/start":
            if self.reject_turn:
                raise ProviderRejected("fixture model unavailable", {"code": -1})
            self.state["count"] += 1
            turn = "turn-" + str(self.state["count"])
            body = params["input"][0]["text"]
            if body == "HOLD":
                self.state["holding"] = True
                return dict(turn=dict(id=turn))
            answer = self.state["memory"] if body == "recall" else body
            if not self.state["memory"]:
                self.state["memory"] = body
            self.controller._message(dict(method="turn/completed", params=dict(threadId=self.state["id"],
                turn=dict(id=turn, status="completed", items=[dict(type="agentMessage", id=turn + "-answer", text=answer)]))))
            return dict(turn=dict(id=turn))
        raise AssertionError(method)

    def result(self, overrides):
        return dict(thread=dict(id=self.state["id"], status={"type": "idle"}), cwd=str(self.project),
                    sandbox={"type": "readOnly"}, approvalPolicy="on-request", approvalsReviewer="user",
                    model=self.state["model"], modelProvider=self.state["provider"], reasoningEffort=None) | overrides

    def close(self):
        self.alive = False


class SessionModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()
        self.native = {}
        self.make_controller()

    def make_controller(self):
        self.controller = SessionController(self.project, ["fictional-runtime"])
        self.addCleanup(self.controller.close)
        self.provider = ModelProvider(self.controller, self.native)
        self.controller.provider = self.provider
        self.controller.client = dict(command=list(self.provider.command), version=VERSION, version_exit=0,
                                      executable_sha256=EXECUTABLE_SHA256)

    def create(self, **kwargs):
        return self.controller.create(name="Fictional reviewer", responsibility="Use invented context", **kwargs)["session"]

    def wait_for(self, ident, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            snapshot = self.controller._store(ident).snapshot()
            if predicate(snapshot):
                return snapshot
            time.sleep(0.02)
        self.fail("Fixture controller condition did not complete")

    def test_default_creation_keeps_previous_native_request_and_metadata(self):
        meta = self.create()
        self.assertNotIn("model_selection", meta)
        self.assertEqual(meta["model"], "native-default")
        self.assertEqual(set(self.provider.calls[0][1]), {"cwd", "sandbox", "approvalPolicy", "approvalsReviewer",
                                                        "serviceName", "developerInstructions"})

    def test_explicit_intent_is_durable_before_native_input_and_receipt_is_separate(self):
        def before():
            store = next(iter(self.controller._stores.values()))
            self.assertEqual(store.metadata()["model_selection"], dict(requested="fictional:opaque", creation=None,
                                                                       latest=None, state="pending"))

        self.provider.before_start = before
        meta = self.create(model="fictional:opaque")
        self.assertEqual(self.provider.calls[0][1]["model"], "fictional:opaque")
        selection = meta["model_selection"]
        self.assertEqual(set(selection), {"requested", "creation", "latest", "state"})
        self.assertEqual(selection["state"], "matched")
        self.assertEqual(selection["creation"], dict(model="fictional:opaque", provider="fixture-provider",
                                                    reasoning_effort=None, source="thread/start response"))

    def test_invalid_ids_and_claude_refuse_before_records_or_provider_calls(self):
        for model in ("", " ", "with space", "line\nbreak", "x" * 201, 3, True):
            with self.subTest(model=model), self.assertRaises(ValueError):
                self.create(model=model)
        with self.assertRaises(ValueError):
            self.create(model="fictional", provider="claude")
        self.assertEqual(self.controller._stores, {})
        self.assertEqual(self.provider.calls, [])

    def test_unsupported_runtime_holds_intent_without_native_thread_creation(self):
        self.controller.client["executable_sha256"] = "unsupported"
        meta = self.create(model="fictional")
        self.assertEqual(meta["model_selection"]["state"], "held")
        self.assertIsNone(meta["native_id"])
        self.assertEqual(self.provider.calls, [])

    def test_creation_mismatch_and_malformed_configuration_hold_and_keep_identity(self):
        for override in ({"model": "different"}, {"model": None}, {"model": ["malformed"]},
                         {"modelProvider": ""}, {"modelProvider": None}, {"modelProvider": {"bad": True}}):
            with self.subTest(override=override):
                self.provider.start_overrides = override
                meta = self.controller.create(name="Case " + str(len(self.controller._stores)), responsibility="Invented",
                                              model="fictional")["session"]
                self.assertEqual(meta["model_selection"]["state"], "held")
                self.assertEqual(meta["returned_native_id"], "fixture-thread")
                self.assertEqual(meta["state"], "unknown")
                with self.assertRaises(ValueError):
                    self.controller.send(meta["id"], key="never", body="must remain held")

    def test_wrong_project_retains_actual_configuration_but_does_not_admit_identity(self):
        self.provider.start_overrides = dict(cwd=str(self.project.parent), model="different")
        meta = self.create(model="fictional")
        self.assertIsNone(meta["native_id"])
        self.assertEqual(meta["returned_native_id"], "fixture-thread")
        self.assertEqual(meta["model_selection"]["latest"]["model"], "different")
        self.assertEqual(meta["model"], "different")

    def test_creation_rejection_and_response_loss_have_no_fallback_or_replacement(self):
        for attr in ("reject_start", "lose_response"):
            setattr(self.provider, attr, True)
            meta = self.controller.create(name=attr, responsibility="Invented", model="fictional")["session"]
            setattr(self.provider, attr, False)
            self.assertIsNone(meta["native_id"])
            self.assertEqual(meta["model_selection"]["state"], "held")
            self.assertIsNone(meta["model_selection"]["latest"])
        self.assertEqual([method for method, _ in self.provider.calls], ["thread/start", "thread/start"])

    def test_two_turns_and_restart_keep_identity_context_and_omit_model_overrides(self):
        meta = self.create(model="fictional")
        self.controller.send(meta["id"], key="one", body="Invented cedar token")
        self.wait_for(meta["id"], lambda view: len(view["messages"]) == 2)
        self.controller.send(meta["id"], key="two", body="recall")
        view = self.wait_for(meta["id"], lambda view: len(view["messages"]) == 4)
        self.assertEqual(view["messages"][-1]["body"], "Invented cedar token")
        before_calls = list(self.provider.calls)
        self.controller.close()
        self.make_controller()
        resumed = self.controller.resume(meta["id"])["session"]
        self.assertEqual(resumed["native_id"], meta["native_id"])
        self.assertEqual(resumed["model_selection"]["state"], "matched")
        self.assertEqual(resumed["model_selection"]["latest"]["source"], "thread/resume response")
        self.assertEqual(resumed["model_selection"]["creation"], meta["model_selection"]["creation"])
        for method, params in before_calls + self.provider.calls:
            if method in ("turn/start", "thread/resume"):
                self.assertFalse(set(params) & {"model", "modelProvider", "config", "effort", "reasoningEffort", "collaborationMode"})

    def test_resume_mismatch_keeps_queued_work_unclaimed_before_reconciliation(self):
        meta = self.create(model="fictional")
        store = self.controller._store(meta["id"])
        self.controller._stop.set()
        self.controller._worker.join(timeout=2)
        store.post("queued", "Do not release this queued input")
        self.controller.close()
        self.make_controller()
        self.provider.resume_overrides = dict(model="changed-default", modelProvider="changed-provider")
        resumed = self.controller.resume(meta["id"])["session"]
        self.assertEqual(resumed["model_selection"]["state"], "held")
        self.assertEqual(resumed["model_selection"]["creation"], meta["model_selection"]["creation"])
        self.assertEqual(resumed["model_selection"]["latest"]["model"], "changed-default")
        time.sleep(0.4)
        self.assertEqual([method for method, _ in self.provider.calls], ["thread/resume"])
        self.assertEqual(store.snapshot()["attempts"], [])
        self.assertEqual(len(store.snapshot()["unanswered"]), 1)

    def test_resume_requires_both_model_and_creation_provider_and_retains_latest(self):
        meta = self.create(model="fictional")
        store = self.controller._store(meta["id"])
        for overrides in ({"model": None}, {"model": ["malformed"]}, {"modelProvider": None},
                          {"modelProvider": "different-provider"}):
            with self.subTest(overrides=overrides):
                store.update(state="unknown")
                self.provider.resume_overrides = overrides
                self.provider.calls.clear()
                result = self.controller.resume(meta["id"])["session"]
                self.assertEqual(result["model_selection"]["state"], "held")
                self.assertEqual(result["model_selection"]["creation"], meta["model_selection"]["creation"])
                self.assertEqual([method for method, _ in self.provider.calls], ["thread/resume"])
                for field, value in overrides.items():
                    key = "provider" if field == "modelProvider" else field
                    self.assertEqual(result["model_selection"]["latest"][key], value)

    def test_malformed_full_response_holds_without_an_invented_observation(self):
        self.provider.call = lambda *args, **kwargs: None
        meta = self.create(model="fictional")
        self.assertEqual(meta["model_selection"]["state"], "held")
        self.assertIsNone(meta["model_selection"]["latest"])
        self.assertIsNone(meta["native_id"])

    def test_resume_runtime_or_permission_change_holds_before_queued_work(self):
        meta = self.create(model="fictional")
        store = self.controller._store(meta["id"])
        store.update(state="unknown")
        self.controller.client["version"] = "unsupported"
        self.provider.calls.clear()
        result = self.controller.resume(meta["id"])["session"]
        self.assertEqual(result["model_selection"]["state"], "held")
        self.assertEqual(self.provider.calls, [])
        self.controller.client["version"] = VERSION
        self.provider.resume_overrides = dict(approvalPolicy="never")
        result = self.controller.resume(meta["id"])["session"]
        self.assertEqual(result["model_selection"]["state"], "held")
        self.assertEqual(result["model_selection"]["creation"], meta["model_selection"]["creation"])
        self.assertEqual([method for method, _ in self.provider.calls], ["thread/resume"])
        self.assertEqual(result["returned_scope"]["approvalPolicy"], "never")

    def test_native_first_turn_rejection_does_not_choose_another_model(self):
        meta = self.create(model="fictional-unavailable")
        self.provider.reject_turn = True
        self.controller.send(meta["id"], key="rejection", body="invented input")
        view = self.wait_for(meta["id"], lambda value: bool(value["attempts"]))
        self.wait_for(meta["id"], lambda value: value["session"]["state"] == "unknown")
        self.assertEqual(view["session"]["model_selection"]["requested"], "fictional-unavailable")
        self.assertEqual(len([method for method, _ in self.provider.calls if method == "turn/start"]), 1)

    def test_held_selection_blocks_active_turn_update_and_status_target(self):
        meta = self.create(model="fictional")
        posted = self.controller.send(meta["id"], key="active", body="HOLD")
        view = self.wait_for(meta["id"], lambda value: bool(value["attempts"]) and bool(value["attempts"][0]["turn_id"]))
        turn_id = view["attempts"][0]["turn_id"]
        args = dict(key="matched-update", request_id=posted["message"]["id"], expected_turn_id=turn_id, body="Invented update")
        matched = self.controller.update_turn(meta["id"], **args)
        self.assertEqual(matched["update"]["state"], "acknowledged")
        store = self.controller._store(meta["id"])
        store.update(model_selection=dict(meta["model_selection"], state="held"), state="running")
        before = len(self.provider.calls)
        with self.assertRaisesRegex(ValueError, "held"):
            self.controller.update_turn(meta["id"], **dict(args, key="held-update"))
        self.assertEqual(len(self.provider.calls), before)
        status = self.controller.status()["sessions"][0]
        self.assertIsNone(status["update_target"])
        self.assertFalse(status["can_send"])
        self.assertIn("Work remains held", status["control_reason"])

    def test_completion_after_failed_recovery_cannot_release_queued_work(self):
        meta = self.create(model="fictional")
        self.controller.send(meta["id"], key="active", body="HOLD")
        active = self.wait_for(meta["id"], lambda v: bool(v["attempts"]) and bool(v["attempts"][0]["turn_id"]))
        turn_id = active["attempts"][0]["turn_id"]
        queued = self.controller.send(meta["id"], key="queued", body="Must stay queued")["message"]["id"]
        self.controller.close()
        self.make_controller()
        entered, release = threading.Event(), threading.Event()
        original_call, original_resume = self.provider.call, self.controller.resume
        reads = []

        def call(method, params, **kwargs):
            if method == "thread/turns/list":
                return dict(data=[dict(id=turn_id, status="inProgress", itemsView="full", items=[])], nextCursor=None)
            if method == "thread/read" and not reads:
                reads.append(True)
                raise ProviderError("Fictional reconciliation failure")
            return original_call(method, params, **kwargs)

        def resumed(ident):
            result = original_resume(ident)
            entered.set()
            if not release.wait(5):
                raise AssertionError("Callback fixture barrier timed out")
            return result

        self.provider.call = call
        self.provider.resume_overrides = dict(thread=dict(id=meta["native_id"], status=dict(type="active")))
        self.controller.resume = resumed
        try:
            self.assertTrue(entered.wait(5))
            store = self.controller._store(meta["id"])
            self.assertEqual(store.metadata()["model_selection"]["state"], "held")
            self.native["holding"] = False
            self.controller._message(dict(method="turn/completed", params=dict(threadId=meta["native_id"],
                turn=dict(id=turn_id, status="completed", items=[dict(type="agentMessage", id="late", text="Old reply")]))))
            self.assertEqual(store.metadata()["state"], "idle")
            release.set()
            time.sleep(.8)  # Observe the resumed iteration and subsequent queue polls.
            snapshot = store.snapshot()
            self.assertEqual(snapshot["session"]["model_selection"]["state"], "held")
            self.assertEqual(len(snapshot["attempts"]), 1)
            self.assertIn(queued, snapshot["unanswered"])
            self.assertNotIn("turn/start", [method for method, _ in self.provider.calls])
        finally:
            release.set()

    def test_claim_reads_hold_in_the_same_sqlite_transaction_as_reservation(self):
        meta = self.create(model="fictional")
        self.controller._stop.set()
        self.controller._worker.join(timeout=2)
        store = self.controller._store(meta["id"])
        store.post("queued", "Must remain unclaimed")
        other = SessionStore(store.path)
        started, finished = threading.Event(), threading.Event()
        result = []

        def claim():
            started.set()
            result.append(other.claim(self.controller.generation))
            finished.set()

        thread = threading.Thread(target=claim)
        with store.channel.transaction() as conn:
            store._update(conn, model_selection=dict(meta["model_selection"], state="held"), state="idle")
            thread.start()
            self.assertTrue(started.wait(2))
            self.assertFalse(finished.wait(.05))
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [None])
        self.assertEqual(store.snapshot()["attempts"], [])

    def test_hold_after_reservation_refuses_rpc_admission(self):
        meta = self.create(model="fictional")
        self.controller._stop.set()
        self.controller._worker.join(timeout=2)
        store = self.controller._store(meta["id"])
        store.post("queued", "Reserved but not admitted")
        self.assertIsNotNone(store.claim(self.controller.generation))
        store.update(model_selection=dict(meta["model_selection"], state="held"))
        with self.assertRaisesRegex(ValueError, "held"):
            store.rpc_intent(self.controller.generation, "must-not-admit")
        self.assertIsNone(store.snapshot()["attempts"][0]["rpc_id"])

    def test_hold_during_update_preflight_refuses_native_steering(self):
        meta = self.create(model="fictional")
        posted = self.controller.send(meta["id"], key="active", body="HOLD")
        active = self.wait_for(meta["id"], lambda v: bool(v["attempts"]) and bool(v["attempts"][0]["turn_id"]))
        store = self.controller._store(meta["id"])
        entered, release = threading.Event(), threading.Event()
        original_call = self.provider.call
        results = []

        def call(method, params, **kwargs):
            if method == "thread/read":
                entered.set()
                if not release.wait(5):
                    raise AssertionError("Update fixture barrier timed out")
            return original_call(method, params, **kwargs)

        self.provider.call = call
        thread = threading.Thread(target=lambda: results.append(self.controller.update_turn(meta["id"],
            key="in-flight", request_id=posted["message"]["id"], expected_turn_id=active["attempts"][0]["turn_id"],
            body="Must not reach native steering")))
        try:
            thread.start()
            self.assertTrue(entered.wait(5))
            store.update(model_selection=dict(meta["model_selection"], state="held"), state="running")
            release.set()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(results[0]["state"], "refused")
            self.assertIn("held", results[0]["update"]["error"])
            self.assertNotIn("turn/steer", [method for method, _ in self.provider.calls])
            self.assertFalse(any(e["method"] == "awkit/turnUpdateDispatch" for e in store.snapshot()["events"]))
        finally:
            release.set()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
