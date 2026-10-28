"""Offline provider correlation/lifetime checks; the optional SDK is not required."""

import asyncio
import sys
import tempfile
import time
import types
import unittest
import uuid
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from awkit.claude_session import ClaudeSession, recover_local_results
from awkit.session_store import SessionStore


@dataclass
class UserMessage:
    uuid: str
    origin: dict | None
    parent_tool_use_id: str | None = None


@dataclass
class SystemMessage:
    subtype: str
    data: dict


@dataclass
class ResultMessage:
    session_id: str
    uuid: str
    origin: dict | None
    result: str = "A bounded answer."
    terminal_reason: str | None = "completed"
    is_error: bool = False
    errors: list | None = None


class ClaudeCorrelationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.store = SessionStore.create(self.project, name="Worker", project=self.project,
            responsibility="Retain invented facts", generation="connection-a", permissions={}, provider="claude")
        self.native = str(uuid.uuid4())
        self.store.update(requested_native_id=self.native, state="idle",
                          startup_context={"developer_instructions": "Read the project instructions."})
        self.worker = ClaudeSession.__new__(ClaudeSession)
        self.worker.store, self.worker.generation = self.store, "connection-a"
        self.worker._current, self.worker._echo, self.worker._ambiguous = None, False, False
        self.worker._context_input = None
        self.worker._idle_observed, self.worker._state_sequence = False, 0

    def claim(self):
        self.store.post("first", "Check an invented fact.")
        self.worker._current = self.store.claim("connection-a")
        return self.worker._current["id"]

    def init(self):
        self.worker._message(SystemMessage("init", dict(session_id=self.native, cwd=str(self.project), permissionMode="default")))

    def result(self, origin=None):
        self.worker._message(ResultMessage(self.native, str(uuid.uuid4()), origin))

    def test_requested_identity_is_not_observed_until_native_frame(self):
        ident = self.claim()
        self.assertIsNone(self.store.metadata()["native_id"])
        self.assertIsNone(self.store.snapshot()["attempts"][0]["native_id"])
        self.init()
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        self.result({"kind": "human"})
        view = self.store.snapshot()
        self.assertEqual(view["messages"][-1]["reply_to"], "M-001")
        self.assertEqual(view["attempts"][0]["native_id"], self.native)
        self.assertIsNone(view["attempts"][0]["turn_id"])

    def test_peer_result_cannot_complete_current_external_assignment(self):
        ident = self.claim()
        self.init()
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        self.worker._message(UserMessage(str(uuid.uuid4()), {"kind": "peer", "from": "sender-asserted"}))
        self.result({"kind": "peer"})
        self.assertEqual(len(self.store.snapshot()["messages"]), 1)
        self.assertIsNotNone(self.worker._current)
        self.result({"kind": "human"})
        self.assertEqual(len(self.store.snapshot()["messages"]), 2)

    def test_missing_echo_or_unknown_result_origin_never_fabricates_reply(self):
        self.claim()
        self.init()
        self.result()
        self.assertEqual(len(self.store.snapshot()["messages"]), 1)
        self.result({"kind": "human"})
        self.assertEqual(self.store.snapshot()["attempts"][0]["state"], "uncertain")
        self.assertEqual(len(self.store.snapshot()["messages"]), 1)

    def test_unexpected_human_input_invalidates_apparent_latest_result(self):
        ident = self.claim()
        self.init()
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        self.worker._message(UserMessage(str(uuid.uuid4()), {"kind": "human"}))
        self.result({"kind": "human"})
        self.assertEqual(len(self.store.snapshot()["messages"]), 1)
        self.assertEqual(self.store.snapshot()["attempts"][0]["state"], "uncertain")

    def test_wrong_native_identity_remains_unbound(self):
        self.claim()
        with self.assertRaisesRegex(RuntimeError, "different native"):
            self.worker._message(ResultMessage(str(uuid.uuid4()), "result", {"kind": "human"}))
        self.assertIsNone(self.store.metadata()["native_id"])

    def test_recorded_correlated_result_recovers_original_reply_once(self):
        ident = self.claim()
        self.init()
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        result = dict(session_id=self.native, uuid="native-result", origin={"kind": "human"},
                      matched_input=ident, result="Recovered bounded answer.", is_error=False)
        self.store.event("connection-a", "claude/result", result)
        self.assertEqual(len(self.store.snapshot()["messages"]), 1)
        recover_local_results(self.store)
        recover_local_results(self.store)
        view = self.store.snapshot()
        self.assertEqual(len(view["messages"]), 2)
        self.assertEqual(view["messages"][-1]["reply_to"], "M-001")
        self.assertEqual(view["attempts"][0]["provider_result_id"], "native-result")

    def test_result_waits_for_native_idle_before_dispatching_next_assignment(self):
        ident = self.claim()
        self.init()
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        self.result({"kind": "human"})
        self.store.post("next", "A separate next assignment.")
        self.assertEqual(self.store.metadata()["state"], "waiting for idle")
        self.assertIsNone(self.store.claim("connection-a"))
        self.worker._message(SystemMessage("session_state_changed", {"state": "idle"}))
        self.assertIsNotNone(self.store.claim("connection-a"))

    def test_idle_before_result_does_not_release_current_delivery_early(self):
        ident = self.claim()
        self.init()
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        self.worker._message(SystemMessage("session_state_changed", {"state": "idle"}))
        self.assertEqual(len(self.store.snapshot()["messages"]), 1)
        self.assertEqual(self.store.metadata()["state"], "running")
        self.result({"kind": "human"})
        self.assertEqual(self.store.metadata()["state"], "idle")

    def test_stale_idle_before_input_echo_cannot_release_the_next_assignment(self):
        ident = self.claim()
        self.init()
        self.worker._message(SystemMessage("session_state_changed", {"state": "idle"}))
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        self.result({"kind": "human"})
        self.assertEqual(self.store.metadata()["state"], "waiting for idle")

    def test_idle_does_not_hide_uncertain_correlation_or_disable_explicit_recovery(self):
        self.claim()
        self.init()
        self.result({"kind": "human"})
        self.worker._message(SystemMessage("session_state_changed", {"state": "idle"}))
        self.assertEqual(self.store.metadata()["state"], "unknown")
        self.assertEqual(self.store.snapshot()["attempts"][0]["state"], "uncertain")

    def test_native_turn_limit_is_retained_separately_from_completed_outcome(self):
        ident = self.claim()
        self.init()
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        self.worker._message(ResultMessage(self.native, "limited-result", {"kind": "human"}, terminal_reason="max_turns"))
        attempt = self.store.snapshot()["attempts"][0]
        self.assertEqual(attempt["outcome"], "max_turns")
        self.assertEqual(self.store.metadata()["state"], "waiting for idle")

    def test_callback_response_is_not_native_resolution_until_parent_result(self):
        ident = self.claim()
        self.init()
        self.worker._message(UserMessage(ident, {"kind": "human"}))
        callback = self.store.add_decision("connection-a", "sdk-callback", "claude/permission",
                                           {"provider_input_id": ident, "tool_use_id": "tool"}, ["allow", "deny"])
        self.store.answer_intent("connection-a", callback, "allow")
        self.assertEqual(self.store.snapshot()["decisions"][0]["state"], "sending")
        self.result({"kind": "human"})
        decision = self.store.snapshot()["decisions"][0]
        self.assertEqual(decision["state"], "resolved")
        self.assertIn("correlated native parent result", decision["params"]["resolution_source"])


