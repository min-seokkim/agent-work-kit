"""Reconcile only the known owned native conversation; never regenerate missing work."""

from pathlib import Path

from .codex_session import ProviderError
from .session_models import observe as observe_model
from .session_models import selected, verify_runtime
from .session_store import now

TERMINAL = {"completed", "failed", "interrupted"}


def pages(provider, method, params):
    rows, seen = [], set()
    for _ in range(1000):
        result = provider.call(method, params)
        rows.extend(result["data"])
        cursor = result.get("nextCursor")
        if not cursor:
            return rows
        if cursor in seen:
            raise ProviderError("Provider repeated a history cursor; reconciliation is incomplete.")
        seen.add(cursor)
        params = dict(params, cursor=cursor)
    raise ProviderError("History pagination limit reached; reconciliation is incomplete.")


def recover_completed(store):
    # A completed event persisted before a local crash is sufficient to publish its original reply.
    for attempt in store.snapshot()["attempts"]:
        if attempt["state"] in ("returned", "failed", "no-reply") or not attempt["turn_id"]:
            continue
        for method, params in store.turn_events(attempt["turn_id"]):
            turn = params.get("turn", {})
            if method == "turn/completed" and turn.get("status") in TERMINAL:
                store.finish(attempt["generation"], turn["id"], turn["status"],
                             store.final_text(turn["id"], turn.get("items", [])), turn.get("error"))


def resume(controller, store):
    meta = store.metadata()
    native_id = meta.get("native_id")
    if not native_id:
        raise ValueError("No admitted native identity exists. The uncertain creation has not been replaced.")
    recover_completed(store)
    store.reconnect(controller.generation)
    store.update(generation=controller.generation, state="reconnecting", source="exact-ID resume requested",
                 observed_at=now(), error=None)
    permissions = meta["permissions"]
    sandbox = permissions.get("sandbox", permissions.get("requested", {}).get("sandbox"))
    sandbox = sandbox.get("type") if isinstance(sandbox, dict) else sandbox
    sandbox = {"readOnly": "read-only", "workspaceWrite": "workspace-write"}.get(sandbox, sandbox)
    if sandbox not in ("read-only", "workspace-write"):
        raise ValueError("Saved permission scope cannot be resumed safely by this controller.")
    provider = controller._owned_provider()
    if selected(meta):
        verify_runtime(controller, provider)
    result = provider.call("thread/resume", dict(threadId=native_id, cwd=str(controller.project),
        sandbox=sandbox, approvalPolicy=permissions["approvalPolicy"], approvalsReviewer=permissions["approvalsReviewer"], excludeTurns=True,
        developerInstructions=meta["startup_context"]["developer_instructions"]))
    if selected(meta):
        observe_model(store, result, creation=False)
    thread = result["thread"]
    if thread["id"] != native_id or Path(result["cwd"]).resolve() != controller.project:
        raise ValueError("Resume returned a different conversation or project. No replacement has been bound.")
    scope = {key: result[key] for key in ("sandbox", "approvalPolicy", "approvalsReviewer")}
    if scope != {key: permissions[key] for key in scope}:
        store.update(returned_scope=scope)
        raise ValueError("Resumed permission scope differs from the saved scope; no queued work was dispatched. "
                         "Saved and returned scopes remain available for inspection.")
    store.update(returned_scope=None)
    store.update(client=controller.client, permissions=dict(
        {key: result[key] for key in ("cwd", "sandbox", "approvalPolicy", "approvalsReviewer")}, source="thread/resume response"))
    reconcile(controller, store, provider, thread=thread)


def reconcile(controller, store, provider, *, thread=None):
    """Recover only this channel's recorded attempts on its admitted native owner."""
    meta = store.metadata()
    native_id, generation = meta["native_id"], meta["generation"]
    thread = thread or {"status": {"type": "idle"}}
    attempts = [row for row in store.snapshot()["attempts"] if row["state"] == "unresolved"]
    if attempts:
        turns = pages(provider, "thread/turns/list", dict(threadId=native_id, limit=100, sortDirection="asc", itemsView="full"))
        if len({turn["id"] for turn in turns}) != len(turns):
            raise ValueError("History contains duplicate turn identities; no ambiguous result was bound.")
        for turn in turns:
            if turn.get("itemsView", "full") != "full":
                entries = pages(provider, "thread/items/list", dict(threadId=native_id, turnId=turn["id"], limit=100, sortDirection="asc"))
                if any(entry["turnId"] != turn["id"] for entry in entries):
                    raise ValueError("Provider returned items from a different turn.")
                turn["items"] = [entry["item"] for entry in entries]
        used = {row["turn_id"] for row in store.snapshot()["attempts"]
                if row["state"] != "unresolved" and row["turn_id"]}
        for attempt in attempts:
            matches = [turn for turn in turns if turn["id"] == attempt["turn_id"]] if attempt["turn_id"] else [
                turn for turn in turns for item in turn.get("items", []) if attempt.get("client_id") and
                    item.get("type") == "userMessage" and item.get("clientId") == attempt["client_id"]
                ]
            if len(matches) != 1 or matches[0]["id"] in used:
                continue
            turn = matches[0]
            used.add(turn["id"])
            if turn["status"] in TERMINAL:
                store.recover_turn(generation, attempt["id"], turn["id"])
                retained = dict(id=turn["id"], status=turn["status"], items=[item for item in turn.get("items", [])
                                if item.get("type") != "reasoning"])
                store.event(generation, "awkit/recoveredTurn", dict(threadId=native_id, turn=retained))
                store.finish(generation, turn["id"], turn["status"],
                             store.final_text(turn["id"], turn.get("items", [])), turn.get("error"))
            elif turn["status"] == "inProgress" and thread.get("status", {}).get("type") == "active":
                store.recover_turn(generation, attempt["id"], turn["id"], running=True)
                for method, params in store.turn_events(turn["id"]):
                    controller._apply_turn(store, method, params)
    # Observe after history: a stale active history entry is not proof of a live turn.
    observed = provider.call("thread/read", {"threadId": native_id})["thread"]
    if observed["id"] != native_id or observed.get("status", {}).get("type") not in ("idle", "active"):
        raise ValueError("Provider has not established the resumed conversation's current availability.")
    active = store.active(generation)
    store.update(state="running" if active else "idle" if observed["status"]["type"] == "idle" else "waiting for idle",
                 source="exact-ID resume and history reconciliation", observed_at=now(), error=None)
