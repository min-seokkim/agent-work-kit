"""Explicit bundled results keep execution errors out of rule block state."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from awkit import hooks, rule_command
from support import child_env
from test_hook_rules import Project


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = {"hook_event_name": "Stop", "session_id": "adapter", "cwd": str(self.root)}

    def execute(self, argv, payload=None):
        return rule_command.execute(argv, json.dumps(self.payload if payload is None else payload))

    def test_actual_writing_pass_and_finding_have_unambiguous_envelopes(self):
        path = self.root / "guide.md"
        path.write_text("A guide.\n", encoding="utf-8")
        self.assertEqual(self.execute(["check", "writing", str(path)])["status"], "pass")
        path.write_text("A\u2014B.\n", encoding="utf-8")
        result = self.execute(["check", "writing", str(path)])
        self.assertEqual(result["status"], "finding")
        self.assertIn("em-dash", result["message"])

    def test_parser_unsupported_action_and_required_input_errors_are_not_passes(self):
        for argv in (["hook", "old-action"], ["kit", "init", str(self.root / "unexpected")], ["check", "commit"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.execute(argv)["status"], "error")
        for raw in ("", "{bad", "[]", "{}", '{"hook_event_name":"Stop","stop_hook_active":"yes"}'):
            with self.subTest(raw=raw):
                self.assertEqual(rule_command.execute(["hook", "reply"], raw)["status"], "error")
        self.assertFalse((self.root / "unexpected").exists())
        self.assertEqual(self.execute(["check", "commit", "--hook"])["status"], "error")

    def test_injected_internal_and_import_failures_are_errors_with_bounded_messages(self):
        with mock.patch.object(rule_command, "_dispatch", side_effect=RuntimeError("x" * 3000)):
            result = self.execute(["hook", "reply"])
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(result["message"]), 1000)
        with mock.patch.dict(sys.modules, {"awkit.cli": None}):
            self.assertEqual(self.execute(["hook", "reply"])["status"], "error")

    def test_intentional_unknown_guide_evidence_is_a_completed_noop(self):
        self.payload["last_assistant_message"] = "# Example\n" + chr(0xAC00) * 600
        self.assertEqual(self.execute(["hook", "reply"])["status"], "pass")

    def test_capability_probe_and_cli_error_output_are_single_json_values(self):
        command = [sys.executable, "-m", "awkit.rule_command"]
        probe = subprocess.run(command + ["--capabilities"], capture_output=True, text=True, encoding="utf-8", env=child_env())
        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertEqual(json.loads(probe.stdout)["protocol"], "awkit-v1")
        output = subprocess.run(command + ["hook", "old-action"], input=json.dumps(self.payload),
                                capture_output=True, text=True, encoding="utf-8", env=child_env())
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual(json.loads(output.stdout)["status"], "error")
        self.assertEqual(output.stderr, "")

    def test_strict_commit_error_does_not_change_legacy_helper(self):
        payload = {**self.payload, "tool_input": {"command": "git commit -m fixture"}}
        self.assertEqual(hooks.check_commit_command(payload), [])
        with self.assertRaises(ValueError):
            hooks.check_commit_command(payload, strict=True)
        self.assertEqual(self.execute(["check", "commit", "--hook"], payload)["status"], "error")
        with mock.patch.object(hooks, "git_commits", side_effect=ValueError("unparsable")):
            self.assertEqual(hooks.check_commit_command(payload), [])
            with self.assertRaises(ValueError):
                hooks.check_commit_command(payload, strict=True)

    def test_main_restores_stdin_and_writes_one_envelope(self):
        original = sys.stdin
        output = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(self.payload))), contextlib.redirect_stdout(output):
            self.assertEqual(rule_command.main(["hook", "reply"]), 0)
        self.assertIs(sys.stdin, original)
        self.assertEqual(json.loads(output.getvalue())["status"], "pass")


class ProtocolRules(Project):
    def rule(self, argv, protocol=True, kind="verify", event="Stop"):
        selector = 'command_protocol = "awkit-v1"\n' if protocol else ""
        text = 'schema = 1\n[[rules]]\nname = "probe"\nkind = ' + json.dumps(kind)
        text += '\nevents = [' + json.dumps(event) + ']\n' + selector + 'command = ' + json.dumps(argv) + '\n'
        (self.root / "rules.toml").write_text(text, encoding="utf-8")

    def bundled(self, *argv):
        return [sys.executable, "-m", "awkit.rule_command", *argv]

    def violation(self):
        path = self.root / "bad.md"
        path.write_text("A\u2014B.\n", encoding="utf-8")
        return self.bundled("check", "writing", str(path))

    def assert_error_then_finding(self, argv, session="probe"):
        self.rule(argv)
        self.assertIsNone(self.event("Stop", session=session))
        self.assertEqual(self.log()[-1]["decision"], "error")
        self.rule(self.violation())
        output = self.event("Stop", session=session)
        self.assertEqual(output["decision"], "block")
        self.assertEqual(self.log()[-1]["decision"], "block")
        self.assertIsNone(self.event("Stop", session=session))

    def test_unknown_action_startup_and_old_child_failures_preserve_later_block(self):
        cases = [self.bundled("hook", "old-action"),
                 [sys.executable, "-c", "raise RuntimeError('injected child crash')"],
                 [sys.executable, "-m", "awkit.absent_old_child_adapter"],
                 [sys.executable, "-m", "awkit", "check", "writing", str(self.root / "bad.md")]]
        self.violation()
        for index, argv in enumerate(cases):
            with self.subTest(index=index):
                self.assert_error_then_finding(argv, session=f"error{index}")

    def test_malformed_wrong_version_contaminated_and_unsuccessful_results_are_errors(self):
        valid = {"protocol": "awkit-v1", "status": "finding", "message": "fixture"}
        cases = [(0, "bad"), (0, json.dumps({**valid, "protocol": "awkit-v0"})),
                 (0, json.dumps({**valid, "status": "unsupported"})),
                 (0, json.dumps({**valid, "message": 1})), (0, json.dumps({**valid, "extra": True})),
                 (0, json.dumps({**valid, "message": "x" * 1001})),
                 (0, "prefix\n" + json.dumps(valid)), (1, json.dumps(valid))]
        for index, (code, output) in enumerate(cases):
            with self.subTest(index=index):
                self.rule(self.bundled("hook", "reply"))
                with mock.patch.object(hooks, "run_command", return_value=(code, output)):
                    self.assertIsNone(self.event("Stop", session=f"shape{index}"))
                self.assertEqual(self.log()[-1]["decision"], "error")
                self.rule(self.violation())
                self.assertEqual(self.event("Stop", session=f"shape{index}")["decision"], "block")

    def test_real_findings_and_passes_keep_existing_once_semantics(self):
        clean = self.root / "clean.md"
        clean.write_text("Clean.\n", encoding="utf-8")
        self.rule(self.bundled("check", "writing", str(clean)))
        self.assertIsNone(self.event("Stop"))
        self.assertEqual(self.log(), [])
        self.rule(self.violation())
        self.assertEqual(self.event("Stop")["decision"], "block")
        self.assertIsNone(self.event("Stop"))

    def test_execution_error_does_not_consume_inject_opportunity(self):
        self.rule(self.bundled("hook", "old-action"), kind="inject", event="SessionStart")
        self.assertIsNone(self.event("SessionStart"))
        self.rule(self.violation(), kind="inject", event="SessionStart")
        output = self.event("SessionStart")
        self.assertIn("probe", output["hookSpecificOutput"]["additionalContext"])

    def test_unmarked_custom_exit_and_decision_json_behavior_is_unchanged(self):
        code = "import json; print(json.dumps({'protocol':'awkit-v1','status':'error','message':'custom'})); raise SystemExit(1)"
        self.rule([sys.executable, "-c", code], protocol=False)
        self.assertEqual(self.event("Stop")["decision"], "block")
        self.rule([sys.executable, "-c", "print('{\"decision\":\"allow\"}')"], protocol=False)
        self.assertIsNone(self.event("Stop", session="allow"))
        self.rule([sys.executable, "-c", "print('{\"decision\":\"block\",\"reason\":\"custom\"}')"], protocol=False)
        self.assertEqual(self.event("Stop", session="json")["decision"], "block")

    def test_older_runner_field_recognition_rejects_selector_visibly(self):
        self.rule(self.violation())
        with mock.patch.object(hooks, "FIELDS", hooks.FIELDS - {"command_protocol"}):
            self.assertIsNone(self.event("Stop"))
        self.assertEqual(self.log()[-1]["decision"], "error")
        self.assertIn("command_protocol", self.log()[-1]["reason"])
        self.assertEqual(self.event("Stop")["decision"], "block")

    def test_selector_requires_supported_value_and_a_command(self):
        self.rule(self.violation())
        path = self.root / "rules.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('command_protocol = "awkit-v1"', 'command_protocol = "unknown"'), encoding="utf-8")
        self.assertIsNone(self.event("Stop"))
        self.assertEqual(self.log()[-1]["decision"], "error")
