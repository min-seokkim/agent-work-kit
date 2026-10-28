"""Read-only dispositions from existing exchanges, attempts and explicit declarations."""

from copy import deepcopy

from .channel import ID, REQUESTS


class SelectorError(ValueError):
    """The requested local read target is missing or unsupported."""


def selectors(values):
    """Parse public query/CLI values without treating blanks or repeats as omission."""
    if not isinstance(values, dict) or set(values) - {"session", "request"}:
        raise SelectorError("Status accepts only session and request selectors.")
    result = {}
    for key, value in values.items():
        if isinstance(value, list):
            if len(value) != 1:
                raise SelectorError(f"Supply the {key} selector exactly once.")
            value = value[0]
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise SelectorError(f"The {key} selector must be a nonempty exact local identifier.")
        if key == "session" and len(value) > 200:
            raise SelectorError("The session selector is at most 200 characters.")
        if key == "request" and not ID.fullmatch(value):
            raise SelectorError("The request selector must be an exact stored message ID, such as M-007.")
        result[key] = value
    if "request" in result and "session" not in result:
        raise SelectorError("A request selector requires an explicit managed session selector.")
    return result


def _input(message):
    return (message.get("sender") == "main" and message.get("receiver") == "reviewer"
            and message.get("kind") in REQUESTS and not message.get("reply_to"))


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _generations(attempt):
    return {value for value in (attempt.get("generation"), attempt.get("origin_generation")) if _text(value)}


def _native_context(meta, attempt, params, generation):
    return (_text(generation) and generation in _generations(attempt)
            and _text(attempt.get("native_id")) and attempt["native_id"] == meta.get("native_id")
            and _text(params.get("threadId")) and params["threadId"] == attempt["native_id"])


def decision_request(view, decision):
    """Assign only a uniquely correlated, context-consistent provider control."""
    meta, params = view["session"], decision.get("params", {})
    if not isinstance(params, dict):
        raise ValueError("Stored provider control parameters are unsupported; scoped association is unavailable.")
    originals = {row["id"] for row in view["messages"] if _input(row)}
    candidates = []
    for row in view["attempts"]:
        if row["request_id"] not in originals or not _native_context(meta, row, params, decision.get("generation")):
            continue
        if meta["provider"] == "claude":
            matches = (params.get("agent_id") is None and _text(params.get("provider_input_id"))
                       and _text(row.get("provider_input_id")) and row["provider_input_id"] == params["provider_input_id"])
        else:
            matches = (_text(params.get("turnId")) and _text(row.get("turn_id")) and row["turn_id"] == params["turnId"])
        if matches:
            candidates.append(row)
    return candidates[0]["request_id"] if len(candidates) == 1 else None


