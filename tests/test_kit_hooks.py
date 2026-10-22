"""`awkit kit hooks` and `--remove` in three folders: one with no hook settings, one with Claude Code hook
settings and a husky commit hook, and one where the command runs twice. In each, what the project had stays
as it was, its hooks and awkit's both run, and `--remove` leaves the tree as it was before."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit import kit_hooks
from awkit.review import git
from support import child_env

AGENT_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"
USER_HANDLER = {"type": "command", "command": "echo checked"}


def tree(root):
    """Every file awkit may touch with its bytes and mode: the working tree and Git's hooks, exclude and config."""
    found = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        inside_git = relative == ".git" or relative.startswith(".git/")
        if inside_git and not (relative.startswith(".git/hooks/") or relative in (".git/info/exclude", ".git/config")):
            continue
        if path.is_dir():
            found[relative + "/"] = None
        else:
            found[relative] = (path.read_bytes(), path.stat().st_mode & 0o111 if os.name != "nt" else 0)
    return found


class KitHooks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        git(self.root, "init", "-q")
        git(self.root, "config", "core.autocrlf", "false")
        git(self.root, "config", "user.name", "owner")
        git(self.root, "config", "user.email", "owner@example.com")
        (self.root / "app.py").write_text("print(1)\n", encoding="utf-8")
        git(self.root, "add", "app.py")
        git(self.root, "commit", "-q", "-m", "First")

    def awkit(self, *args):
        result = subprocess.run([sys.executable, "-m", "awkit", "kit", "hooks", *args, str(self.root)],
                                capture_output=True, text=True, encoding="utf-8", env=child_env(), stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def commit(self, *messages):
        (self.root / "app.py").write_text("print(2)\n", encoding="utf-8")
        git(self.root, "add", "app.py")
        args = [part for message in messages for part in ("-m", message)]
        return subprocess.run(["git", "-C", str(self.root), "commit", "-q", *args], capture_output=True, text=True,
                              encoding="utf-8", env=child_env())

    def handlers(self, relative):
        data = json.loads((self.root / relative).read_text(encoding="utf-8"))
        return {event: [h["command"] for e in entries for h in e["hooks"]] for event, entries in data["hooks"].items()}

    def test_a_folder_without_hook_settings(self):
        before = tree(self.root)
        output = self.awkit()
        for name in ("rules.toml", ".claude/settings.local.json", ".codex/hooks.json", ".git/hooks/commit-msg"):
            self.assertIn(f"installed: {self.root / name}", output)
        self.assertTrue((self.root / "rules.toml").read_text(encoding="utf-8").startswith(kit_hooks.DRAFT_MARK))
        for relative in kit_hooks.SETTINGS.values():
            self.assertEqual(self.handlers(relative)["Stop"], ["awkit hook Stop --kit-hooks || exit 0"])
        # The commit-msg hook awkit wrote refuses an agent's trailer and lets the owner's commit through.
        refused = self.commit("Fix", AGENT_TRAILER)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Co-Authored-By", refused.stderr)
        git(self.root, "reset", "-q", "HEAD", "app.py")
        (self.root / "app.py").write_text("print(1)\n", encoding="utf-8")
        removed = self.awkit("--remove")
        self.assertIn("deleted:", removed)
        self.assertEqual(tree(self.root), before)

    def test_a_folder_with_claude_hooks_and_husky(self):
        # The project's own Claude Code handlers, in both settings files, and a husky commit-msg hook that
        # writes a file outside the repository when it runs.
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.json").write_text(json.dumps(
            {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [USER_HANDLER]}]}}, indent=4) + "\n", encoding="utf-8")
        (self.root / ".claude" / "settings.local.json").write_text(
            '{"model": "sonnet", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo 끝"}]}]}}',
            encoding="utf-8")
        ran = self.base / "husky-ran"
        husky = self.root / ".husky"
        (husky / "_").mkdir(parents=True)
        # Shell scripts keep LF on Windows too, as Git checks them out.
        (husky / "_" / "commit-msg").write_text('#!/bin/sh\nexec sh "$(dirname "$0")/../commit-msg" "$@"\n',
                                                encoding="utf-8", newline="\n")
        (husky / "commit-msg").write_text(f'#!/bin/sh\necho ran >> "{ran.as_posix()}"\n', encoding="utf-8",
                                          newline="\n")
        for path in (husky / "_" / "commit-msg", husky / "commit-msg"):
            path.chmod(0o755)
        git(self.root, "config", "core.hooksPath", ".husky/_")
        before = tree(self.root)
        output = self.awkit()
        self.assertIn(f"connected: {husky / 'commit-msg'}", output)
        # What the project had is still there, beside awkit's handlers.
        self.assertEqual((self.root / ".claude" / "settings.json").read_bytes(), before[".claude/settings.json"][0])
        local = json.loads((self.root / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(local["model"], "sonnet")
        self.assertEqual(self.handlers(".claude/settings.local.json")["Stop"],
                         ["echo 끝", "awkit hook Stop --kit-hooks || exit 0"])
        self.assertEqual((husky / "_" / "commit-msg").read_bytes(), before[".husky/_/commit-msg"][0])
        # Both commit hooks run: husky's writes its file, then awkit's line refuses the agent's trailer.
        refused = self.commit("Fix", AGENT_TRAILER)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Co-Authored-By", refused.stderr)
        self.assertTrue(ran.is_file())
        git(self.root, "reset", "-q", "HEAD", "app.py")
        (self.root / "app.py").write_text("print(1)\n", encoding="utf-8")
        self.awkit("--remove")
        self.assertEqual(tree(self.root), before)

    def test_running_twice(self):
        before = tree(self.root)
        self.awkit()
        once = tree(self.root)
        output = self.awkit()
        self.assertNotIn("installed:", output)
        self.assertEqual(output.count("kept existing hook:"), 4)
        self.assertEqual(tree(self.root), once)
        self.awkit("--remove")
        self.assertEqual(tree(self.root), before)
        # Removing again finds nothing of awkit's.
        self.awkit("--remove")
        self.assertEqual(tree(self.root), before)

    def test_a_changed_rules_file_is_deleted_only_when_the_person_agrees(self):
        self.awkit("--claude")
        rules = self.root / "rules.toml"
        rules.write_text(rules.read_text(encoding="utf-8") + "\n# the project's own rule\n", encoding="utf-8")
        kept = self.awkit("--remove")  # no terminal: nothing to ask, so the file stays
        self.assertIn("kept (changed since it was written)", kept)
        self.assertTrue(rules.is_file())
        self.assertFalse((self.root / ".claude" / "settings.local.json").exists())
        self.awkit("--claude")
        kit_hooks.remove(self.root, ask=lambda path: True)
        self.assertFalse(rules.exists())


if __name__ == "__main__":
    unittest.main()
