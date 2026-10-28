"""Exact-turn transport, durable intent and race/refusal checks using an offline provider."""

import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from awkit.cli import main
from awkit.codex_session import ProviderError, ProviderRejected
from awkit.session_http import SessionServer, request
from awkit.session_updates import EXECUTABLE_SHA256, VERSION
from awkit.sessions import SessionController


class TurnUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.command = [sys.executable, str(Path(__file__).with_name("session_provider_fixture.py"))]
        self.start()
        self.controller.create(name="Worker", responsibility="Invented held assignment")
        self.store = self.controller._store("Worker")
        # This is an offline runtime fixture, not live native runtime verification.
        self.store.update(client=dict(version=VERSION, executable_sha256=EXECUTABLE_SHA256))
        self.message = self.controller.send("Worker", key="original", body="HOLD")["message"]
        self.active = self.wait(lambda v: v["update_target"] is not None)["update_target"]

    def start(self):
        self.controller = SessionController(self.project, self.command)
        self.addCleanup(self.controller.close)

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            view = self.controller.status()["sessions"][0]
            if predicate(view):
                return view
            time.sleep(.025)
        self.fail(str(view))

    def args(self, body="Use the South dock", key="correction"):
        return dict(key=key, request_id=self.message["id"], expected_turn_id=self.active["expected_turn_id"], body=body)

    def test_same_turn_reply_stays_with_original_request_and_duplicate_never_calls_provider(self):
        result = self.controller.update_turn("Worker", **self.args())
        self.assertEqual(result["state"], "acknowledged")
        final = self.wait(lambda v: len(v["messages"]) == 2)
        self.assertEqual(final["messages"][0], self.message)
        self.assertEqual(final["messages"][-1]["reply_to"], self.message["id"])
        self.assertEqual(len(final["attempts"]), 1)
        self.assertEqual(final["attempts"][0]["turn_id"], self.active["expected_turn_id"])
        self.assertIn("South dock", final["messages"][-1]["body"])
        self.assertEqual(len(final["turn_updates"]), 1)
        self.assertEqual(final["extension_schema"], 3)
        with patch.object(self.controller.provider, "call", side_effect=AssertionError("must not call")):
            duplicate = self.controller.update_turn("Worker", **self.args())
        self.assertTrue(duplicate["recovered"])
        self.assertEqual(duplicate["update"]["id"], result["update"]["id"])
        self.assertEqual(duplicate["state"], "acknowledged")

    def test_wrong_target_turn_request_provider_runtime_or_input_are_refused(self):
        self.controller.create(name="Other", responsibility="Different invented conversation")
        cases = [("Other", self.args()), ("Worker", dict(self.args(), expected_turn_id="stale")),
                 ("Worker", dict(self.args(), request_id="M-999")), ("Worker", dict(self.args(), body="")),
                 ("Worker", self.args(key="original"))]
        for ident, args in cases:
            with self.subTest(ident=ident, args=args), self.assertRaises(ValueError):
                self.controller.update_turn(ident, **args)
        for field, value in (("provider", "claude"), ("client", {})):
            saved = self.store.metadata()[field]
            self.store.update(**{field: value})
            try:
                with self.assertRaises(ValueError):
                    self.controller.update_turn("Worker", **self.args())
            finally:
                self.store.update(**{field: saved})
        self.assertEqual(self.store.turn_updates(), [])

    def test_duplicate_key_different_body_or_target_refuses(self):
        self.controller.update_turn("Worker", **self.args("KEEP_HOLDING"))
        with self.assertRaisesRegex(ValueError, "turn update"):
            self.controller.send("Worker", key="correction", body="An explicit new assignment needs a fresh key")
        with self.assertRaisesRegex(ValueError, "turn update"):
            self.controller.send("Worker", key="correction", body="A separate notice", kind="notice")
        self.controller.create(name="Other", responsibility="Different invented conversation")
        for ident, args in (("Worker", self.args("different")), ("Worker", dict(self.args("KEEP_HOLDING"), expected_turn_id="other")),
                            ("Worker", dict(self.args("KEEP_HOLDING"), request_id="M-999")), ("Other", self.args("KEEP_HOLDING"))):
            with self.subTest(ident=ident, args=args), self.assertRaisesRegex(ValueError, "key already names"):
                self.controller.update_turn(ident, **args)

    def test_persistence_failure_prevents_native_call(self):
        with patch.object(self.store, "turn_update_intent", side_effect=sqlite3.OperationalError("injected disk failure")), \
                patch.object(self.controller.provider, "call") as call:
            with self.assertRaises(sqlite3.Error):
                self.controller.update_turn("Worker", **self.args())
            call.assert_not_called()
        original_event = self.store.event
        def failed_dispatch(generation, method, params, **kwargs):
            if method == "awkit/turnUpdateDispatch":
                raise sqlite3.OperationalError("injected pre-write RPC persistence failure")
            return original_event(generation, method, params, **kwargs)
        with patch.object(self.store, "event", side_effect=failed_dispatch), \
                patch.object(self.controller.provider, "_write", wraps=self.controller.provider._write) as write:
            with self.assertRaises(sqlite3.Error):
                self.controller.update_turn("Worker", **self.args())
            self.assertEqual([args[0]["method"] for args, _ in write.call_args_list], ["thread/read"])
        self.assertEqual(self.store.turn_updates()[0]["state"], "uncertain")
        with patch.object(self.controller.provider, "call", side_effect=AssertionError("must not replay")):
            self.assertTrue(self.controller.update_turn("Worker", **self.args())["recovered"])

    def test_race_native_rejection_and_wrong_ack_do_not_fallback(self):
        provider = self.controller.provider
        with self.assertRaises(ProviderRejected):
            provider.call("turn/steer", dict(threadId=self.store.metadata()["native_id"], expectedTurnId="stale",
                                           input=[dict(type="text", text="Fixture stale-turn check")]))
        original = provider.call
        for index, failure in enumerate((ProviderRejected("expected turn ended", {"code": -32600}),
                ProviderError("lost RPC response"), {"turnId": "other"}, ProviderRejected("native internal error", {"code": -32603}))):
            calls = []
            def rpc(method, params, _calls=calls, _failure=failure, **kwargs):
                _calls.append((method, params))
                if method != "turn/steer":
                    return original(method, params, **kwargs)
                kwargs["on_request"]("injected-rpc")
                if isinstance(_failure, Exception):
                    raise _failure
                return _failure
            with patch.object(provider, "call", side_effect=rpc):
                result = self.controller.update_turn("Worker", **self.args(key=f"race{index}"))
            self.assertEqual(result["state"], "refused" if index == 0 else "uncertain")
            if index == 2:
                self.assertEqual(result["update"]["native_response"]["turnId"], "other")
            if index == 3:
                self.assertEqual(result["update"]["native_error"]["code"], -32603)
            self.assertEqual([method for method, _ in calls], ["thread/read", "turn/steer"])
            self.assertEqual(calls[-1][1]["expectedTurnId"], self.active["expected_turn_id"])
            self.assertEqual(len(self.store.snapshot()["attempts"]), 1)

    def test_unavailable_native_observation_never_steers(self):
        meta = self.store.metadata()
        base = dict(id=meta["native_id"], cwd=str(self.project), status=dict(type="active"), canAcceptDirectInput=True)
        cases = [dict(base, id="other"), dict(base, cwd=str(self.project.parent)), dict(base, status=dict(type="idle")),
                 dict(base, status=None), dict(base, canAcceptDirectInput=False), None]
        for index, observed in enumerate(cases):
            def rpc(method, params, _observed=observed, **kwargs):
                self.assertEqual(method, "thread/read")
                return dict(thread=_observed)
            with patch.object(self.controller.provider, "call", side_effect=rpc) as call:
                result = self.controller.update_turn("Worker", **self.args(key=f"observation{index}"))
                self.assertEqual(result["state"], "refused")
                self.assertEqual(call.call_count, 1)

    def test_completed_turn_refuses_new_input_and_send_notice_meanings_remain(self):
        self.controller.send("Worker", key="notice", body="Information only", kind="notice")
        queued = self.controller.send("Worker", key="queued", body="Independent later assignment")["message"]
        before = self.store.snapshot()
        self.assertEqual(len(before["attempts"]), 1)
        self.controller.update_turn("Worker", **self.args())
        final = self.wait(lambda v: len(v["attempts"]) == 2 and v["attempts"][-1]["state"] == "returned")
        self.assertEqual(final["attempts"][-1]["request_id"], queued["id"])
        self.assertEqual(len(final["attempts"]), 2)
        before = self.store.snapshot()
        with patch.object(self.controller.provider, "call") as call:
            with self.assertRaisesRegex(ValueError, "No active turn is currently observed"):
                self.controller.update_turn("Worker", **self.args(key="ended"))
            call.assert_not_called()
        after = self.store.snapshot()
        self.assertEqual(after["turn_updates"], before["turn_updates"])
        self.assertEqual(after["messages"], before["messages"])

    def test_lost_response_and_restart_retain_uncertainty_without_replay(self):
        args = self.args("LOSE_UPDATE_RESPONSE")
        result = self.controller.update_turn("Worker", **args)
        self.assertEqual(result["state"], "uncertain")
        before = self.store.turn_updates()
        self.controller.close()
        self.start()
        self.wait(lambda v: v["can_send"])
        with patch.object(self.controller.provider, "call", side_effect=AssertionError("must not replay")):
            recovered = self.controller.update_turn("Worker", **args)
        self.assertTrue(recovered["recovered"])
        self.assertEqual(recovered["update"], before[0])
        self.assertEqual(recovered["state"], "uncertain")
        self.assertEqual(len(self.controller._store("Worker").snapshot()["attempts"]), 1)

    def test_concurrent_same_key_has_one_intent_and_one_native_call(self):
        reached, release = threading.Event(), threading.Event()
        original = self.controller.provider.call
        calls = []
        results, errors = [], []
        def rpc(method, params, **kwargs):
            if method == "turn/steer":
                calls.append(params)
                reached.set()
                release.wait(3)
            return original(method, params, **kwargs)
        def first():
            try:
                results.append(self.controller.update_turn("Worker", **self.args("KEEP_HOLDING")))
            except Exception as exc:
                errors.append(exc)
        with patch.object(self.controller.provider, "call", side_effect=rpc):
            worker = threading.Thread(target=first)
            worker.start()
            try:
                self.assertTrue(reached.wait(3))
                duplicate = self.controller.update_turn("Worker", **self.args("KEEP_HOLDING"))
                self.assertTrue(duplicate["recovered"])
                self.assertEqual(duplicate["state"], "uncertain")
            finally:
                release.set()
                worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.store.turn_updates()), 1)
        self.assertEqual(results[0]["state"], "acknowledged")

    def test_agent_cli_and_human_http_require_same_exact_target(self):
        server = SessionServer(self.controller)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        (self.controller.directory / "controller.json").write_text(json.dumps(dict(schema=1, project=str(self.project), url=server.url, token=server.token)), encoding="utf-8")
        request(self.project, "update", dict(ident="Worker", entry="human", **self.args("KEEP_HOLDING", "human")))
        with patch.object(self.controller.provider, "call", side_effect=AssertionError("must not replay across entry paths")):
            recovered = self.controller.update_turn("Worker", **self.args("KEEP_HOLDING", "human"))
        self.assertTrue(recovered["recovered"])
        self.assertEqual(recovered["update"]["entry"], "human")
        with redirect_stdout(io.StringIO()) as output:
            code = main(["session", "--project", str(self.project), "update", "Worker", "--request", self.message["id"],
                         "--expected-turn-id", self.active["expected_turn_id"], "--key", "agent", "--body", "Use the West dock"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["state"], "acknowledged")
        self.assertEqual([row["entry"] for row in self.store.turn_updates()], ["human", "agent"])

    def test_offline_protocol_uses_utf8_under_legacy_stdio_codepage(self):
        self.controller.close()
        project = self.project / "legacy-codepage"
        project.mkdir()
        with patch.dict(os.environ, {"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp949:surrogateescape"}):
            self.controller = SessionController(project, self.command)
            self.addCleanup(self.controller.close)
            self.controller.create(name="Worker", responsibility="Legacy-codepage offline fixture")
        self.store = self.controller._store("Worker")
        self.store.update(client=dict(version=VERSION, executable_sha256=EXECUTABLE_SHA256))
        self.message = self.controller.send("Worker", key="original", body="HOLD")["message"]
        self.active = self.wait(lambda view: view["update_target"] is not None)["update_target"]
        body = "Unicode correction: \uac00\uc0c1 \uc218\uc815."
        result = self.controller.update_turn("Worker", **self.args(body))
        self.assertEqual(result["state"], "acknowledged")
        final = self.wait(lambda view: len(view["messages"]) == 2)
        self.assertEqual(final["turn_updates"][0]["body"], body)
        self.assertEqual(final["messages"][-1]["body"], "Updated same turn: " + body)
