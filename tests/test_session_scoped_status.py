"""Scoped retained reads with fictional provider records and no controller startup."""

import io
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from awkit.channel import REQUESTS
from awkit.cli import main
from awkit.session_history import HistoryViews
from awkit.session_http import SessionServer, request
from awkit.session_reading import SelectorError, decision_request, exact_request
from awkit.session_store import SessionStore
from awkit.sessions import SessionController


class ScopedStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        # The owner already exists. Queries may only read these retained facts.
        self.owner = object.__new__(SessionController)
        self.owner.project = self.root
        self.owner.generation = "generation"
        self.owner._mutex = threading.RLock()
        self.owner._stores = {}
        self.owner.history = HistoryViews(self.root, self.root / "views")
        self.owner.provider = SimpleNamespace(alive=True)
        self.owner.claude_clients = {}
        self.owner.enrolled_clients = {}
        self.owner.command = ["fictional-unavailable-executable"]
        self.owner.record = None
        self.owner.provider_error = "UNRELATED_PROVIDER_ERROR"
        self.owner.errors = ["UNRELATED_DIAGNOSTIC_BODY"]
        self.codex = self.store("Codex", "codex")
        self.claude = self.store("Claude", "claude")

    def store(self, name, provider):
        store = SessionStore.create(self.root / "channels", name=name, project=self.root, provider=provider,
                                    responsibility="UNRELATED_ROLE_TEXT", generation="generation", permissions={})
        store.update(native_id="native-" + provider, state="idle", error="UNRELATED_SESSION_ERROR",
                     startup_context={"developer_instructions": "UNRELATED_STARTUP_BODY"})
        ident = store.metadata()["id"]
        self.owner._stores[ident] = store
        if provider == "claude":
            self.owner.claude_clients[ident] = SimpleNamespace(alive=True, generation="generation")
        return store

    def scoped(self, store, ident):
        return self.owner.status(session=store.metadata()["name"], request=ident)["sessions"][0]

    def active(self, store, key="work"):
        message = store.post(key, "SELECTED_INPUT")
        claim = store.claim("generation")
        if store.metadata()["provider"] == "claude":
            store.claude_echo("generation", claim["id"], store.metadata()["native_id"])
        else:
            store.bind_turn("generation", "turn-" + key, executing=True)
        return message, store.snapshot()["attempts"][-1]

    def finish(self, store, attempt, outcome="completed", text="SELECTED_REPLY"):
        if store.metadata()["provider"] == "claude":
            store.claude_finish("generation", attempt["provider_input_id"], str(uuid.uuid4()), outcome, text)
        else:
            store.finish("generation", attempt["turn_id"], outcome, text)

    def test_session_name_id_and_default_views_preserve_payload_without_other_snapshots(self):
        for selected, other in ((self.codex, self.claude), (self.claude, self.codex)):
            with self.subTest(provider=selected.metadata()["provider"]):
                default = self.owner.status()
                expected = next(row for row in default["sessions"] if row["session"]["id"] == selected.metadata()["id"])
                with mock.patch.object(other, "snapshot", side_effect=AssertionError("unrelated snapshot")):
                    named = self.owner.status(session=selected.metadata()["name"])
                    identified = self.owner.status(session=selected.metadata()["id"])
                self.assertEqual(named, identified)
                self.assertEqual(named["sessions"], [expected])
                self.assertEqual(named["selection"], {"session_id": selected.metadata()["id"]})
                self.assertNotIn("diagnostics", named)
        self.assertNotIn("selection", self.owner.status())
        self.assertEqual(len(self.owner.status()["sessions"]), 2)

    def test_selection_errors_do_not_fall_back_to_unfiltered_data(self):
        aliases = dict(id="history-only", parties=dict(main="History main", reviewer="History reader"))
        with mock.patch.object(self.owner.history, "registrations", return_value=[aliases]):
            for args, text in ((dict(session="history-only"), "History-only"),
                               (dict(session="native-codex"), "native conversation"),
                               (dict(session="missing"), "No unique"),
                               (dict(session=""), "nonempty"),
                               (dict(session=" Codex"), "nonempty"),
                               (dict(request="M-001"), "requires"),
                               (dict(session="Codex", request="bad"), "exact stored"),
                               (dict(session="Codex", request="M-999"), "no input")):
                with self.subTest(args=args), self.assertRaisesRegex(SelectorError, text):
                    self.owner.status(**args)

    def test_all_request_kinds_and_reverse_notice_reply_targets(self):
        for provider in (self.codex, self.claude):
            for kind in REQUESTS:
                message = provider.post(kind, "SELECTED_" + kind, kind=kind)
                self.assertEqual(self.scoped(provider, message["id"])["request"], message)
            wrong = [provider.channel.post("reviewer", "main", "question", "reverse"),
                     provider.channel.post("main", "reviewer", "notice", "notice")]
            reply = provider.channel.post("reviewer", "main", "re", "not original", reply_to="M-001")
            wrong.append(reply)
            for ident in wrong:
                with self.subTest(ident=ident), self.assertRaisesRegex(SelectorError, "original main-to-reviewer"):
                    self.scoped(provider, ident)

    def test_exact_request_is_resolved_only_inside_the_selected_channel(self):
        self.codex.post("first", "UNRELATED_CODEX_INPUT")
        self.codex.post("second", "UNRELATED_CODEX_SECOND")
        self.claude.post("only", "SELECTED_CLAUDE_INPUT")
        with self.assertRaisesRegex(SelectorError, "no input"):
            self.scoped(self.claude, "M-002")

    def test_exact_envelope_excludes_other_request_role_error_event_and_declaration_bodies(self):
        for store in (self.codex, self.claude):
            selected = store.post("selected", "SELECTED_INPUT")
            other = store.post("other", "UNRELATED_OTHER_REQUEST")
            store.channel.post("reviewer", "main", "re", "UNRELATED_OTHER_REPLY", reply_to=other["id"])
            store.event("generation", "fixture/raw", {"body": "UNRELATED_RAW_EVENT"})
            self.owner.record = self.root / "record.json"
            self.owner.record.write_text(json.dumps(dict(schema=1, session="planner", relationships=[dict(
                id="selected", channel=str(store.path), local_role="main", counterpart=store.metadata()["native_id"],
                task="UNRELATED_RELATIONSHIP_TASK")], obligations=[dict(id="other", source=dict(relationship="selected", message=other["id"]),
                    responsible_session="planner", action="UNRELATED_DECLARATION_BODY", state="pending")])), encoding="utf-8")
            encoded = json.dumps(self.owner.status(session=store.metadata()["name"], request=selected["id"]))
            self.assertIn("SELECTED_INPUT", encoded)
            self.assertNotIn("UNRELATED_", encoded)
            value = json.loads(encoded)["sessions"][0]
            self.assertNotIn("events", value)
            self.assertEqual(len(value["messages"]), 1)

    def test_reply_descendants_use_explicit_edges_and_do_not_absorb_independent_requests(self):
        selected = self.codex.post("one", "SELECTED_INPUT")
        # Separate counters deliberately make the returned ID differ from the input suffix.
        self.codex.channel.post("reviewer", "main", "notice", "UNRELATED_NOTICE")
        reply = self.codex.channel.post("reviewer", "main", "re", "SELECTED_REPLY", reply_to=selected["id"])
        rebut = self.codex.channel.post("main", "reviewer", "rebut", "SELECTED_REBUT", reply_to=reply)
        follow = self.codex.channel.post("reviewer", "main", "re", "SELECTED_FOLLOWUP", reply_to=rebut)
        other = self.codex.post("independent", "UNRELATED_INDEPENDENT")
        # A malformed request edge must still never extend the reply-only tree.
        with self.codex.channel.transaction() as conn:
            conn.execute("UPDATE messages SET reply_to=? WHERE id=?", (follow, other["id"]))
        view = self.scoped(self.codex, selected["id"])
        self.assertEqual([row["id"] for row in view["messages"]], [selected["id"], reply, rebut, follow])
        self.assertEqual(view["reply_evidence"], dict(provider_reply_id=None, direct_ids=[reply], descendant_ids=[rebut, follow]))
        self.assertNotIn("UNRELATED_", json.dumps(view))

    def test_failed_capacity_report_and_cancelled_inputs_remain_separate(self):
        selected, attempt = self.active(self.codex)
        self.codex.event("generation", "item/completed", dict(threadId="native-codex", turnId=attempt["turn_id"],
                         item=dict(type="agentMessage", phase="commentary", text="Reported a push; delivery unverified")))
        self.finish(self.codex, attempt, "failed", "")
        second = self.codex.post("next", "UNRELATED_NEXT")
        third = self.codex.post("later", "UNRELATED_LATER")
        self.codex.cancel(second["id"])
        self.codex.cancel(third["id"])
        failed = self.scoped(self.codex, selected["id"])
        self.assertEqual((failed["dispositions"][0]["dispatch_state"], failed["attempts"][0]["outcome"]), ("failed", "failed"))
        self.assertIsNone(failed["reply_evidence"]["provider_reply_id"])
        self.assertIn("Reported a push", failed["attempts"][0]["public_update"]["text"])
        self.assertNotIn("UNRELATED_", json.dumps(failed))
        for message in (second, third):
            view = self.scoped(self.codex, message["id"])
            self.assertEqual(view["dispositions"][0]["dispatch_state"], "cancelled")
            self.assertFalse(view["attempts"])
            self.assertNotIn("Reported a push", json.dumps(view))

    def test_lifecycle_and_after_dispatch_stop_are_not_rewritten_by_session_activity_or_replies(self):
        for store in (self.codex, self.claude):
            selected, attempt = self.active(store)
            queued = store.post("queued", "QUEUED_INPUT")
            self.assertEqual(self.scoped(store, queued["id"])["dispositions"][0]["dispatch_state"], "queued")
            store.cancel(selected["id"])
            stopped = self.scoped(store, selected["id"])
            self.assertNotEqual(stopped["dispositions"][0]["dispatch_state"], "cancelled")
            self.assertEqual(stopped["cancellations"][0]["disposition"], "after-dispatch")
            self.finish(store, attempt, "failed", "SELECTED_FAILURE_REPLY")
            final = self.scoped(store, selected["id"])
            self.assertEqual((final["attempts"][0]["state"], final["attempts"][0]["outcome"]), ("returned", "failed"))
            self.assertIsNotNone(final["reply_evidence"]["provider_reply_id"])
            self.assertEqual(final["coverage"]["semantic_acceptance"], "unverified")
            self.assertFalse(final["update_target"])

    def test_completed_without_text_and_separate_direct_reply_preserve_native_facts(self):
        for store in (self.codex, self.claude):
            selected, attempt = self.active(store)
            self.finish(store, attempt, "completed", "")
            store.channel.post("reviewer", "main", "re", "SELECTED_DIRECT_REPLY", reply_to=selected["id"])
            view = self.scoped(store, selected["id"])
            self.assertEqual((view["attempts"][0]["state"], view["attempts"][0]["outcome"]), ("no-reply", "completed"))
            self.assertIsNone(view["reply_evidence"]["provider_reply_id"])
            self.assertTrue(view["reply_evidence"]["direct_ids"])

    def test_admission_acknowledgement_and_recovered_origin_generation(self):
        selected = self.codex.post("one", "SELECTED_INPUT")
        claim = self.codex.claim("generation")
        self.assertIn("reserved locally", self.scoped(self.codex, selected["id"])["dispositions"][0]["state"])
        self.codex.rpc_intent("generation", "rpc")
        self.assertIn("unconfirmed", self.scoped(self.codex, selected["id"])["dispositions"][0]["state"])
        self.codex.bind_turn("generation", "turn")
        self.assertEqual(self.scoped(self.codex, selected["id"])["dispositions"][0]["dispatch_state"], "accepted")
        self.codex.reconnect("next-generation")
        view = self.scoped(self.codex, selected["id"])
        self.assertEqual(view["attempts"][0]["origin_generation"], claim["generation"])
        self.assertEqual(view["dispositions"][0]["dispatch_state"], "unresolved")

    def test_shared_decisions_require_nonempty_unique_context_for_both_providers(self):
        for store in (self.codex, self.claude):
            selected, attempt = self.active(store)
            provider = store.metadata()["provider"]
            key = "provider_input_id" if provider == "claude" else "turnId"
            value = attempt["provider_input_id"] if provider == "claude" else attempt["turn_id"]
            params = dict(threadId=store.metadata()["native_id"], **{key: value})
            store.add_decision("generation", "valid", "fixture", params, ["deny"])
            store.add_decision("generation", "missing", "fixture", {"threadId": params["threadId"]}, ["deny"])
            store.add_decision("generation", "wrong", "fixture", {**params, "threadId": "other-native", "body": "UNRELATED_CONTROL_BODY"}, ["deny"])
            if provider == "claude":
                store.add_decision("generation", "child", "fixture", {**params, "agent_id": "child", "body": "UNRELATED_CHILD_BODY"}, ["deny"])
            default = next(row for row in self.owner.status()["sessions"] if row["session"]["id"] == store.metadata()["id"])
            self.assertEqual([row["request_id"] for row in default["decisions"]].count(selected["id"]), 1)
            view = self.scoped(store, selected["id"])
            self.assertEqual(len(view["decisions"]), 1)
            self.assertFalse(view["decision_summary"]["association_complete"])
            self.assertGreater(view["coverage"]["unassigned_controls"], 0)
            self.assertNotIn("UNRELATED_", json.dumps(view))
            raw = store.snapshot()
            raw["attempts"].append(deepcopy(raw["attempts"][0]))
            self.assertIsNone(decision_request(raw, raw["decisions"][0]))

    def test_none_to_none_decision_does_not_match_a_reserved_input(self):
        selected = self.codex.post("pending", "SELECTED_INPUT")
        self.codex.claim("generation")
        self.codex.add_decision("generation", "missing-turn", "fixture", {"threadId": "native-codex"}, ["deny"])
        default = self.owner.status()["sessions"][0]
        self.assertIsNone(default["decisions"][0]["request_id"])
        self.assertEqual(self.scoped(self.codex, selected["id"])["decisions"], [])

    def test_update_and_commentary_associations_reject_wrong_context(self):
        selected, attempt = self.active(self.codex)
        valid = self.codex.turn_update_intent("generation", key="update", request_id=selected["id"],
                                             expected_turn_id=attempt["turn_id"], body="SELECTED_UPDATE", entry="agent")
        invalid = {**valid, "id": "wrong-update", "native_id": "other-native", "body": "UNRELATED_UPDATE_BODY"}
        self.codex.event("generation", "awkit/turnUpdateIntent", invalid)
        view = self.scoped(self.codex, selected["id"])
        self.assertEqual([row["id"] for row in view["turn_updates"]], [valid["id"]])
        self.assertNotIn("UNRELATED_", json.dumps(view))
        raw = self.codex.snapshot()
        raw["attempts"][0]["public_update"] = dict(request_id=selected["id"], attempt_id=attempt["id"], generation="wrong", text="UNRELATED_COMMENTARY_BODY")
        self.with_raw(raw, selected["id"], lambda projected: self.assertIsNone(projected["attempts"][0]["public_update"]))

    def with_raw(self, raw, ident, assertion):
        with mock.patch.object(self.codex, "snapshot", return_value=deepcopy(raw)):
            value = self.scoped(self.codex, ident)
        assertion(value)
        return value

    def test_reply_record_inconsistency_is_explicit_without_importing_foreign_body(self):
        selected, attempt = self.active(self.codex)
        self.finish(self.codex, attempt)
        other = self.codex.post("other", "UNRELATED_INPUT")
        foreign = self.codex.channel.post("reviewer", "main", "re", "UNRELATED_REPLY", reply_to=other["id"])
        raw = self.codex.snapshot()
        raw["attempts"][0]["reply_id"] = foreign
        result = self.with_raw(raw, selected["id"], lambda projected: self.assertFalse(projected["coverage"]["association_complete"]))
        self.assertIsNone(result["reply_evidence"]["provider_reply_id"])
        self.assertNotIn("UNRELATED_", json.dumps(result))

    def test_one_snapshot_stays_coherent_during_completion_and_query_never_reads_live_active(self):
        selected, attempt = self.active(self.codex)
        captured, finished = threading.Event(), threading.Event()
        original = self.codex.snapshot

        def snapshot():
            value = original()
            captured.set()
            self.assertTrue(finished.wait(5))
            return value

        def complete():
            if captured.wait(5):
                self.finish(self.codex, attempt)
            finished.set()

        worker = threading.Thread(target=complete)
        worker.start()
        try:
            with mock.patch.object(self.codex, "snapshot", side_effect=snapshot), \
                    mock.patch.object(self.codex, "active", side_effect=AssertionError("fresh active read")):
                before = self.scoped(self.codex, selected["id"])
        finally:
            worker.join(5)
        self.assertEqual(before["attempts"][0]["state"], "executing")
        self.assertEqual(len(before["messages"]), 1)
        after = self.scoped(self.codex, selected["id"])
        self.assertEqual(after["attempts"][0]["state"], "returned")
        self.assertEqual(len(after["messages"]), 2)

    def test_snapshot_boundary_keeps_claim_cancellation_and_connection_change_separate(self):
        for provider in ("codex", "claude"):
            for transition in ("claim", "cancel", "disconnect"):
                with self.subTest(provider=provider, transition=transition):
                    store = self.store(provider + transition, provider)
                    selected = store.post("selected", "SELECTED_INPUT")
                    original = store.snapshot
                    captured, changed = threading.Event(), threading.Event()

                    def snapshot(original=original, captured=captured, changed=changed):
                        value = original()
                        captured.set()
                        self.assertTrue(changed.wait(5))
                        return value

                    def mutate(captured=captured, changed=changed, transition=transition, store=store, selected=selected):
                        try:
                            if captured.wait(5):
                                if transition == "claim":
                                    store.claim("generation")
                                elif transition == "cancel":
                                    store.cancel(selected["id"])
                                else:
                                    store.update(generation="next-generation", state="unknown")
                        finally:
                            changed.set()

                    worker = threading.Thread(target=mutate)
                    worker.start()
                    try:
                        with mock.patch.object(store, "snapshot", side_effect=snapshot):
                            before = self.scoped(store, selected["id"])
                    finally:
                        worker.join(5)
                    self.assertEqual(before["dispositions"][0]["dispatch_state"], "queued")
                    self.assertEqual(before["attempts"], [])
                    self.assertEqual(before["cancellations"], [])
                    self.assertEqual(before["session"]["generation"], "generation")
                    after = self.scoped(store, selected["id"])
                    if transition == "disconnect":
                        self.assertFalse(after["session_observation"]["connected"])
                        self.assertEqual(after["dispositions"][0]["dispatch_state"], "queued")
                    else:
                        self.assertEqual(after["dispositions"][0]["dispatch_state"],
                                         "admitting" if transition == "claim" else "cancelled")

    def server(self):
        server = SessionServer(self.owner)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        directory = self.root / ".awkit/sessions"
        directory.mkdir(parents=True)
        (directory / "controller.json").write_text(json.dumps(dict(schema=1, project=str(self.root), url=server.url, token=server.token)), encoding="utf-8")
        return server

    def test_cli_http_public_parity_errors_and_read_only_bytes(self):
        server = self.server()
        message = self.claude.post("selected", "SELECTED_INPUT")
        before = {store.path: store.path.read_bytes() for store in (self.codex, self.claude)}
        expected = request(self.root, "status", dict(session="Claude", request=message["id"]))
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["session", "--project", str(self.root), "status", "--session", "Claude", "--request", message["id"]])
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        self.assertEqual(json.loads(stdout.getvalue()), dict(schema=1, **expected))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for query in ("session=", "request=M-001", "session=Claude&session=Codex", "session=Claude&request=", "unexpected=value"):
            call = urllib.request.Request(server.url + "/api/status?" + query, headers={"Authorization": "Bearer " + server.token})
            with self.subTest(query=query), self.assertRaises(urllib.error.HTTPError) as raised:
                opener.open(call)
            self.assertEqual(raised.exception.code, 400)
            with raised.exception as response:
                self.assertIn("error", json.loads(response.read()))
        for args in (["--session", "Claude", "--session", "Codex"], ["--request", "M-001"], ["--session", ""]):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["session", "--project", str(self.root), "status", *args]), 2)
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents)
            conn = sqlite3.connect(path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM cursors").fetchone()[0], 0)
            finally:
                conn.close()

    def test_absent_endpoint_does_not_construct_a_controller_or_create_state(self):
        absent = self.root / "absent"
        absent.mkdir()
        with mock.patch("awkit.session_http.SessionController", side_effect=AssertionError("controller startup")):
            with self.assertRaises(FileNotFoundError):
                request(absent, "status", dict(session="Codex", request="M-001"))
        self.assertFalse((absent / ".awkit").exists())

    def test_pure_projection_refuses_duplicate_message_id_and_keeps_input_snapshot(self):
        selected = self.codex.post("one", "SELECTED_INPUT")
        view = self.owner.status(session="Codex")["sessions"][0]
        view.update(configuration_held=False, scoped_control_reason="fixture")
        original = deepcopy(view)
        exact_request(view, selected["id"])
        self.assertEqual(view, original)
        view["messages"].append(deepcopy(view["messages"][0]))
        with self.assertRaisesRegex(ValueError, "duplicated"):
            exact_request(view, selected["id"])
