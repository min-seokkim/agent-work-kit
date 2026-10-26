"""Read-only dispositions from existing exchanges, attempts and explicit declarations."""

from .channel import REQUESTS


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
