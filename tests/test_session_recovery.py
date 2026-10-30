"""Durable offline provider faults; these do not establish live-provider recovery."""

import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

import test_sessions
from awkit.sessions import SessionController


class RecoveryTests(unittest.TestCase):
    setUp = test_sessions.SessionControllerTests.setUp
    create = test_sessions.SessionControllerTests.create
    wait_for = test_sessions.SessionControllerTests.wait_for
    def restart(self):
        self.controller.close()
        self.controller = SessionController(self.project, self.controller.command)
        self.addCleanup(self.controller.close)
        return self.wait_for(lambda view: view["can_send"])

    def test_context_and_completed_work_survive_without_replay(self):
        session = self.create()
        self.controller.send(session["id"], key="first", body="Cedar the invented otter")
        self.wait_for(lambda view: len(view["messages"]) == 2)
        recovered = self.restart()
        self.assertEqual(recovered["session"]["native_id"], session["native_id"])
        self.assertEqual(len(recovered["attempts"]), 1)
        self.controller.send(session["id"], key="follow-up", body="recall")
        final = self.wait_for(lambda view: len(view["messages"]) == 4)
        self.assertIn("Cedar", final["messages"][-1]["body"])
        self.assertEqual(len(final["attempts"]), 2)
        self.assertEqual(len(json.loads((self.project / ".offline-native.json").read_text())), 1)

    def test_lost_rpc_response_is_correlated_by_client_id_without_resend(self):
        self.check_recovered_reply("LOST_RESPONSE", expect_bound=False)

    def test_slow_provider_completion_is_waited_for_without_another_attempt(self):
        session = self.create()
        request = self.controller.send(session["id"], key="delayed", body="DELAYED_FINISH")["message"]
        completed = self.wait_for(lambda view: len(view["messages"]) == 2)
        self.assertEqual(completed["messages"][-1]["reply_to"], request["id"])
        self.assertEqual(completed["attempts"][0]["state"], "returned")
        self.assertEqual(len(completed["attempts"]), 1)

    def test_reply_missing_locally_is_recovered_by_known_turn(self):
        self.check_recovered_reply("MISSING_RECORD", expect_bound=True)

    def check_recovered_reply(self, body, *, expect_bound):
        session = self.create()
        request = self.controller.send(session["id"], key="fault", body=body)["message"]
        # The response and the connection loss race; wait until both are recorded, in either order.
        lost = self.wait_for(lambda view: view["attempts"] and view["attempts"][0]["state"] == "uncertain"
                             and bool(view["attempts"][0]["turn_id"]) == expect_bound)
        self.assertEqual(bool(lost["attempts"][0]["turn_id"]), expect_bound)
        recovered = self.restart()
        self.assertEqual(len(recovered["messages"]), 2)
        self.assertEqual(recovered["messages"][-1]["reply_to"], request["id"])
        self.assertEqual(recovered["messages"][-1]["body"], "Recovered: " + body)
        self.assertEqual(recovered["attempts"][0]["state"], "returned")
        self.assertNotEqual(recovered["attempts"][0]["origin_generation"], recovered["attempts"][0]["generation"])
        repeated = self.controller.send(session["id"], key="fault", body=body)
        self.assertEqual(repeated["message"]["id"], request["id"])
        self.assertEqual(len(self.controller.status()["sessions"][0]["attempts"]), 1)

    def test_unknown_delivery_stays_distinct_from_a_new_assignment(self):
        session = self.create()
        self.controller.send(session["id"], key="unknown", body="DISCONNECT")
        self.wait_for(lambda view: view["attempts"] and view["attempts"][0]["state"] == "uncertain")
        recovered = self.restart()
        self.assertEqual(recovered["attempts"][0]["state"], "unresolved")
        old = recovered["messages"][0]["id"]
        self.controller.cancel(session["id"], old)
        self.controller.send(session["id"], key="fresh", body="A separate new assignment")
        final = self.wait_for(lambda view: len(view["messages"]) == 3)
        self.assertEqual(final["attempts"][0]["state"], "unresolved")
        self.assertEqual(final["messages"][-1]["reply_to"], final["messages"][1]["id"])
        self.assertIn("delivery unresolved", final["dispositions"][0]["state"])
        self.assertEqual(final["dispositions"][0]["cancellation"]["disposition"], "after-dispatch")

    def test_old_decision_and_unsent_cancellation_remain_identifiable(self):
        session = self.create()
        self.controller.send(session["id"], key="decision", body="ASK_APPROVAL")
        pending = self.wait_for(lambda view: bool(view["decisions"]))
        decision = pending["decisions"][0]
        cancelled = self.controller.send(session["id"], key="cancel", body="Never dispatch this")["message"]
        queued = self.controller.send(session["id"], key="queued", body="Separate queued work")["message"]
        self.controller.cancel(session["id"], cancelled["id"])
        self.restart()
        final = self.wait_for(lambda view: any(row["reply_to"] == queued["id"] for row in view["messages"]))
        self.assertEqual(final["decisions"][0]["state"], "route unavailable")
        self.assertFalse(final["decisions"][0]["can_answer"])
        self.assertEqual(final["decisions"][0]["request_id"], pending["messages"][0]["id"])
        with self.assertRaises(ValueError):
            self.controller.decide(session["id"], decision["id"], "accept")
        self.assertEqual({row["request_id"] for row in final["attempts"]}, {pending["messages"][0]["id"], queued["id"]})
        self.assertIn("cancelled before dispatch", {row["state"] for row in final["dispositions"]})

    def test_persisted_completed_event_recovers_before_history_access(self):
        session = self.create()
        store = self.controller._store(session["id"])
        with patch.object(store, "finish", side_effect=RuntimeError("injected local recording interruption")):
            self.controller.send(session["id"], key="local-boundary", body="Already returned answer")
            self.wait_for(lambda view: any(row["method"] == "turn/completed" for row in view["events"]))
        recovered = self.restart()
        self.assertEqual(len(recovered["messages"]), 2)
        self.assertEqual(recovered["attempts"][0]["state"], "returned")

    def test_duplicate_native_client_key_does_not_bind_a_reply(self):
        session = self.create()
        self.controller.send(session["id"], key="ambiguous", body="AMBIGUOUS_RESPONSE")
        self.wait_for(lambda view: view["attempts"] and view["attempts"][0]["state"] == "uncertain")
        recovered = self.restart()
        self.assertEqual(recovered["attempts"][0]["state"], "unresolved")
        self.assertEqual(len(recovered["messages"]), 1)
        self.assertEqual(len(recovered["attempts"]), 1)

    def test_owner_conflict_stays_visible_without_replacement_or_retry_loop(self):
        session = self.create()
        self.controller.close()
        conflict = self.project / ".offline-resume-error"
        conflict.write_text("owned elsewhere")
        self.controller = SessionController(self.project, self.controller.command)
        self.addCleanup(self.controller.close)
        unavailable = self.wait_for(lambda view: "Active owner conflict" in (view["session"].get("error") or ""))
        self.assertFalse(unavailable["can_send"])
        self.assertIn("Active owner conflict", unavailable["control_reason"])
        self.assertEqual(unavailable["session"]["native_id"], session["native_id"])
        self.assertEqual(unavailable["attempts"], [])
        conflict.unlink()
        self.controller.resume(session["id"])
        resumed = self.wait_for(lambda view: view["can_send"])
        self.assertEqual(resumed["session"]["native_id"], session["native_id"])
        self.assertEqual(resumed["messages"], [])

    def test_interruption_acknowledgement_is_not_a_terminal_outcome(self):
        session = self.create()
        self.controller.send(session["id"], key="hold", body="HOLD")
        before = self.wait_for(lambda view: view["attempts"] and view["attempts"][0]["state"] == "executing")
        provider = self.controller.provider
        original = provider.call
        with patch.object(provider, "call", side_effect=lambda method, params, **kw: {} if method == "turn/interrupt" else original(method, params, **kw)):
            receipt = self.controller.interrupt(session["id"])
        self.assertEqual(receipt["state"], "interrupt requested")
        pending = self.controller.status()["sessions"][0]
        self.assertEqual(pending["attempts"][0]["state"], "executing")
        self.assertIn("interruption requested", pending["dispositions"][0]["state"])
        self.assertIsNone(pending["attempts"][0]["outcome"])
        provider.call("turn/interrupt", dict(threadId=session["native_id"], turnId=before["attempts"][0]["turn_id"]))
        final = self.wait_for(lambda view: view["attempts"][0]["state"] == "no-reply")
        self.assertEqual(final["attempts"][0]["outcome"], "interrupted")

    def test_new_callback_cannot_reuse_a_previous_decision(self):
        session = self.create()
        self.controller.send(session["id"], key="first-decision", body="ASK_APPROVAL")
        first = self.wait_for(lambda view: bool(view["decisions"]))["decisions"][0]
        self.controller.decide(session["id"], first["id"], "decline")
        self.wait_for(lambda view: len(view["messages"]) == 2)
        self.controller.send(session["id"], key="second-decision", body="ASK_APPROVAL")
        second = self.wait_for(lambda view: len(view["decisions"]) == 2)
        self.assertEqual(second["decisions"][0]["state"], "resolved")
        self.assertEqual(second["decisions"][1]["state"], "pending")
        self.assertIsNone(second["decisions"][1]["response"])
        self.assertNotEqual(first["id"], second["decisions"][1]["id"])
        with self.assertRaises(ValueError):
            self.controller.decide(session["id"], first["id"], "accept")

    def test_changed_effective_scope_preserves_saved_policy_and_holds_queued_work(self):
        session = self.create()
        store = self.controller._store(session["id"])
        saved = dict(store.metadata()["permissions"], approvalPolicy="untrusted")
        store.update(permissions=saved)
        self.controller.send(session["id"], key="hold", body="HOLD")
        self.wait_for(lambda view: view["attempts"] and view["attempts"][0]["state"] == "executing")
        queued = self.controller.send(session["id"], key="held-queue", body="Do not dispatch with changed permissions")["message"]
        self.controller.close()
        changed = self.project / ".offline-permission-change"
        changed.write_text("injected changed provider configuration")
        self.controller = SessionController(self.project, self.controller.command)
        self.addCleanup(self.controller.close)
        held = self.wait_for(lambda view: "permission scope differs" in (view["session"].get("error") or ""))
        self.assertFalse(held["can_send"])
        self.assertEqual(held["session"]["permissions"], saved)
        self.assertEqual(held["session"]["returned_scope"]["approvalPolicy"], "never")
        self.assertFalse(any(row["request_id"] == queued["id"] for row in held["attempts"]))
        changed.unlink()
        self.controller.resume(session["id"])
        resumed = self.wait_for(lambda view: any(row["reply_to"] == queued["id"] for row in view["messages"]))
        self.assertEqual(resumed["session"]["permissions"]["approvalPolicy"], "untrusted")
        self.assertIsNone(resumed["session"]["returned_scope"])

    def test_managed_migration_preserves_core_messages_keys_and_provenance(self):
        session = self.create()
        self.controller.send(session["id"], key="migration", body="Stored before migration")
        before = self.wait_for(lambda view: len(view["messages"]) == 2)
        self.controller.close()
        with closing(sqlite3.connect(before["channel"])) as conn, conn:
            conn.execute("DROP TABLE awkit_cancellations")
            for field in ("origin_generation", "client_id", "interruption_requested"):
                conn.execute(f"ALTER TABLE awkit_delivery DROP COLUMN {field}")
            conn.execute("UPDATE awkit_session SET schema=1")
        after = self.restart()
        self.assertEqual(after["extension_schema"], 3)
        self.assertEqual(after["messages"], before["messages"])
        self.assertEqual(after["posts"], before["posts"])
        self.assertEqual(after["attempts"][0]["origin_generation"], before["attempts"][0]["generation"])
        self.assertIsNone(after["attempts"][0]["client_id"])
        with closing(sqlite3.connect(after["channel"])) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)
