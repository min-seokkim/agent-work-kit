"""How the controller reaches each managed conversation.

A session is reached in one of three ways: the controller's own Codex app server, a dedicated connection to
an enrolled Codex conversation, or a Claude SDK client. Each way is a route with the same operations, so the
controller asks the session's route instead of branching on the provider. Routes are part of the controller
and use its public methods only.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

from . import session_states as states
from .claude_session import recover_local_results
from .codex_session import ProviderError
from .session_models import hold
from .session_models import ready as model_ready
from .session_store import now

DECISIONS = {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}
DISPATCH_ERRORS = (OSError, ValueError, KeyError, TypeError, sqlite3.Error, ProviderError)


class Route:
    """The operations every route provides. `meta` is the session's stored metadata."""

    def connection(self, controller, meta):
        """(client or None, generation) for sending and status."""
        raise NotImplementedError

    def request_connection(self, controller, meta):
        """(client or None, generation) for a request-scoped status read."""
        return self.connection(controller, meta)

    def resume(self, controller, store):
        raise NotImplementedError

    def dispatch(self, controller, store, meta):
        """One dispatcher cycle for this session: send its next queued request when the conversation is idle."""
        raise NotImplementedError

    def failed(self, controller, store, error):
        """Record a dispatch error as an uncertain attempt."""
        store.uncertain(self.connection(controller, store.metadata())[1], str(error))

    def decide(self, controller, store, decision_id, choice):
        raise NotImplementedError

    def interrupt(self, controller, store):
        raise NotImplementedError


class ClaudeRoute(Route):
    def connection(self, controller, meta):
        client = controller.claude_clients.get(meta["id"])
        return client, client.generation if client else controller.generation

    def request_connection(self, controller, meta):
        client = controller.claude_clients.get(meta["id"])
        return client, client.generation if client else controller.generation

    def resume(self, controller, store):
        meta = store.metadata()
        prior = controller.claude_clients.get(meta["id"])
        if prior and prior.alive and meta["state"] != "unknown":
            return
        if prior:
            prior.close()
        controller.claude_clients.pop(meta["id"], None)
        recover_local_results(store)
        generation = str(uuid.uuid4())
        store.reconnect(generation)
        store.update(generation=generation, state="reconnecting", observed_at=now(), source="exact-ID Claude resume")
        controller.recovery_attempted.add(meta["id"])
        try:
            controller.claude_clients[meta["id"]] = controller.claude_factory(store, cli_path=controller.claude_cli, resume=True)
        except (OSError, ValueError, RuntimeError, ImportError) as exc:
            store.update(state="unknown", error=str(exc), source="Claude resume unavailable; no resend", observed_at=now())

    def dispatch(self, controller, store, meta):
        if meta["id"] not in controller.claude_clients and meta["id"] not in controller.recovery_attempted:
            controller.resume(meta["id"])
        client = controller.claude_clients.get(meta["id"])
        if client and client.alive and store.metadata()["state"] == "idle":
            claim = store.claim(client.generation)
            if claim:
                client.submit(claim)

    def decide(self, controller, store, decision_id, choice):
        client = controller.claude_clients.get(store.metadata()["id"])
        if not client or not client.alive:
            raise ValueError("The original Claude callback connection is unavailable.")
        return client.decide(decision_id, choice)

    def interrupt(self, controller, store):
        client = controller.claude_clients.get(store.metadata()["id"])
        active = store.active(client.generation) if client else None
        if not active or not client.alive:
            raise ValueError("No correlated Claude work is active on this connection.")
        store.request_interruption(active["id"])
        client.interrupt()
        return dict(state="interrupt requested", task_result="unverified")


