"""Declared provider behavior, distinct from runtime and conversation availability."""

CLAUDE_EFFORTS = ("low", "medium", "high", "xhigh", "max")


def describe(provider):
    codex = provider == "codex"
    native = provider in ("codex", "claude")
    discovery_reason = ("Requires an existing initialized supported connection in this project and home." if codex else
                        "Claude conversation discovery is unavailable: its listing reads transcripts and does not establish safe enrollment.")
    enrollment_reason = ("Exact-ID enrollment checks identity, native ownership and returned policy." if codex else
                         "Claude enrollment of another conversation is unavailable; exclusive ownership has not been established. Owned-session recovery remains available.")
    update_reason = ("Requires the verified runtime and the exact observed active turn." if codex else
                     "Claude active-turn steering is unavailable. Wait for its result before a new assignment; interruption remains separate.")
    if not native:
        discovery_reason = enrollment_reason = update_reason = "Stored channel history has no native connection or input control."
    result = dict(
        model=dict(supported=native, admission="exact-receipt" if codex else "submitted-request",
                   reason="Configuration must match the native creation/resume receipt; execution remains unverified." if codex else
                   "Model aliases are retained as requested; a later native model observation is separate and may differ."),
        effort=dict(supported=native, values=None if codex else list(CLAUDE_EFFORTS), requires_model=True,
                    reason="Omission inherits native configuration. Explicit effort must match its returned configuration." if codex else
                    "Omission inherits native configuration. Native model support may cap or downgrade effort; effective effort remains unverified. Equal labels across providers do not imply equal behavior."),
        permissions=dict(field="sandbox" if codex else "permission_mode",
                         reason="Approval requests go to this screen. The conversation shows the scope actually returned by Codex." if codex else
                         "Claude uses native default approvals and project instructions. This does not establish a Codex sandbox or Windows network restriction."),
        operations=dict(create=dict(supported=native), status=dict(supported=True), send=dict(supported=native),
                        cancel=dict(supported=native), interrupt=dict(supported=native), decide=dict(supported=native),
                        resume=dict(supported=native), discovery=dict(supported=codex, reason=discovery_reason),
                        enrollment=dict(supported=codex, reason=enrollment_reason),
                        active_turn_update=dict(supported=codex, reason=update_reason)))
    if not native:
        result["model"].update(admission="unavailable", reason=discovery_reason)
        result["effort"].update(values=None, reason=discovery_reason)
        result["permissions"].update(field=None, reason=discovery_reason)
    return result
