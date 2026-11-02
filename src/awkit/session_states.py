"""The states of managed sessions, their delivery attempts and their decisions, in one place.

Each tuple is a set of states some code tests for; the store refuses a session state not listed in SESSION.
SQL uses the same tuples through `sql`, so a state renamed here changes every query.
"""

# A session (awkit_session.data["state"]).
SESSION = ("creating", "reconnecting", "idle", "waiting for idle", "submitting", "accepted", "running",
           "decision needed", "unknown")
DISPATCHABLE = ("idle", "waiting for idle")  # the dispatcher may send the next request
SENDABLE = ("idle", "waiting for idle", "running", "accepted", "decision needed", "submitting")  # a new request may be queued
WORKING = ("running", "accepted", "decision needed")  # a turn is under way and can take an exact-turn update

# A delivery attempt (awkit_delivery.state).
ATTEMPT_RUNNING = ("admitting", "accepted", "executing")  # sent or being sent, outcome not yet known
ATTEMPT_LIVE = ATTEMPT_RUNNING + ("uncertain",)  # the session's one active attempt
ATTEMPT_RECONNECTABLE = ATTEMPT_LIVE + ("unresolved",)  # moved to a new connection on reconnect
ATTEMPT_STARTED = ("accepted", "executing")  # the provider took the turn
ATTEMPT_FINISHED = ("returned", "failed", "no-reply")
ATTEMPT = ATTEMPT_RECONNECTABLE + ATTEMPT_FINISHED

# A decision the provider asked for (awkit_decisions.state).
DECISION_OPEN = ("pending", "sending", "sent", "uncertain")
DECISION = DECISION_OPEN + ("route unavailable", "resolved", "unresolved")


def sql(states):
    """A SQL tuple literal for an IN clause; the states are constants above, never user input."""
    return "(" + ",".join(f"'{state}'" for state in states) + ")"
