"""Probe the launched binary's schema and read-only endpoints without a model call."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .codex_runtime import runtime, supported_version

REQUIRES = {
    "model": {"thread/start": ("model", "config"), "thread/resume": ("model",)},
    "enrollment": {"thread/resume": ("threadId", "excludeTurns"), "thread/read": ("threadId",),
                   "thread/turns/list": ("threadId",)},
    "discovery": {"thread/list": ("cwd", "useStateDbOnly", "sourceKinds")},
    "active_turn_update": {"thread/read": ("threadId",), "turn/steer": ("threadId", "expectedTurnId", "input")},
}


def unavailable(reason):
    return {feature: dict(supported=False, reason=reason) for feature in REQUIRES}


def schema_capabilities(schema):
    methods = {}
    for variant in schema.get("oneOf", []):
        properties = variant.get("properties", {})
        names = properties.get("method", {}).get("enum", [])
        params = properties.get("params", {})
        reference = params.get("$ref", "")
        if reference.startswith("#/definitions/"):
            params = schema.get("definitions", {}).get(reference.removeprefix("#/definitions/"), {})
        for name in names:
            methods[name] = params.get("properties", {})
    result = {}
    for feature, required in REQUIRES.items():
        missing = [method if method not in methods else f"{method}.{field}"
                   for method, fields in required.items()
                   for field in (fields if method in methods else (None,))
                   if method not in methods or field not in methods[method]]
        result[feature] = dict(supported=not missing, reason="Missing protocol support: " + ", ".join(missing)
                               if missing else "Native protocol schema supports the required methods and fields.")
    return result


def probe(command, client):
    """Return evidence for this connection. A failed feature never disables unrelated features."""
    try:
        evidence = runtime(command)
        with tempfile.TemporaryDirectory(prefix="awkit-codex-probe-") as directory:
            result = subprocess.run([evidence["executable"], "app-server", "generate-json-schema", "--experimental",
                                     "--out", directory], capture_output=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if result.returncode:
                raise ValueError("Codex protocol schema probe failed.")
            schema = json.loads((Path(directory) / "ClientRequest.json").read_text(encoding="utf-8"))
            capabilities = schema_capabilities(schema)
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        return dict(capabilities=unavailable(str(exc)))
    # Bound the result and filter by project; discard all returned metadata.
    if capabilities["discovery"]["supported"]:
        try:
            response = client.discover_threads(dict(cwd=str(client.project), useStateDbOnly=True,
                archived=False, limit=1, modelProviders=[], sourceKinds=[]))
            if not isinstance(response, dict) or not isinstance(response.get("conversations"), list):
                raise ValueError("Unexpected listing response.")
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            capabilities["discovery"] = dict(supported=False, reason="Native thread/list probe failed.")
    evidence["capabilities"] = capabilities
    return evidence


def capability(evidence, feature):
    if not evidence.get("native_executable") or not supported_version(evidence.get("version")):
        return dict(supported=False, reason="A supported native Codex runtime has not been verified.")
    return evidence.get("capabilities", {}).get(feature, dict(supported=False, reason="Protocol capability has not been probed."))