def exact_request(view, request_id, declarations=None):
    """Project one immutable retained snapshot; no live store or provider calls."""
    by_id = {row["id"]: row for row in view["messages"]}
    if len(by_id) != len(view["messages"]):
        raise ValueError("Stored message IDs are duplicated; scoped reading is unavailable.")
    original = by_id.get(request_id)
    if original is None:
        raise SelectorError("The selected managed channel has no input with that request ID.")
    if not _input(original):
        raise SelectorError("Select an original main-to-reviewer request, not a notice, reply, close or reverse-role message.")
    chosen = {request_id}
    # Only reply edges can extend this tree; independent requests never enter it.
    changed = True
    while changed:
        changed = False
        for row in view["messages"]:
            parent = by_id.get(row.get("reply_to"))
            if (row["id"] not in chosen and row.get("kind") in ("re", "rebut") and parent
                    and parent["id"] in chosen and row.get("sender") == parent.get("receiver")
                    and row.get("receiver") == parent.get("sender")):
                chosen.add(row["id"])
                changed = True
    messages = [deepcopy(row) for row in view["messages"] if row["id"] in chosen]
    attempts = [deepcopy(row) for row in view["attempts"] if row["request_id"] == request_id]
    meta = view["session"]
    limits = []
    if len(attempts) > 1:
        limits.append("Multiple attempt records reference this input; its native lifecycle is ambiguous.")
    for attempt in attempts:
        update = attempt.get("public_update")
        if update and not (meta["provider"] == "codex" and update.get("request_id") == request_id and update.get("attempt_id") == attempt["id"]
                           and _native_context(meta, attempt, {"threadId": update.get("thread_id")}, update.get("generation"))
                           and _text(attempt.get("turn_id")) and update.get("turn_id") == attempt["turn_id"]):
            attempt["public_update"] = None
            limits.append("A commentary record lacks consistent request/attempt context and was omitted.")
    valid = attempts[0] if len(attempts) == 1 else None
    provider_reply = None
    if valid and valid.get("reply_id"):
        row = by_id.get(valid["reply_id"])
        if row and row["id"] in chosen and row.get("reply_to") == request_id and row.get("kind") == "re" and row.get("sender") == "reviewer":
            provider_reply = row["id"]
        else:
            limits.append("The attempt's recorded reply ID has no consistent direct reply; provider reply evidence is unavailable.")
    if valid and valid.get("state") == "returned" and not provider_reply:
        limits.append("The attempt is marked returned but its bound provider reply is unavailable.")
    if valid and valid.get("state") in ("failed", "no-reply") and provider_reply:
        limits.append("The retained native disposition and bound reply evidence disagree; neither fact was replaced.")
    decisions, unassigned = [], 0
    for decision in view["decisions"]:
        association = decision_request(view, decision)
        if association == request_id:
            decisions.append(deepcopy(decision))
        elif association is None:
            unassigned += 1
    if unassigned:
        limits.append("Some session controls lack unique request context; this view cannot establish whether they concern this input.")
    turn_updates = []
    for update in view.get("turn_updates", []):
        if update.get("request_id") != request_id:
            if not _text(update.get("request_id")) or (valid and update.get("attempt_id") == valid["id"]):
                limits.append("An update has missing or conflicting request identity; its association is unavailable.")
            continue
        if (valid and meta["provider"] == "codex" and update.get("attempt_id") == valid["id"]
                and _native_context(meta, valid, {"threadId": update.get("native_id")}, update.get("generation"))
                and _text(valid.get("turn_id")) and update.get("expected_turn_id") == valid["turn_id"]):
            turn_updates.append(deepcopy(update))
        else:
            limits.append("An update record lacks consistent attempt/native context and was omitted.")
    result = dict(session={key: meta.get(key) for key in ("id", "name", "provider", "project", "native_id", "generation")},
                  channel=view["channel"], request=deepcopy(original), messages=messages, attempts=attempts,
                  decisions=decisions, cancellations=[deepcopy(row) for row in view.get("cancellations", []) if row["request_id"] == request_id],
                  posts=[deepcopy(row) for row in view.get("posts", []) if row["message_id"] in chosen],
                  turn_updates=turn_updates, unanswered=[request_id] if request_id in view["unanswered"] else [],
                  closed=view["closed"], capabilities=deepcopy(view["capabilities"]),
                  session_observation=dict(connected=view["connected"], execution_state=view["execution_state"],
                                           state=meta["state"], observed_at=meta["observed_at"], source=meta["source"],
                                           configuration_held=view["configuration_held"], control_reason=view["scoped_control_reason"]),
                  reply_evidence=dict(provider_reply_id=provider_reply,
                                      direct_ids=[row["id"] for row in messages if row.get("reply_to") == request_id],
                                      descendant_ids=[row["id"] for row in messages if row["id"] != request_id and row.get("reply_to") != request_id]),
                  coverage=dict(association_complete=not limits, unassigned_controls=unassigned, limitations=limits,
                                public_updates="retained Codex commentary only" if meta["provider"] == "codex" else "unavailable for Claude",
                                semantic_acceptance="unverified"))
    result["dispositions"] = dispositions(result)
    if valid:
        result["dispositions"][0]["reply_id"] = provider_reply
    elif len(attempts) > 1:
        result["dispositions"][0].update(dispatch_state="unknown", state="Ambiguous retained attempt records.", attempt_id=None, reply_id=None)
    if attempts and any(row["disposition"] == "before-dispatch" for row in result["cancellations"]):
        limits.append("Before-dispatch cancellation conflicts with a retained attempt; cancellation is not established.")
        result["dispositions"][0].update(dispatch_state="unknown", state="Cancellation and dispatch records conflict.", can_cancel=False)
    target = view.get("update_target") or {}
    target_matches = (valid and target.get("request_id") == request_id and _text(valid.get("native_id"))
                      and target.get("native_id") == valid["native_id"] == meta.get("native_id")
                      and _text(valid.get("turn_id")) and target.get("expected_turn_id") == valid["turn_id"])
    result["update_target"] = deepcopy(target) if target_matches else None
    if target.get("request_id") == request_id and not target_matches:
        limits.append("The session update target lacks consistent request/attempt context and was omitted.")
    project(result, None)
    # Retain only declarations explicitly attached to this input or one of its reply edges.
    report = (declarations or {}).get("report", {})
    links = (declarations or {}).get("view_links", {})
    relevant = [deepcopy(value) for value in report.get("obligations", [])
                if links.get(value["source"]["relationship"]) == meta["id"] and value["source"]["message"] in chosen]
    missing = bool((declarations or {}).get("error"))
    if missing:
        limits.append("Handling declarations were unavailable; unrecorded handling cannot be established.")
    result["dispositions"][0]["handling"] = dict(state="declared" if relevant else "unavailable" if missing else "unrecorded", declarations=relevant)
    if valid and valid["state"] in ("failed", "no-reply"):
        result["dispositions"][0]["state"] = "Recorded provider " + str(valid.get("outcome")) + "; linked-message and bound-reply evidence are separate."
    result["decision_summary"].update(association_complete=not unassigned, unassigned=unassigned)
    result["coverage"].update(association_complete=not limits, source="retained local snapshot; native completeness unverified")
    return result