class CodexRoute(Route):
    """What owned and enrolled Codex conversations share: thread/read before turn/start, and native decisions."""

    def wants_resume(self, controller, meta):
        raise NotImplementedError

    def before_read(self, controller, store, provider):
        """Checks a route runs before asking the provider about the thread."""

    def dispatch(self, controller, store, meta):
        if self.wants_resume(controller, meta):
            controller.resume(meta["id"])
            meta = store.metadata()
        provider, generation = self.connection(controller, meta)
        if (not model_ready(meta) or meta["generation"] != generation
                or meta["state"] not in states.DISPATCHABLE or not meta["native_id"]):
            return
        if not store.has_pending_request():
            return
        if provider is None or not provider.alive:
            return
        self.before_read(controller, store, provider)
        result = provider.call("thread/read", {"threadId": meta["native_id"]})
        thread = result.get("thread", {})
        state = thread.get("status", {}).get("type")
        if thread.get("id") != meta["native_id"] or state not in ("idle", "active"):
            store.update(state="unknown", observed_at=now(), source="thread/read", error="Provider identity or availability is uncertain.")
            return
        if state == "active":
            store.observe_state(meta["state"], state="waiting for idle", observed_at=now(), source="thread/read")
            return
        if store.observe_state(meta["state"], state="idle", observed_at=now(), source="thread/read") is None:
            return  # the state changed during thread/read; decide again on the next cycle
        claim = store.claim(generation)
        if claim is None:
            return
        result = provider.call("turn/start", {
            "threadId": claim["native_id"], "clientUserMessageId": claim["id"],
            "input": [{"type": "text", "text": claim["request"]["body"]}]},
            on_request=lambda rpc_id, target=store, gen=generation: target.rpc_intent(gen, rpc_id))
        turn_id = result["turn"]["id"]
        store.bind_turn(generation, turn_id)
        # Events can precede the RPC response. Bind only the response's actual turn.
        for method, params in store.turn_events(turn_id):
            controller.apply_turn(store, method, params)

    def decide(self, controller, store, decision_id, choice):
        provider, generation = self.connection(controller, store.metadata())
        decision = next((row for row in store.snapshot()["decisions"] if row["id"] == decision_id), None)
        if (decision is None or decision["generation"] != generation or decision["method"] not in DECISIONS
                or choice not in decision["choices"]):
            raise ValueError("This choice is unavailable for the originating provider request.")
        active = store.active(generation)
        if (provider is None or not provider.alive or active is None
                or decision["params"].get("threadId") != active["native_id"]
                or decision["params"].get("turnId") != active["turn_id"]):
            raise ValueError("The originating provider turn is not correlated on this live connection; no answer was sent.")
        row = store.answer_intent(generation, decision_id, {"decision": choice})
        try:
            provider.respond(json.loads(row["rpc_id"]), {"decision": choice})
        except ProviderError:
            store.decision_state(decision_id, "uncertain")
            raise
        store.decision_state(decision_id, "sent")
        return dict(state="sent", decision=decision_id)

    def interrupt(self, controller, store):
        provider, generation = self.connection(controller, store.metadata())
        active = store.active(generation)
        if active is None or not active["turn_id"] or provider is None or not provider.alive:
            raise ValueError("There is no observed live turn to interrupt on this connection.")
        store.interruption(generation, active["turn_id"])
        provider.call("turn/interrupt", {"threadId": active["native_id"], "turnId": active["turn_id"]})
        return dict(state="interrupt requested", task_result="unverified")


class OwnedCodexRoute(CodexRoute):
    def connection(self, controller, meta):
        return controller.provider, controller.generation

    def wants_resume(self, controller, meta):
        return meta["generation"] != controller.generation and meta["id"] not in controller.recovery_attempted

    def resume(self, controller, store):
        from .session_recovery import resume

        controller.provider_error = None
        if controller.provider is not None and not controller.provider.alive:
            controller.provider.close()
            controller.provider = None
            controller.provider_error = None
            # Native request IDs are scoped to this connection, not the HTTP process.
            controller.generation = str(uuid.uuid4())
            controller.recovery_attempted.clear()
        if store.metadata()["generation"] == controller.generation and store.metadata()["state"] != "unknown":
            return
        controller.recovery_attempted.add(store.metadata()["id"])
        try:
            resume(controller, store)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, ProviderError) as exc:
            hold(store)
            store.update(state="unknown", observed_at=now(), source="resume unavailable; history retained", error=str(exc))


class EnrolledCodexRoute(CodexRoute):
    def connection(self, controller, meta):
        client = controller.enrolled_clients.get(meta["id"])
        return client, client.generation if client else meta["generation"]

    def request_connection(self, controller, meta):
        client = controller.enrolled_clients.get(meta["id"])
        return client, client.generation if client else controller.generation

    def wants_resume(self, controller, meta):
        return meta["id"] not in controller.enrolled_clients and meta["id"] not in controller.recovery_attempted

    def resume(self, controller, store):
        prior = controller.enrolled_clients.get(store.metadata()["id"])
        if not prior or not prior.alive or store.metadata()["state"] == "unknown":
            controller.resume_enrolled(store)

    def before_read(self, controller, store, provider):
        from .codex_enrollment import observe

        observe(controller, store, provider)

    def failed(self, controller, store, error):
        super().failed(controller, store, error)
        client = controller.enrolled_clients.pop(store.metadata()["id"], None)
        if client:
            client.close()


ROUTES = {"claude": ClaudeRoute(), "owned": OwnedCodexRoute(), "enrolled": EnrolledCodexRoute()}


def route(meta):
    """The route for a session's stored metadata."""
    if meta.get("enrollment"):
        return ROUTES["enrolled"]
    return ROUTES["claude"] if meta["provider"] == "claude" else ROUTES["owned"]