class FakeClient:
    instances = []

    def __init__(self, options):
        self.options, self.queries = options, []
        self.__class__.instances.append(self)

    async def connect(self):
        self.owner = asyncio.current_task()
        self.queue = asyncio.Queue()

    async def get_server_info(self):
        return dict(current_permission_mode="default", session_state="idle", account={"private": "discard"})

    async def query(self, frames):
        async for frame in frames:
            self.queries.append(frame)
            native = self.options.session_id or self.options.resume
            await self.queue.put(SystemMessage("init", dict(session_id=native, cwd=self.options.cwd, permissionMode="default", model="claude-canonical-fixture")))
            await self.queue.put(SystemMessage("session_state_changed", {"state": "running"}))
            await self.queue.put(UserMessage(frame["uuid"], frame["origin"]))
            await self.queue.put(ResultMessage(native, str(uuid.uuid4()), frame["origin"], frame["message"]["content"]))
            await self.queue.put(SystemMessage("session_state_changed", {"state": "idle"}))

    async def receive_messages(self):
        while True:
            yield await self.queue.get()

    async def disconnect(self):
        self.disconnected_by_owner = self.owner is asyncio.current_task()


class ClaudeLifetimeTests(unittest.TestCase):
    def setUp(self):
        ClaudeCorrelationTests.setUp(self)
        module = types.ModuleType("claude_agent_sdk")
        module.ClaudeAgentOptions = lambda **kwargs: types.SimpleNamespace(**kwargs)
        module.ClaudeSDKClient = FakeClient
        module.get_session_info = lambda ident, directory: types.SimpleNamespace(session_id=ident)
        module.get_session_messages = lambda ident, directory, limit: []
        module.PermissionResultAllow = lambda **kwargs: dict(behavior="allow", **kwargs)
        module.PermissionResultDeny = lambda **kwargs: dict(behavior="deny", **kwargs)
        self.module = module
        FakeClient.instances.clear()
        self.patcher = patch.dict(sys.modules, {"claude_agent_sdk": module})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        binary = patch("awkit.claude_session.executable", return_value=(Path(sys.executable), "fixture-hash"))
        binary.start()
        self.addCleanup(binary.stop)
        version = patch("awkit.claude_session.availability", return_value={"available": True})
        version.start()
        self.addCleanup(version.stop)

    def test_two_queries_keep_one_client_and_disconnect_in_owning_context(self):
        client = ClaudeSession(self.store)
        try:
            for index in range(2):
                self.store.post(f"request{index}", f"invented fact {index}")
                client.submit(self.store.claim(client.generation))
                deadline = time.monotonic() + 3
                while len(self.store.snapshot()["messages"]) < (index + 1) * 2 and time.monotonic() < deadline:
                    time.sleep(0.01)
            self.assertEqual(len(FakeClient.instances), 1)
            self.assertEqual(len(FakeClient.instances[0].queries), 2)
            self.assertEqual(len(self.store.snapshot()["messages"]), 4)
            self.assertNotIn("account", self.store.metadata()["client"])
            self.assertNotIn("allowed_tools", vars(FakeClient.instances[0].options))
            self.assertFalse(set(vars(FakeClient.instances[0].options)) & {"model", "effort", "fallback_model"})
        finally:
            client.close()
        self.assertTrue(FakeClient.instances[0].disconnected_by_owner)
        self.assertFalse(client.alive)

    def test_explicit_alias_effort_are_submitted_and_reapplied_without_false_matching(self):
        selection = dict(requested="sonnet", requested_effort="xhigh", creation=None, latest=None, state="requested")
        self.store.update(model_selection=selection)
        client = ClaudeSession(self.store)
        try:
            options = FakeClient.instances[-1].options
            self.assertEqual((options.model, options.effort), ("sonnet", "xhigh"))
            self.assertNotIn("fallback_model", vars(options))
            self.assertEqual(self.store.metadata()["model_selection"]["state"], "submitted")
            self.assertIsNone(self.store.metadata()["model_selection"]["latest"])
            self.store.post("alias-input", "Invented alias input")
            client.submit(self.store.claim(client.generation))
            deadline = time.monotonic() + 3
            while len(self.store.snapshot()["messages"]) < 2 and time.monotonic() < deadline:
                time.sleep(.01)
            observed = self.store.metadata()["model_selection"]
            self.assertEqual(observed["requested"], "sonnet")
            self.assertEqual(observed["requested_effort"], "xhigh")
            self.assertEqual(observed["latest"]["model"], "claude-canonical-fixture")
            self.assertIsNone(observed["latest"]["reasoning_effort"])
            self.assertEqual(observed["state"], "submitted")
            self.assertEqual(len(self.store.snapshot()["messages"]), 2)
        finally:
            client.close()
        self.store.reconnect("connection-b")
        self.store.update(generation="connection-b")
        resumed = ClaudeSession(self.store, resume=True)
        self.addCleanup(resumed.close)
        options = FakeClient.instances[-1].options
        self.assertEqual(options.resume, self.native)
        self.assertIsNone(options.session_id)
        self.assertEqual((options.model, options.effort), ("sonnet", "xhigh"))
        self.assertEqual(FakeClient.instances[-1].queries, [])
        self.assertEqual(self.store.metadata()["model_selection"]["creation"], observed["creation"])

    def test_model_only_request_omits_effort_and_initialization_failure_never_falls_back(self):
        self.store.update(model_selection=dict(requested="sonnet", creation=None, latest=None, state="requested"))

        async def reject(_client):
            _client.owner = asyncio.current_task()
            raise RuntimeError("Fictional unavailable model")

        with patch.object(FakeClient, "connect", reject), self.assertRaisesRegex(RuntimeError, "Fictional unavailable"):
            ClaudeSession(self.store)
        self.assertEqual(len(FakeClient.instances), 1)
        options = vars(FakeClient.instances[0].options)
        self.assertEqual(options["model"], "sonnet")
        self.assertFalse(set(options) & {"effort", "fallback_model"})
        self.assertEqual(self.store.metadata()["model_selection"]["requested"], "sonnet")
        self.assertEqual(self.store.metadata()["state"], "unknown")
        self.assertEqual(FakeClient.instances[0].queries, [])

    def wait_for_decision(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            rows = [row for row in self.store.snapshot()["decisions"] if row["state"] == "pending"]
            if rows:
                return rows[-1]
            time.sleep(0.01)
        self.fail("No original permission callback was observed")

    def test_cancelled_callback_cannot_receive_old_answer_even_with_reused_tool_id(self):
        client = ClaudeSession(self.store)
        self.addCleanup(client.close)
        context = types.SimpleNamespace(tool_use_id="same-tool-id")
        first = asyncio.run_coroutine_threadsafe(client._permission("Read", {"path": "invented.txt"}, context), client._loop)
        old = self.wait_for_decision()
        self.assertEqual(old["choices"], ["allow", "deny"])
        first.cancel()
        deadline = time.monotonic() + 3
        old_row = old
        while time.monotonic() < deadline:
            old_row = next(row for row in self.store.snapshot()["decisions"] if row["id"] == old["id"])
            if old_row["state"] == "route unavailable":
                break
            time.sleep(0.01)
        self.assertEqual(old_row["state"], "route unavailable")
        second = asyncio.run_coroutine_threadsafe(client._permission("Read", {"path": "another.txt"}, context), client._loop)
        new = self.wait_for_decision()
        self.assertNotEqual(new["id"], old["id"])
        with self.assertRaisesRegex(ValueError, "no longer pending"):
            client.decide(old["id"], "allow")
        client.decide(new["id"], "deny")
        self.assertEqual(second.result(timeout=3)["behavior"], "deny")
        rows = self.store.snapshot()["decisions"]
        self.assertEqual(rows[0]["state"], "route unavailable")
        self.assertEqual(rows[1]["state"], "sending")

    def test_question_answers_preserve_original_input_and_need_exact_question_text(self):
        client = ClaudeSession(self.store)
        self.addCleanup(client.close)
        context = types.SimpleNamespace(tool_use_id="question-tool")
        questions = {"questions": [{"question": "Which invented dock?", "header": "Dock", "options": []}]}
        callback = asyncio.run_coroutine_threadsafe(client._permission("AskUserQuestion", questions, context), client._loop)
        decision = self.wait_for_decision()
        with self.assertRaisesRegex(ValueError, "every original question"):
            client.decide(decision["id"], {"answers": {"different question": "North"}})
        client.decide(decision["id"], {"answers": {"Which invented dock?": "North"}})
        result = callback.result(timeout=3)
        self.assertEqual(result["updated_input"]["questions"], questions["questions"])
        self.assertEqual(result["updated_input"]["answers"], {"Which invented dock?": "North"})
        self.assertNotIn("updated_permissions", result)

    def test_exact_resume_keeps_uncertain_assignment_unreplayed(self):
        self.store.update(native_id=self.native)
        self.store.post("old", "An uncertain request.")
        attempt = self.store.claim("connection-a")
        self.store.reconnect("connection-b")
        self.store.update(generation="connection-b")
        self.module.get_session_messages = lambda ident, directory, limit: [types.SimpleNamespace(uuid=attempt["id"])]
        client = ClaudeSession(self.store, resume=True)
        self.addCleanup(client.close)
        native = FakeClient.instances[-1]
        self.assertEqual(native.options.resume, self.native)
        self.assertIsNone(native.options.session_id)
        self.assertEqual(native.options.cwd, str(self.project.resolve()))
        self.assertEqual(native.queries, [])
        view = self.store.snapshot()
        self.assertEqual(view["attempts"][0]["id"], attempt["id"])
        self.assertEqual(view["attempts"][0]["state"], "unresolved")
        self.assertIsNone(view["attempts"][0]["reply_id"])
        self.assertEqual(view["session"]["recovery_evidence"]["inputs"], [
            {"provider_input_id": attempt["id"], "visible_occurrences": 1}])

    def test_sdk_admission_error_uses_controller_error_boundary(self):
        class FakeSDKFailure(Exception):
            pass

        async def fail_query(_client, _frames):
            raise FakeSDKFailure("injected native write failure")

        client = ClaudeSession(self.store)
        self.addCleanup(client.close)
        self.store.post("failed-write", "A bounded request.")
        with patch.object(FakeClient, "query", fail_query), self.assertRaisesRegex(RuntimeError, "FakeSDKFailure"):
            client.submit(self.store.claim(client.generation))
