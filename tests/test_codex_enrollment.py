"""Offline enrollment contract; native writer admission needs a separate live observation."""

import copy
import io
import json
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from awkit.cli import main
from awkit.codex_enrollment import policy, runtime
from awkit.codex_session import ProviderError
from awkit.session_http import SessionServer, request
from awkit.session_store import SessionStore
from awkit.sessions import SessionController


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        self.home = self.project / "native-home"
        self.home.mkdir()
        (self.home / "sessions").mkdir()
        (self.home / "sessions" / "selected.jsonl").write_text("owned fixture", encoding="utf-8")
        self.native_id = str(uuid.uuid4())
        self.calls, self.clients, self.turns = [], [], []
        self.fault, self.lose_response = None, False
        self.scope = dict(cwd=str(self.project), approvalPolicy="on-request", approvalsReviewer="auto_review",
            sandbox=dict(type="workspaceWrite", networkAccess=False, writableRoots=[],
                         excludeTmpdirEnvVar=False, excludeSlashTmp=False),
            runtimeWorkspaceRoots=[], activePermissionProfile=dict(id=":workspace", extends=None))
        self.thread = dict(id=self.native_id, cwd=str(self.project), status=dict(type="idle"),
            canAcceptDirectInput=True, ephemeral=False, path=str(self.home / "sessions" / "selected.jsonl"))
        self.inspected = dict(executable="verified-fixture", executable_sha256="fixture",
                              version="fixture", codex_home=str(self.home))
        self.patcher = patch("awkit.codex_enrollment.runtime", return_value=self.inspected)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.start()

    def factory(self, command, project, callback, **kwargs):
        self.assertEqual(kwargs, dict(experimental=True))
        outer = self

        class Client:
            alive = True
            initialization = dict(codexHome=str(outer.home))
            process = SimpleNamespace(pid=12345)

            def call(self, method, params, on_request=None):
                outer.calls.append((method, copy.deepcopy(params)))
                if method == "thread/resume":
                    if outer.fault:
                        raise ProviderError(outer.fault)
                    return dict(copy.deepcopy(outer.scope), thread=copy.deepcopy(outer.thread))
                if method == "thread/read":
                    return dict(thread=copy.deepcopy(outer.thread))
                if method == "thread/turns/list":
                    return dict(data=copy.deepcopy(outer.turns), nextCursor=None)
                if method == "turn/start":
                    on_request("fixture-rpc")
                    turn = dict(id=str(uuid.uuid4()), status="completed", clientUserMessageId=params["clientUserMessageId"],
                                items=[dict(type="userMessage", clientId=params["clientUserMessageId"], content=params["input"]),
                                       dict(type="agentMessage", text="Kept the original context.")])
                    outer.turns.append(turn)
                    if outer.lose_response:
                        raise ProviderError("turn/start response lost; delivery uncertain")
                    callback(dict(method="turn/completed", params=dict(threadId=outer.native_id, turn=turn)))
                    return dict(turn=turn)
                raise AssertionError(method)

            def close(self):
                self.alive = False

        client = Client()
        self.clients.append(client)
        return client

    def start(self):
        self.controller = SessionController(self.project, ["verified-fixture"], provider_factory=self.factory)
        self.addCleanup(self.controller.close)

    def wait(self, predicate):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            view = self.controller.status()["sessions"][0]
            if predicate(view):
                return view
            time.sleep(.02)
        self.fail(str(view))

    def enroll(self):
        return self.controller.enroll(name="Research", thread_id=self.native_id)

    def test_enroll_and_restart_retain_identity_scope_without_new_instructions_or_history(self):
        before = self.enroll()
        self.assertEqual(before["extension_schema"], 4)
        self.assertEqual(before["messages"], [])
        self.assertIsNone(before["session"]["startup_context"])
        self.assertEqual(before["session"]["enrollment"]["policy"], self.scope)
        self.assertEqual([m for m, _ in self.calls], ["thread/resume", "thread/read"])
        self.controller.send("Research", key="first", body="Use the retained context.")
        self.wait(lambda v: len(v["messages"]) == 2)
        self.controller.close()
        self.start()
        after = self.wait(lambda v: v["can_send"])
        self.assertEqual(after["session"]["native_id"], self.native_id)
        self.assertEqual(len(after["attempts"]), 1)
        self.assertEqual(sum(m == "turn/start" for m, _ in self.calls), 1)
        for method, params in self.calls:
            if method == "thread/resume":
                self.assertEqual(params, dict(threadId=self.native_id, excludeTurns=True))
        self.assertFalse(any(m in ("thread/start", "thread/fork", "thread/list") for m, _ in self.calls))

    def test_null_profile_is_retained_without_invention_and_sends_no_assignment(self):
        self.scope["activePermissionProfile"] = None
        view = self.enroll()
        self.assertEqual(view["session"]["state"], "idle")
        self.assertEqual(view["session"]["native_id"], self.native_id)
        self.assertEqual(view["messages"], [])
        self.assertEqual(view["attempts"], [])
        self.assertEqual(view["session"]["admission_observation"]["scope"]["activePermissionProfile"], None)
        self.assertIsNone(view["session"]["enrollment"]["policy"]["activePermissionProfile"])

    def test_absent_optional_provenance_is_preserved_and_differs_from_null(self):
        self.scope.pop("activePermissionProfile")
        self.scope.pop("runtimeWorkspaceRoots")
        view = self.enroll()
        self.assertEqual(view["session"]["state"], "idle")
        saved = view["session"]["enrollment"]["policy"]
        self.assertNotIn("activePermissionProfile", saved)
        self.assertNotIn("runtimeWorkspaceRoots", saved)
        self.assertIn("activePermissionProfile", view["session"]["admission_observation"]["unexposed_fields"])
        self.scope["activePermissionProfile"] = None
        self.controller.send("Research", key="changed-exposure", body="Must stay queued")
        held = self.wait(lambda v: v["session"]["state"] == "unknown")
        self.assertEqual(held["attempts"], [])
        self.assertIsNone(held["session"]["returned_scope"]["activePermissionProfile"])

    def test_named_profile_provenance_is_retained_without_builtin_inference(self):
        self.scope["activePermissionProfile"] = dict(id="configured-profile", extends="parent-profile")
        view = self.enroll()
        self.assertEqual(view["session"]["state"], "idle")
        self.assertEqual(view["session"]["enrollment"]["policy"], self.scope)

    def test_duplicate_identity_name_conflicts_and_cross_project_controller_are_refused(self):
        original = self.enroll()
        self.assertEqual(self.enroll()["session"]["id"], original["session"]["id"])
        with self.assertRaises(ValueError):
            self.controller.enroll(name="Other", thread_id=self.native_id)
        with self.assertRaises(ValueError):
            self.controller.enroll(name="Research", thread_id=str(uuid.uuid4()))
        with self.assertRaises(ValueError):
            SessionController(self.project, ["verified-fixture"], provider_factory=self.factory)
        self.assertEqual(len(self.clients), 1)

    def test_different_native_home_is_refused_without_resume(self):
        original_factory = self.factory
        def factory(*args, **kwargs):
            client = original_factory(*args, **kwargs)
            client.initialization = dict(codexHome=str(self.project))
            return client
        self.controller.provider_factory = factory
        view = self.enroll()
        self.assertEqual(view["session"]["state"], "unknown")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.clients[-1].alive)

    def test_conflicting_restored_registration_refuses_and_closes_owned_connection(self):
        self.enroll()
        conflicting = SessionStore.create(self.controller.directory / "channels", name="Conflicting", project=self.project,
            responsibility="Duplicate fixture", generation=self.controller.generation, permissions={},
            enrollment=dict(thread_id=self.native_id))
        self.controller._stores[conflicting.metadata()["id"]] = conflicting
        self.controller._recovery_attempted.add(conflicting.metadata()["id"])
        prior_calls = len(self.calls)
        self.controller._resume_enrolled(self.controller._store("Research"))
        self.assertEqual(len(self.calls), prior_calls)
        self.assertFalse(self.clients[-1].alive)
        self.assertEqual(self.controller._store("Research").metadata()["state"], "unknown")

    @unittest.skipUnless(__import__("os").name == "nt", "native Windows extended path spelling")
    def test_extended_drive_path_is_same_owned_local_store(self):
        result = dict(copy.deepcopy(self.scope), thread=copy.deepcopy(self.thread))
        result["thread"]["path"] = "\\\\?\\" + result["thread"]["path"]
        self.assertEqual(policy(result, self.project, self.native_id, self.home), self.scope)

    def test_unknown_delivery_recovers_one_original_reply_without_replay(self):
        self.enroll()
        self.lose_response = True
        original = self.controller.send("Research", key="lost", body="A single original assignment")["message"]
        self.wait(lambda v: v["attempts"] and v["attempts"][0]["state"] == "uncertain")
        self.controller.close()
        self.start()
        recovered = self.wait(lambda v: len(v["messages"]) == 2)
        self.assertEqual(recovered["messages"][-1]["reply_to"], original["id"])
        self.assertEqual(sum(m == "turn/start" for m, _ in self.calls), 1)

    def test_unresolved_without_native_evidence_remains_unresolved(self):
        self.enroll()
        self.lose_response = True
        self.controller.send("Research", key="lost", body="Uncertain")
        self.wait(lambda v: v["attempts"] and v["attempts"][0]["state"] == "uncertain")
        self.turns.clear()
        self.controller.close()
        self.start()
        view = self.wait(lambda v: v["can_send"])
        self.assertEqual(view["attempts"][0]["state"], "unresolved")
        self.assertEqual(len(view["messages"]), 1)
        self.assertEqual(sum(m == "turn/start" for m, _ in self.calls), 1)

    def test_native_owner_conflict_refuses_without_replacement_or_task(self):
        self.fault = "native writer conflict"
        view = self.enroll()
        self.assertEqual(view["session"]["state"], "unknown")
        self.assertFalse(self.clients[-1].alive)
        self.assertEqual(self.calls, [("thread/resume", dict(threadId=self.native_id, excludeTurns=True))])
        self.assertEqual(view["attempts"], [])
        self.fault = None
        resumed = self.controller.resume("Research")
        self.assertEqual(resumed["session"]["native_id"], self.native_id)

    def test_changed_policy_holds_assignment_and_preserves_both_scopes(self):
        self.enroll()
        original = copy.deepcopy(self.scope)
        self.scope["sandbox"]["networkAccess"] = True
        self.controller.send("Research", key="held", body="Must stay queued")
        held = self.wait(lambda v: v["session"]["state"] == "unknown")
        self.assertEqual(held["attempts"], [])
        self.assertEqual(held["session"]["enrollment"]["policy"], original)
        self.assertEqual(held["session"]["returned_scope"], self.scope)
        self.assertFalse(self.clients[-1].alive)

    def test_policy_refuses_identity_project_activity_child_and_unknown_scope(self):
        cases = [lambda r: r["thread"].update(id=str(uuid.uuid4())),
                 lambda r: r.update(cwd=str(self.project.parent)),
                 lambda r: r["thread"].update(cwd=str(self.project.parent)),
                 lambda r: r["thread"].update(status=dict(type="active")),
                 lambda r: r["thread"].update(status="unknown-shape"),
                 lambda r: r["thread"].update(canAcceptDirectInput=False),
                 lambda r: r["thread"].update(canAcceptDirectInput=None),
                 lambda r: r["thread"].update(path=str(self.project / "elsewhere.jsonl")),
                 lambda r: r["sandbox"].update(unknownPermission=True),
                 lambda r: r.pop("sandbox"),
                 lambda r: r.pop("approvalPolicy"),
                 lambda r: r.pop("approvalsReviewer"),
                 lambda r: r.update(activePermissionProfile=dict(id=123))]
        for mutate in cases:
            with self.subTest(mutate=cases.index(mutate)):
                result = dict(copy.deepcopy(self.scope), thread=copy.deepcopy(self.thread))
                mutate(result)
                with self.assertRaises((ValueError, KeyError, OSError)):
                    policy(result, self.project, self.native_id, self.home)

    def test_runtime_home_change_refuses_before_new_connection(self):
        self.enroll()
        self.controller.close()
        self.inspected["codex_home"] = str(self.project / "different-home")
        self.start()
        view = self.wait(lambda v: v["session"]["state"] == "unknown")
        self.assertIn("runtime/home changed", view["session"]["error"])
        self.assertEqual(len(self.clients), 1)

    def test_cli_and_human_endpoint_share_exact_selection(self):
        from awkit.cli import _parser

        args = _parser().parse_args(["session", "enroll", "Research", "--thread-id", self.native_id])
        self.assertEqual(args.thread_id, self.native_id)
        server = SessionServer(self.controller)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = dict(schema=1, project=str(self.project), url=server.url, token=server.token)
            (self.controller.directory / "controller.json").write_text(json.dumps(endpoint), encoding="utf-8")
            view = request(self.project, "enroll", dict(name="Research", thread_id=self.native_id))
            self.assertEqual(view["session"]["native_id"], self.native_id)
            self.assertEqual(view["messages"], [])
            request(self.project, "send", dict(ident="Research", key="human", body="Preserve context", entry="human"))
            sent = self.wait(lambda v: len(v["messages"]) == 2)
            self.assertEqual(sent["posts"][0]["entry"], "human")
            with patch("awkit.session_http.request", return_value=dict(session=dict(state="unknown"))):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["session", "enroll", "Refused", "--thread-id", str(uuid.uuid4())]), 1)
        finally:
            server.shutdown()
            server.server_close()

    def test_wrapped_or_unsupported_runtime_refuses_before_process(self):
        with patch("awkit.codex_enrollment.subprocess.run") as run:
            with self.assertRaises(ValueError):
                runtime(["codex", "--config", "unsafe=true"])
            executable = self.project / "unsupported.exe"
            executable.write_bytes(b"unsupported")
            with self.assertRaises(ValueError):
                runtime([str(executable)])
            run.assert_not_called()
