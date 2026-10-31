"""Scoped Git-Bash conversion, adapter transport and unavailable-protection output."""

import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from unittest import mock

from awkit import commit_paths, hook_cli, hooks, rule_command
from support import child_env
from test_hooks import AGENT_TRAILER, Project

ADAPTER = [sys.executable, "-m", "awkit.rule_command", "check", "commit", "--hook"]


class PathComponents(unittest.TestCase):
    def test_literal_drive_relative_and_unc_meanings(self):
        pairs = [("/e/work/한 글", "E:/work/한 글"), ("/C", "C:/"),
                 ("C:/native", "C:/native"), (r"D:\native", r"D:\native"),
                 ("../relative space", "../relative space"), (".", "."),
                 ("//server/share/work", "//server/share/work"),
                 (r"\\server\share\work", r"\\server\share\work")]
        for given, expected in pairs:
            with self.subTest(given=given):
                self.assertEqual(commit_paths.component(given), expected)
        self.assertEqual(PureWindowsPath(commit_paths.join("C:/first", "/e/second")),
                         PureWindowsPath("E:/second"))

    def test_unsupported_or_ambiguous_paths_raise_without_a_converter(self):
        for value in ("/", "/home/name", "/mnt/e/work", "/cygdrive/e/work", r"\rooted", "E:relative",
                      "//server", "//wsl$/Ubuntu/home", "//wsl.localhost/Ubuntu/home", r"\\?\E:\work",
                      "~/repo", "$HOME/repo", "$(pwd)", "`pwd`", "repo*", "{one,two}", "", "a\x00b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                commit_paths.component(value)

    def test_cd_components_are_converted_before_joining(self):
        command = 'cd /c/first && cd /e/second && cd "space 한글" && git -C ../repo -C /d/final commit -m x'
        _, options, _, folder = hooks.git_commits(command, bash_paths=True)[0]
        self.assertEqual(PureWindowsPath(folder), PureWindowsPath("E:/second/space 한글"))
        self.assertEqual(options, [("-C", "../repo"), ("-C", "/d/final")])
        self.assertEqual(hooks.git_commits('cd -- /e/repo && git -C/d/sub commit -m x', bash_paths=True)[0][1],
                         [("-C", "/d/sub")])
        for command in ('cd -P /e/repo && git commit -m x', 'cd one two && git commit -m x',
                        'cd /home/name && git commit -m x', 'cd "unclosed && git commit -m x',
                        'git -C $(pwd) commit -m x', 'git -C$HOME commit -m x', 'cd && git commit -m x'):
            with self.subTest(command=command), self.assertRaises(ValueError):
                hooks.git_commits(command, bash_paths=True)

    def test_selection_requires_native_windows_and_raw_bash_identity(self):
        for platform in ("win32", "linux", "darwin"):
            for tool in ("Bash", "PowerShell", "exec_command", "bash", None):
                with self.subTest(platform=platform, tool=tool), mock.patch.object(sys, "platform", platform):
                    expected = "git-bash" if platform == "win32" and tool == "Bash" else None
                    self.assertEqual(commit_paths.selected("git-bash", {"tool_name": tool}), expected)
                    self.assertIsNone(commit_paths.selected(None, {"tool_name": tool}))


class PathTransport(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.payload = {"hook_event_name": "PreToolUse", "session_id": "paths", "cwd": str(self.root),
                        "tool_name": "Bash", "tool_input": {"command": "git commit -m fixture"}}
        self.settings = self.root / ".claude/settings.local.json"
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({"env": {commit_paths.ENV_KEY: "git-bash"}}), encoding="utf-8")
        self.rule(ADAPTER)

    def rule(self, argv, protocol=True):
        (self.root / "rules.toml").write_text(
            'schema = 1\n[[rules]]\nname = "identity"\nkind = "block"\nevents = ["PreToolUse"]\n'
            + ('command_protocol = "awkit-v1"\n' if protocol else "")
            + "command = " + json.dumps(argv) + '\n[[rules]]\nname = "other"\nkind = "inject"\n'
            'events = ["PreToolUse"]\nmessage = "Other rules continue."\n', encoding="utf-8")

    def run_hook(self, value="git-bash", result=None, payload=None):
        result = result or (0, json.dumps({"protocol": "awkit-v1", "status": "pass", "message": ""}))
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(hooks, "run_command", return_value=result) as run:
            output = hooks.run(json.dumps(payload or self.payload), self.root, bash_paths=value)
        return json.loads(output) if output else {}, run

    def test_only_exact_adapter_gets_selector_payload_and_environment_unchanged(self):
        before = copy.deepcopy(self.payload)
        environment = dict(os.environ)
        output, run = self.run_hook()
        self.assertEqual(run.call_args.args[:2], (ADAPTER + [commit_paths.ARGUMENT], before))
        self.assertEqual(self.payload, before)
        self.assertEqual(dict(os.environ), environment)
        self.assertIn("Other rules continue.", output["hookSpecificOutput"]["additionalContext"])
        for argv, protocol in ((ADAPTER, False), (ADAPTER[:-2] + ["done", "--hook"], True),
                               ([sys.executable, "-c", "print('custom')"], True),
                               (["custom-python", *ADAPTER[1:]], True)):
            with self.subTest(argv=argv, protocol=protocol):
                self.rule(argv, protocol)
                _, run = self.run_hook()
                self.assertEqual(run.call_args.args[0], argv)

    def test_missing_selection_or_tool_keeps_default_even_with_inherited_env(self):
        with mock.patch.dict(os.environ, {commit_paths.ENV_KEY: "git-bash"}):
            _, run = self.run_hook(value=None)
        self.assertEqual(run.call_args.args[0], ADAPTER)
        for tool in ("PowerShell", "exec_command", None):
            _, run = self.run_hook(payload={**self.payload, "tool_name": tool})
            self.assertEqual(run.call_args.args[0], ADAPTER)

    def test_invalid_selection_and_conflicting_arguments_warn_without_running_commit_check(self):
        for value in ("", "automatic", "GIT-BASH"):
            output, run = self.run_hook(value=value)
            run.assert_not_called()
            specific = output["hookSpecificOutput"]
            self.assertNotIn("permissionDecision", specific)
            self.assertIn("commit protection unavailable", specific["additionalContext"])
        self.rule(ADAPTER + ["--bash-paths=other"])
        output, run = self.run_hook()
        run.assert_not_called()
        self.assertIn("conflicting", output["hookSpecificOutput"]["additionalContext"])

    def test_selected_child_errors_are_visible_and_do_not_consume_later_findings(self):
        failures = [(0, json.dumps({"protocol": "awkit-v1", "status": "error", "message": "old child rejects argument"})),
                    (2, "unrecognized arguments"), (0, "bad envelope")]
        for result in failures:
            with self.subTest(result=result):
                output, _ = self.run_hook(result=result)
                self.assertIn("commit protection unavailable", output["hookSpecificOutput"]["additionalContext"])
                self.assertNotIn("permissionDecision", output["hookSpecificOutput"])
        finding = (0, json.dumps({"protocol": "awkit-v1", "status": "finding", "message": "identity differs"}))
        output, _ = self.run_hook(result=finding)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("identity differs", output["hookSpecificOutput"]["permissionDecisionReason"])
        self.payload["session_id"] = "unselected"
        output, _ = self.run_hook(value=None, result=failures[0])
        self.assertNotIn("commit protection unavailable", json.dumps(output))

    def test_selected_spawn_errors_and_timeout_warn_and_other_rules_continue(self):
        for exc in (OSError("unavailable interpreter"), subprocess.TimeoutExpired(ADAPTER, 20)):
            self.payload["session_id"] = type(exc).__name__
            with mock.patch.object(sys, "platform", "win32"), mock.patch.object(hooks, "run_command", side_effect=exc):
                output = json.loads(hooks.run(json.dumps(self.payload), self.root, bash_paths="git-bash"))
            self.assertIn("commit protection unavailable", output["hookSpecificOutput"]["additionalContext"])
            self.assertIn("Other rules continue.", output["hookSpecificOutput"]["additionalContext"])

    def test_entry_reads_setting_once_and_adapter_reads_only_explicit_argument(self):
        args = SimpleNamespace(group="hook", action="PreToolUse", root=self.root, skip=[], kit_rules=False)
        with mock.patch.dict(os.environ, {commit_paths.ENV_KEY: "git-bash"}), \
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps(self.payload))), \
                mock.patch.object(hooks, "run", return_value="") as run:
            self.assertEqual(hook_cli.run(args, None), 0)
        self.assertEqual(run.call_args.kwargs["bash_paths"], "git-bash")
        with mock.patch.dict(os.environ, {commit_paths.ENV_KEY: "git-bash"}), \
                mock.patch.object(hooks, "check_commit_command", return_value=[]) as check:
            result = rule_command.execute(ADAPTER[3:], json.dumps(self.payload))
        self.assertEqual(result["status"], "pass")
        self.assertIsNone(check.call_args.kwargs["bash_paths"])
        with mock.patch.object(hooks, "check_commit_command", return_value=[]) as check:
            result = rule_command.execute(ADAPTER[3:] + [commit_paths.ARGUMENT], json.dumps(self.payload))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(check.call_args.kwargs["bash_paths"], "git-bash")

    def test_adapter_rejects_selector_on_other_actions_and_conflicts(self):
        for argv in (["hook", "reply", commit_paths.ARGUMENT], ADAPTER[3:] + [commit_paths.ARGUMENT] * 2,
                     ADAPTER[3:] + ["--bash-paths=other"], ADAPTER[3:] + ["--bash-paths", "git-bash"]):
            with self.subTest(argv=argv):
                result = rule_command.execute(argv, json.dumps(self.payload))
                self.assertEqual(set(result), {"protocol", "status", "message"})
                self.assertEqual(result["status"], "error")

    def test_retained_environment_after_declaration_removal_or_change_is_unavailable(self):
        for index, contents in enumerate((None, b"\xff", "{}", '{"env": {}}', '{"env": {"AWKIT_CLAUDE_BASH_PATHS": "other"}}',
                                          "{broken", "[]", '{"env": "git-bash"}', '{"env": {"AWKIT_CLAUDE_BASH_PATHS": null}}')):
            with self.subTest(contents=contents):
                if contents is None:
                    self.settings.unlink(missing_ok=True)
                elif isinstance(contents, bytes):
                    self.settings.write_bytes(contents)
                else:
                    self.settings.write_text(contents, encoding="utf-8")
                self.payload["session_id"] = f"declaration-{index}"
                with mock.patch.object(hooks, "check_commit_command", side_effect=AssertionError("identity lookup")), \
                        mock.patch.object(commit_paths, "component", side_effect=AssertionError("path conversion")):
                    output, run = self.run_hook()
                run.assert_not_called()
                specific = output["hookSpecificOutput"]
                self.assertNotIn("permissionDecision", specific)
                self.assertIn("commit protection unavailable", specific["additionalContext"])
                self.assertIn("Other rules continue.", specific["additionalContext"])

    def test_unreadable_declaration_is_commit_only_and_default_gates_do_not_read_it(self):
        read_text = Path.read_text
        def unreadable(path, *args, **kwargs):
            if path == self.settings:
                raise PermissionError("fixture")
            return read_text(path, *args, **kwargs)
        with mock.patch.object(Path, "read_text", unreadable):
            output, run = self.run_hook()
        run.assert_not_called()
        self.assertIn("unreadable", output["hookSpecificOutput"]["additionalContext"])
        for value, tool, platform in ((None, "Bash", "win32"), ("git-bash", "PowerShell", "win32"),
                                       ("git-bash", None, "win32"), ("git-bash", "Bash", "linux")):
            with self.subTest(value=value, tool=tool, platform=platform), \
                    mock.patch.object(commit_paths, "declaration_error", side_effect=AssertionError("settings read")), \
                    mock.patch.object(sys, "platform", platform), \
                    mock.patch.object(hooks, "run_command", return_value=(0, json.dumps({
                        "protocol": "awkit-v1", "status": "pass", "message": ""}))) as run:
                hooks.run(json.dumps({**self.payload, "tool_name": tool}), self.root, bash_paths=value)
            self.assertEqual(run.call_args.args[0], ADAPTER)

    def test_only_resolved_rule_root_declaration_counts_without_parent_or_cwd_search(self):
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "rules.toml").write_bytes((self.root / "rules.toml").read_bytes())
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(hooks, "run_command") as run:
            output = hooks.run(json.dumps({**self.payload, "cwd": str(nested)}), nested, bash_paths="git-bash")
        run.assert_not_called()
        self.assertIn("commit protection unavailable", output)
        # Explicit root selects the existing rule root, even if the tool cwd names another project.
        output, run = self.run_hook(payload={**self.payload, "cwd": str(nested)})
        self.assertEqual(run.call_args.args[0], ADAPTER + [commit_paths.ARGUMENT])
        self.assertNotIn("commit protection unavailable", json.dumps(output))


