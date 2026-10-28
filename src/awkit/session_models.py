"""Explicit provider requests with distinct configuration-observation contracts."""

from pathlib import Path

from .session_capabilities import describe


def validate(model, provider, reasoning_effort=None):
    if reasoning_effort is not None:
        if provider not in ("codex", "claude") or model is None:
            raise ValueError("Reasoning effort requires an explicit model for a new supported conversation.")
        if (not isinstance(reasoning_effort, str) or not 1 <= len(reasoning_effort) <= 200
                or not reasoning_effort.isprintable() or any(character.isspace() for character in reasoning_effort)):
            raise ValueError("Reasoning effort must contain 1 to 200 visible non-whitespace characters.")
        values = describe(provider)["effort"]["values"]
        if values is not None and reasoning_effort not in values:
            raise ValueError("This provider supports these reasoning effort values: " + ", ".join(values) + ".")
    if model is None:
        return
    if provider not in ("codex", "claude"):
        raise ValueError("Explicit model IDs require a supported session provider.")
    if (not isinstance(model, str) or not 1 <= len(model) <= 200 or not model.isprintable()
            or any(character.isspace() for character in model)):
        raise ValueError("Model ID must contain 1 to 200 visible non-whitespace characters.")


def selected(meta):
    return meta.get("provider") == "codex" and not meta.get("enrollment") and "model_selection" in meta


def ready(meta):
    return not selected(meta) or meta["model_selection"].get("state") == "matched"


def hold(store):
    meta = store.metadata()
    if selected(meta):
        store.update(model_selection=dict(meta["model_selection"], state="held"))


def claude_options(meta):
    """Reapply only the saved request of this awkit-owned Claude session."""
    selection = meta.get("model_selection")
    if not selection or meta.get("provider") != "claude" or meta.get("enrollment"):
        return {}
    validate(selection["requested"], "claude", selection.get("requested_effort"))
    options = dict(model=selection["requested"])
    if "requested_effort" in selection:
        options["effort"] = selection["requested_effort"]
    return options


def claude_submitted(store):
    selection = store.metadata().get("model_selection")
    if selection:
        store.update(model_selection=dict(selection, state="submitted"))


def claude_observe(store, model):
    selection = store.metadata().get("model_selection")
    if selection:
        observation = dict(model=model, provider=None, reasoning_effort=None, source="native system/init")
        store.update(model_selection=dict(selection, creation=selection.get("creation") or observation,
                                           latest=observation))


def verify_runtime(controller, provider):
    from .codex_enrollment import EXECUTABLE_SHA256, VERSION

    evidence = controller.client
    if (evidence.get("version") != VERSION or evidence.get("executable_sha256") != EXECUTABLE_SHA256
            or evidence.get("version_exit") != 0 or len(controller.command) != 1
            or tuple(evidence.get("command", ())) != tuple(controller.command)
            or tuple(getattr(provider, "command", ())) != tuple(controller.command)
            or Path(getattr(provider, "project", "")).resolve() != controller.project):
        raise ValueError("Explicit model selection requires the verified Codex runtime; work remains held.")


def observe(store, result, *, creation):
    if not isinstance(result, dict):
        raise ValueError("Native response returned no configuration observation; work remains held.")
    meta = store.metadata()
    selection = meta["model_selection"]
    observation = dict(model=result.get("model"), provider=result.get("modelProvider"),
                       reasoning_effort=result.get("reasoningEffort"),
                       source="thread/start response" if creation else "thread/resume response")
    expected = observation if creation else selection.get("creation")
    matched = (observation["model"] == selection["requested"] and isinstance(observation["model"], str)
               and isinstance(observation["provider"], str) and bool(observation["provider"].strip())
               and isinstance(expected, dict) and expected.get("model") == selection["requested"]
               and observation["provider"] == expected.get("provider"))
    if "requested_effort" in selection:
        matched = matched and observation["reasoning_effort"] == selection["requested_effort"]
    updated = dict(selection, latest=observation, state="matched" if matched else "held")
    if creation:
        updated["creation"] = observation
    store.update(model_selection=updated)
    if not matched:
        raise ValueError("Returned Codex configuration does not match the explicit creation selection; work remains held.")
