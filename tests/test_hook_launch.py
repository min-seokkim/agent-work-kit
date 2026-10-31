"""Run generated commands through real shells, including Windows PowerShell 5.1 (F11)."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit import hooks, kit_hooks
from support import child_env


class HookLaunch(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.bin = self.root / "bin with spaces"
        self.bin.mkdir()
        self.env = child_env()
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env.get("PATH", "")
        (self.root / "rules.toml").write_text(
            'schema = 1\n[[rules]]\nname = "probe"\nkind = "inject"\n'
            'events = ["PreToolUse"]\nmessage = "The hook received stdin."\n', encoding="utf-8")
        if os.name == "nt":
            self.shells = [[shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive", "-Command"],
                           [os.environ["COMSPEC"], "/d", "/c"]]
            (self.bin / "awkit.cmd").write_text(
                f'@"{sys.executable}" -m awkit %*\r\n', encoding="utf-8")
        else:
            self.shells = [["/bin/sh", "-c"]]
            entry = self.bin / "awkit"
            entry.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -m awkit "$@"\n',
                             encoding="utf-8")
            entry.chmod(0o755)

    def run_hook(self, shell, command, payload):
        return subprocess.run([*shell, command], cwd=self.root, input=payload,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=self.env, timeout=30)

    def test_generated_commands_deliver_stdin_and_json_in_real_shells(self):
        for shell_index, shell in enumerate(self.shells):
            for command_index, command in enumerate((kit_hooks.handler_command("PreToolUse"), hooks.hook_command())):
                with self.subTest(shell=shell, command=command):
                    payload = json.dumps({"session_id": f"probe-{shell_index}-{command_index}", "cwd": str(self.root),
                                          "hook_event_name": "PreToolUse", "tool_name": "Bash",
                                          "tool_input": {"command": "echo probe"}})
                    result = self.run_hook(shell, command, payload)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    output = json.loads(result.stdout)
                    self.assertIn("The hook received stdin.", output["hookSpecificOutput"]["additionalContext"])

    def test_bad_input_is_handled_by_runner_without_shell_fallback(self):
        for shell in self.shells:
            with self.subTest(shell=shell):
                result = self.run_hook(shell, kit_hooks.handler_command("PreToolUse"), "{broken")
                self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
        log = (self.root / ".awkit/hooks.ndjson").read_text(encoding="utf-8")
        self.assertIn("unreadable hook input", log)

    def test_missing_executable_is_visible_as_launch_failure(self):
        self.env["PATH"] = str(self.root / "missing-bin")
        for shell in self.shells:
            with self.subTest(shell=shell):
                result = self.run_hook(shell, kit_hooks.handler_command("PreToolUse"), "{}")
                self.assertNotEqual(result.returncode, 0)


class Migration(unittest.TestCase):
    def test_only_exact_generated_commands_are_migrated(self):
        old = ["awkit hook || exit 0", "awkit hook --kit-rules --skip done-check || exit 0",
               "awkit hook Stop --kit-hooks --skip writing-reply || exit 0"]
        custom = ["awkit hook --root custom || exit 0", "awkit hook && echo checked || exit 0",
                  "echo awkit hook || exit 0", "awkit hook Stop --kit-hooks || exit 7"]
        handlers = [{"type": "command", "command": command, "timeout": 12} for command in old + custom]
        data = {"model": "mine", "hooks": {"Stop": [{"matcher": "mine", "hooks": handlers}]}}
        self.assertTrue(hooks.migrate_commands(data))
        self.assertEqual([h["command"] for h in handlers],
                         [c.removesuffix(" || exit 0") for c in old] + custom)
        self.assertTrue(all(h["timeout"] == 12 for h in handlers))
        self.assertFalse(hooks.migrate_commands(data))

    def test_install_migrates_existing_settings_without_duplicate_and_remove_restores(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".codex/hooks.json"
            path.parent.mkdir()
            original = json.dumps({"hooks": {event: [{"hooks": [
                {"type": "command", "command": f"awkit hook {event} --kit-hooks || exit 0"},
                {"type": "command", "command": "echo mine"}]}] for event in kit_hooks.EVENTS}})
            path.write_text(original, encoding="utf-8")
            kit_hooks.install(root, use_git=False, use_claude=False)
            installed = path.read_bytes()
            for event, groups in json.loads(installed)["hooks"].items():
                self.assertEqual([h["command"] for h in groups[0]["hooks"]],
                                 [f"awkit hook {event} --kit-hooks", "echo mine"])
            kit_hooks.install(root, use_git=False, use_claude=False)
            self.assertEqual(path.read_bytes(), installed)
            kit_hooks.remove(root, ask=lambda path: True)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_existing_claude_shared_settings_are_migrated_without_local_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".claude/settings.json"
            path.parent.mkdir()
            original = json.dumps({"hooks": {event: [{"hooks": [
                {"type": "command", "command": "awkit hook || exit 0"}]}] for event in kit_hooks.EVENTS}})
            path.write_text(original, encoding="utf-8")
            kit_hooks.install(root, use_git=False, use_codex=False)
            self.assertNotIn("||", path.read_text(encoding="utf-8"))
            local = json.loads((root / ".claude/settings.local.json").read_text(encoding="utf-8"))
            self.assertEqual(local["hooks"], {})  # The local selector adds no duplicate handler.
            self.assertEqual(local["env"], {"AWKIT_CLAUDE_BASH_PATHS": "git-bash"})
            kit_hooks.remove(root, ask=lambda path: True)
            self.assertEqual(path.read_text(encoding="utf-8"), original)