@unittest.skipUnless(sys.platform == "win32", "real native Windows paths")
class NativePaths(Project):
    def test_canonical_bash_and_relative_forms_find_same_history_and_findings(self):
        space = self.root / "space 한글"
        space.mkdir()
        drive = self.root.as_posix()
        bash = "/" + drive[0].lower() + drive[2:]
        forms = [f'cd "{drive}" && git', f'cd "{bash}" && git',
                 f'git -C "{drive}"', f'git -C "{bash}"',
                 f'cd "{bash}" && cd "space 한글" && cd .. && git',
                 f'git -C "{bash}" -C "space 한글" -C ..',
                 f'git -C "{drive}" -C "{bash}"', f'git -C"{bash}"', 'cd . && git']
        for suffix in ('commit -m ordinary', f'commit --author="Other <other@example.test>" -m x -m "{AGENT_TRAILER}"'):
            baseline = None
            for prefix in forms:
                with self.subTest(prefix=prefix, suffix=suffix):
                    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(self.root),
                               "tool_input": {"command": prefix + " " + suffix}}
                    result = rule_command.execute(ADAPTER[3:] + [commit_paths.ARGUMENT], json.dumps(payload))
                    if baseline is None:
                        baseline = result
                    self.assertEqual(result, baseline)
            self.assertEqual(baseline["status"], "pass" if suffix == 'commit -m ordinary' else "finding")
            if baseline["status"] == "finding":
                self.assertIn("other@example.test", baseline["message"])
                self.assertIn("Co-Authored-By", baseline["message"])

    def test_missing_repository_and_ambiguous_paths_never_pass(self):
        for path in ("/z/awkit-nonexistent-fixture-path", "/mnt/c/project", "/home/owner", "C:relative"):
            payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(self.root),
                       "tool_input": {"command": f'git -C "{path}" commit -m x'}}
            result = rule_command.execute(ADAPTER[3:] + [commit_paths.ARGUMENT], json.dumps(payload))
            self.assertEqual(result["status"], "error", result)

    def test_unc_is_preserved_and_other_tools_keep_their_existing_interpretation(self):
        for tool, path, expected in (("Bash", "//server/share/repo", PureWindowsPath("//server/share/repo")),
                                     ("PowerShell", "/e/repo", PureWindowsPath(self.root.drive + "/e/repo")),
                                     ("exec_command", "/e/repo", PureWindowsPath(self.root.drive + "/e/repo"))):
            payload = {"tool_name": tool, "cwd": str(self.root),
                       "tool_input": {"command": f'git -C "{path}" commit --author="Fixture <fixture@example.test>" -m x'}}
            with mock.patch("awkit.checks.commit_identity", return_value={"problems": []}) as identity:
                self.assertEqual(hooks.check_commit_command(payload, strict=True, bash_paths="git-bash"), [])
            self.assertEqual(PureWindowsPath(identity.call_args.args[0]), expected)

    def test_real_outer_child_round_trip_uses_environment_only_at_entry(self):
        settings = self.root / ".claude/settings.local.json"
        settings.parent.mkdir()
        settings.write_text(json.dumps({"env": {commit_paths.ENV_KEY: "git-bash"}}), encoding="utf-8")
        drive = self.root.as_posix()
        bash = "/" + drive[0].lower() + drive[2:]
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(self.root), "session_id": "native",
                   "tool_input": {"command": f'git -C "{bash}" commit -m x -m "{AGENT_TRAILER}"'}}
        result = subprocess.run([sys.executable, "-m", "awkit", "hook"], cwd=self.root,
                                env=child_env(**{commit_paths.ENV_KEY: "git-bash"}), input=json.dumps(payload),
                                text=True, encoding="utf-8", capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("Co-Authored-By", output["permissionDecisionReason"])