def dispositions(view):
    rows = []
    for message in view["messages"]:
        if message["kind"] not in REQUESTS:
            continue
        ident = message["id"]
        attempt = next((row for row in view["attempts"] if row["request_id"] == ident), None)
        cancellation = next((row for row in view.get("cancellations", []) if row["request_id"] == ident), None)
        reply = next((row for row in view["messages"] if row["reply_to"] == ident and row["kind"] == "re"), None)
        if view["session"].get("history"):
            stage, label = "history", "recorded reply returned" if reply else "recorded request without linked reply; native execution unavailable"
        elif cancellation and cancellation["disposition"] == "before-dispatch":
            stage, label = "cancelled", "cancelled before dispatch"
        elif attempt is None and reply is not None:
            stage, label = "returned", "linked reply returned; native dispatch unrecorded"
        elif attempt is None:
            stage, label = "queued", "queued; no dispatch attempt"
        else:
            stage = attempt["state"]
            label = {
                "admitting": "submission attempted; native acknowledgement unconfirmed" if attempt["rpc_id"] else "reserved locally; native submission not recorded",
                "accepted": "provider acknowledged submission; reply pending",
                "executing": "native turn started; reply pending",
                "uncertain": "delivery unresolved; not retried",
                "unresolved": "delivery unresolved; not retried",
                "returned": "provider " + str(attempt["outcome"]) + "; reply returned",
                "failed": "provider " + str(attempt["outcome"]) + "; no reply. Send a new assignment if further work is needed.",
                "no-reply": "provider " + str(attempt["outcome"]) + "; no reply. Send a new assignment if further work is needed.",
            }.get(stage, "recorded provider disposition unavailable")
            if attempt.get("interruption_requested") and stage in ("admitting", "accepted", "executing"):
                label = "interruption requested; outcome pending; " + label
        rows.append(dict(request_id=ident, state=label, dispatch_state=stage,
                         attempt_id=attempt["id"] if attempt else None, reply_id=reply["id"] if reply else None,
                         public_update=attempt.get("public_update") if attempt else None, cancellation=cancellation,
                         can_cancel=not view["session"].get("history") and attempt is None and reply is None and cancellation is None))
    return rows


def project(view, declarations):
    """Add a current reading without dispatch, cursor changes or inferred handling."""
    counts = dict(responses_needed=0, submitted_unconfirmed=0, unavailable=0)
    for decision in view["decisions"]:
        if decision["state"] == "resolved":
            continue
        category = ("responses_needed" if decision.get("can_answer") else
                    "submitted_unconfirmed" if decision.get("response") is not None or decision["state"] in ("sending", "sent") else
                    "unavailable")
        counts[category] += 1
    view["decision_summary"] = counts
    rows = view.get("dispositions")
    if rows is None:
        rows = dispositions(view)
        view["dispositions"] = rows
    report = (declarations or {}).get("report", {})
    links = (declarations or {}).get("view_links", {})
    for row in rows:
        declared = [value for value in report.get("obligations", [])
                    if links.get(value["source"]["relationship"]) == view["session"]["id"]
                    and value["source"]["message"] in (row["request_id"], row["reply_id"])]
        row["handling"] = dict(state="declared" if declared else "unavailable" if (declarations or {}).get("error") else "unrecorded", declarations=declared)
    if view["session"].get("history"):
        view["current_work"] = rows[-1:]
    else:
        terminal = [row for row in rows if row["dispatch_state"] in ("returned", "failed", "no-reply", "cancelled")]
        latest = terminal[-1:]
        current = [row for row in rows if row in latest
                   or row["dispatch_state"] not in ("returned", "failed", "no-reply", "cancelled")
                   or any(value["state"] == "pending" for value in row["handling"]["declarations"])]
        priority = {"admitting": 0, "accepted": 0, "executing": 0, "uncertain": 1, "unresolved": 1, "queued": 2}
        view["current_work"] = sorted(current, key=lambda row: priority.get(row["dispatch_state"],
            3 if any(value["state"] == "pending" for value in row["handling"]["declarations"]) else 4))
