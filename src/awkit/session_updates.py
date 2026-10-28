"""One exact active-turn input on an existing owned Codex connection; never queued or replayed."""

from .codex_enrollment import EXECUTABLE_SHA256, VERSION, local_path
from .codex_session import ProviderError, ProviderRejected
from .session_store import now

PREVENTS = {"awkit session update": ("F24", "F25", "F29")}


def supported(meta):
    client = meta.get("client") or {}
    return (meta["provider"] == "codex" and client.get("version") == VERSION
            and client.get("executable_sha256") == EXECUTABLE_SHA256)


def submit(controller, ident, *, key, request_id, expected_turn_id, body, entry="agent"):
    store = controller._store(ident)
    if entry not in ("agent", "human"):
        raise ValueError("Unsupported update entry.")
    with controller._mutex:
        for other in controller._stores.values():
            if other.posted_key(key):
                raise ValueError("This caller key already names a stored message; choose a fresh update key.")
            existing = next((row for row in other.turn_updates() if row["key"] == key), None)
            if existing:
                if (other is not store or any(existing[field] != value for field, value in (
                        ("request_id", request_id), ("expected_turn_id", expected_turn_id), ("body", body)))):
                    raise ValueError("This update key already names different input or target; no provider call was made.")
                return dict(session=store.metadata()["id"], update=existing, state=existing["state"], recovered=True)
        meta = store.metadata()
        provider, generation = controller._connection(store)
        if not supported(meta):
            raise ValueError("Exact-turn updates require the verified Codex runtime.")
        if provider is None or not provider.alive or meta["generation"] != generation:
            raise ValueError("Exact-turn updates require an available owned connection on the verified Codex runtime.")
        if meta["state"] not in ("running", "accepted", "decision needed"):
            raise ValueError("No active turn is currently observed for this conversation. Read its latest result before sending a new assignment.")
        intent = store.turn_update_intent(generation, key=key, request_id=request_id,
            expected_turn_id=expected_turn_id, body=body, entry=entry)
    may_have_sent = False

    def dispatch(rpc_id):
        nonlocal may_have_sent
        store.event(generation, "awkit/turnUpdateDispatch", dict(id=intent["id"], rpc_id=rpc_id,
            threadId=meta["native_id"], turnId=expected_turn_id))
        may_have_sent = True

    outcome = dict(id=intent["id"])
    try:
        observed = provider.call("thread/read", {"threadId": meta["native_id"]})["thread"]
        outcome["observation"] = ({field: observed.get(field) for field in ("id", "cwd", "status", "canAcceptDirectInput")}
                                  if isinstance(observed, dict) else {"uninterpretable": True})
        if (not isinstance(observed, dict) or observed.get("id") != meta["native_id"]
                or local_path(observed["cwd"]) != controller.project or not isinstance(observed.get("status"), dict)
                or observed["status"].get("type") != "active" or observed.get("canAcceptDirectInput") is not True):
            raise ValueError("Native active identity/project/direct input is unavailable; no update was sent.")
        result = provider.call("turn/steer", dict(threadId=meta["native_id"], expectedTurnId=expected_turn_id,
            input=[dict(type="text", text=body)]), on_request=dispatch)
        outcome["native_response"] = result
        if not isinstance(result, dict) or result.get("turnId") != expected_turn_id:
            raise ProviderError("Native acknowledgement names a different turn; admission remains uncertain.")
        outcome.update(state="acknowledged", returned_turn_id=result["turnId"],
                       source="native turn/steer response; output adoption unverified")
    except ProviderRejected as exc:
        rejected = not may_have_sent or exc.code in (-32600, -32601, -32602)
        outcome.update(state="refused" if rejected else "uncertain", error=str(exc), native_error=exc.error,
                       source="native validation rejection; no fallback" if rejected else "native internal error; admission uncertain; never replayed")
    except (OSError, ValueError, KeyError, TypeError, ProviderError) as exc:
        outcome.update(state="uncertain" if may_have_sent else "refused", error=str(exc),
                       source="native admission uncertain; never replayed" if may_have_sent else "preflight unavailable; no input sent")
    outcome["finished_at"] = now()
    store.event(generation, "awkit/turnUpdateResult", outcome)
    retained = next(row for row in store.turn_updates() if row["id"] == intent["id"])
    return dict(session=meta["id"], update=retained, state=retained["state"], recovered=False)
