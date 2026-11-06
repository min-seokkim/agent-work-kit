"""Minimum native runtime admission and independent protocol-feature failures."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from awkit.codex_capabilities import capability, probe, schema_capabilities
from awkit.codex_runtime import runtime, supported_version
from awkit.session_capabilities import describe
from support import codex_evidence


def protocol():
    fields = {"thread/start": ["model", "config", "threadSource", "sessionStartSource"], "thread/resume": ["threadId", "excludeTurns", "cwd", "sandbox",
              "approvalPolicy", "approvalsReviewer", "developerInstructions"],
              "thread/read": ["threadId"], "thread/list": ["cwd", "useStateDbOnly", "sourceKinds"],
              "thread/turns/list": ["threadId", "limit", "sortDirection", "itemsView"],
              "thread/items/list": ["threadId", "turnId", "limit", "sortDirection"],
              "turn/steer": ["threadId", "expectedTurnId", "input"]}
    return {"oneOf": [{"properties": {"method": {"enum": [method]}, "params": {
        "properties": dict.fromkeys(names, {"type": "string"})}}} for method, names in fields.items()]}


class RuntimeTests(unittest.TestCase):
    def test_minimum_orders_prereleases_numerically_and_accepts_stable(self):
        for version in ("0.164.0-alpha.11.1", "0.164.0-alpha.11.2", "0.164.0-beta.1", "0.164.0", "0.167.0-alpha.3.2"):
            self.assertTrue(supported_version("codex-cli " + version), version)
        for version in (None, "garbage", "0.163.99", "0.164.0-alpha.11", "0.164.0-alpha.9.9"):
            self.assertFalse(supported_version(version), version)

    def test_new_native_hash_is_evidence_not_an_admission_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "codex"
            executable.write_bytes(b"\x7fELFfictional native header")
            with patch("awkit.codex_runtime.subprocess.run", return_value=SimpleNamespace(
                    returncode=0, stdout="codex-cli 0.167.0-alpha.3.2\n")):
                evidence = runtime([str(executable)])
            self.assertTrue(evidence["native_executable"])
            self.assertEqual(len(evidence["executable_sha256"]), 64)
            with patch("awkit.codex_runtime.subprocess.run", return_value=SimpleNamespace(
                    returncode=0, stdout="codex-cli 0.163.0\n")), self.assertRaises(ValueError):
                runtime([str(executable)])

    def test_missing_method_disables_only_its_feature_and_status_names_it(self):
        schema = protocol()
        schema["oneOf"].pop()  # turn/steer
        capabilities = schema_capabilities(schema)
        self.assertFalse(capabilities["active_turn_update"]["supported"])
        self.assertTrue(all(capabilities[key]["supported"] for key in ("model", "enrollment", "discovery")))
        status = describe("codex", codex_evidence(capabilities=capabilities))
        self.assertIn("turn/steer", status["operations"]["active_turn_update"]["reason"])
        self.assertTrue(status["model"]["supported"])

    def test_missing_field_or_unprobed_runtime_cannot_enable_feature(self):
        schema = protocol()
        del schema["oneOf"][0]["properties"]["params"]["properties"]["config"]
        self.assertFalse(schema_capabilities(schema)["model"]["supported"])
        self.assertFalse(capability(codex_evidence(capabilities={}), "model")["supported"])

    def test_recovery_requires_full_history_and_summary_fallback(self):
        for missing in ("thread/items/list", "thread/turns/list"):
            schema = protocol()
            schema["oneOf"] = [row for row in schema["oneOf"] if row["properties"]["method"]["enum"] != [missing]]
            result = schema_capabilities(schema)
            for feature in ("enrollment", "model"):
                self.assertFalse(result[feature]["supported"])
                self.assertIn(missing, result[feature]["reason"])
            self.assertTrue(result["discovery"]["supported"])
            self.assertTrue(result["active_turn_update"]["supported"])

    def test_history_classification_has_its_own_capability(self):
        schema = protocol()
        del schema["oneOf"][0]["properties"]["params"]["properties"]["threadSource"]
        capabilities = schema_capabilities(schema)
        self.assertFalse(capabilities["native_history"]["supported"])
        self.assertTrue(capabilities["model"]["supported"])
        status = describe("codex", codex_evidence(capabilities=capabilities))
        self.assertIn("threadSource", status["operations"]["native_history"]["reason"])

    def test_model_resume_does_not_require_an_unused_model_override(self):
        schema = protocol()
        self.assertNotIn("model", schema["oneOf"][1]["properties"]["params"]["properties"])
        self.assertTrue(schema_capabilities(schema)["model"]["supported"])

    def test_status_preserves_schema_failure_and_runtime_refusal_reasons(self):
        with patch("awkit.codex_capabilities.runtime", return_value=codex_evidence(executable="fictional")), \
                patch("awkit.codex_capabilities.subprocess.run", return_value=SimpleNamespace(returncode=1)):
            result = probe(["fictional"], None)
        self.assertEqual(result["version"], codex_evidence()["version"])
        self.assertIn("schema probe failed", describe("codex", result)["model"]["reason"])
        for reason in ("script wrappers are unsupported", "Codex requires version 0.164.0-alpha.11.1 or newer"):
            with patch("awkit.codex_capabilities.runtime", side_effect=ValueError(reason)):
                result = probe(["fictional"], None)
            self.assertEqual(describe("codex", result)["model"]["reason"], reason)

    def test_probe_uses_only_schema_and_metadata_listing(self):
        calls = []

        def generate(argv, **kwargs):
            self.assertEqual(argv[1:4], ["app-server", "generate-json-schema", "--experimental"])
            (Path(argv[-1]) / "ClientRequest.json").write_text(json.dumps(protocol()), encoding="utf-8")
            return SimpleNamespace(returncode=0)

        def listing(params):
            calls.append(params)
            return dict(conversations=[])

        client = SimpleNamespace(project=Path.cwd(), discover_threads=listing)
        with patch("awkit.codex_capabilities.runtime", return_value=codex_evidence(executable="fictional")), \
                patch("awkit.codex_capabilities.subprocess.run", side_effect=generate):
            result = probe(["fictional"], client)
        self.assertTrue(all(row["supported"] for row in result["capabilities"].values()))
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["useStateDbOnly"])
        client.discover_threads = lambda params: (_ for _ in ()).throw(RuntimeError("unsupported"))
        with patch("awkit.codex_capabilities.runtime", return_value=codex_evidence(executable="fictional")), \
                patch("awkit.codex_capabilities.subprocess.run", side_effect=generate):
            result = probe(["fictional"], client)
        self.assertFalse(result["capabilities"]["discovery"]["supported"])
        self.assertTrue(result["capabilities"]["model"]["supported"])
