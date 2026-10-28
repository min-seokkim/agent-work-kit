"""Creation-only explicit Codex configuration and conservative recovery admission."""

from pathlib import Path


def validate(model, provider, reasoning_effort=None):
    if reasoning_effort is not None:
        if provider != "codex" or model is None:
            raise ValueError("Reasoning effort requires an explicit model for a new Codex conversation.")
        if (not isinstance(reasoning_effort, str) or not 1 <= len(reasoning_effort) <= 200
                or not reasoning_effort.isprintable() or any(character.isspace() for character in reasoning_effort)):
            raise ValueError("Reasoning effort must contain 1 to 200 visible non-whitespace characters.")
    if model is None:
        return
    if provider != "codex":
        raise ValueError("Explicit model IDs are supported only for new Codex conversations.")
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
