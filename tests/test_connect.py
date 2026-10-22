"""Connecting the kit to projects that already have their own agent setup, and taking it out again.

Three kinds of project: an empty one, one with CLAUDE.md, hooks and MEMORY.md, and one with a method
bundle, a completion gate and husky. For each: the words awkit adds to every session, the project's own
files unchanged apart from what awkit adds, hooks chained so both run, and after `kit remove` a tree
equal to the one before. init itself (the three layers) is tested in test_layers.py; here it runs without
calling `kit hooks`, and the hooks are installed directly.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from awkit import connect, environment
from awkit.checks import GIT_MARK, install_git_hook, install_hooks
from awkit.review import git
from support import child_env

ROOT = Path(__file__).resolve().parents[1]
# What the kit may add to every session in a project: one line per skill.
SESSION_WORD_LIMIT = 250
AGENT_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"


def tree(root):
    """Every file under `root` except Git's own folder, as {relative path: bytes}."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] == ".git" or not path.is_file():
            continue
        found[relative.as_posix()] = path.read_bytes()
    return found


def git_hooks(root):
    folder = Path(root) / ".git" / "hooks"
    return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file() and not p.name.endswith(".sample")}


class Kinds(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        # Claude Code's automatic memory lives under the home folder; keep the test's own.
        home = mock.patch.dict(os.environ, {**child_env(), "HOME": str(self.base / "home"),
                                            "USERPROFILE": str(self.base / "home")})
        home.start()
        self.addCleanup(home.stop)

    def repository(self, name, files):
        root = self.base / name
        root.mkdir()
        git(root, "init", "-q")
        git(root, "config", "core.autocrlf", "false")
        git(root, "config", "user.name", "owner")
        git(root, "config", "user.email", "owner@example.com")
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "First")
        return root

    def connect_everything(self, root):
        report = connect.init(root, hooks=False)
        changes = connect.Changes(root)
        hooks = install_hooks(root, None, True, True, True, changes)
        changes.save()
        return report, hooks

    def commit(self, root, *message):
        (root / "change.txt").write_text(str(len(message)) + os.urandom(4).hex(), encoding="utf-8")
        git(root, "add", "change.txt")
        return subprocess.run(["git", "-C", str(root), "commit", "-q", *sum((["-m", m] for m in message), [])],
                              capture_output=True, text=True, encoding="utf-8")

    def undo_commit(self, root):
        """Take back the test commit without touching the files awkit changed."""
        git(root, "reset", "-q", "--mixed", "HEAD~1")
        (root / "change.txt").unlink()

    def assert_removed_cleanly(self, root, before, hooks_before):
        report = connect.remove(root, hooks=False)
        self.assertEqual(tree(root), before, report)
        self.assertEqual(git_hooks(root), hooks_before)
        self.assertEqual(report["awkit_folder"], "deleted")

    def test_empty_project(self):
        root = self.repository("empty", {"README.md": "# Empty\n"})
        before, hooks_before = tree(root), git_hooks(root)
        report, _ = self.connect_everything(root)
        # With no instruction file, init writes none: the project gets checks.toml and nothing to read.
        self.assertEqual(report["checks"], "created")
        self.assertFalse((root / "AGENTS.md").exists() or (root / "CLAUDE.md").exists())
        words = environment.session_words(root)
        self.assertLessEqual(max(words.values()), SESSION_WORD_LIMIT)
        self.assertEqual(tree(root)["README.md"], before["README.md"])
        self.assert_removed_cleanly(root, before, hooks_before)

    def test_project_with_claude_md_hooks_and_memory(self):
        settings = ('{\n    "permissions": {"allow": ["Bash(ls)"]},\n    "hooks": {\n        "Stop": [\n'
                    '            {"hooks": [{"type": "command", "command": "echo 끝"}]}\n        ]\n    }\n}\n')
        root = self.repository("claude", {
            "CLAUDE.md": "# 프로젝트 규칙\n\n- 테스트: `make test`\n- 커밋 메시지는 한국어로 쓴다", "MEMORY.md": "- 결정: A\n",
            ".claude/settings.json": settings})
        mine = root / ".git" / "hooks" / "commit-msg"
        mine.write_text('#!/bin/sh\necho "$1" >> "$(git rev-parse --git-dir)/mine.log"\n', encoding="utf-8",
                        newline="\n")
        mine.chmod(0o755)
        before, hooks_before = tree(root), git_hooks(root)
        scan_memory = environment.memory(root)
        self.assertEqual([m["path"] for m in scan_memory], ["MEMORY.md"])
        report, hooks = self.connect_everything(root)
        # CLAUDE.md is left as it is; the [kit] table points to MEMORY.md for records.
        self.assertEqual(tree(root)["CLAUDE.md"], before["CLAUDE.md"])
        self.assertEqual(connect.kit_table(root / "checks.toml")["records"], "MEMORY.md")
        self.assertFalse((root / "AGENTS.md").exists())
        words = environment.session_words(root)
        self.assertLessEqual(words["claude"], SESSION_WORD_LIMIT)
        self.assertEqual(tree(root)["MEMORY.md"], before["MEMORY.md"])  # read only
        # The settings keep their handler, indentation and characters; only awkit's handlers are added.
        text = (root / ".claude" / "settings.json").read_text(encoding="utf-8")
        data = json.loads(text)
        self.assertEqual(data["hooks"]["Stop"][0], {"hooks": [{"type": "command", "command": "echo 끝"}]})
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})
        self.assertIn('    "permissions"', text)
        self.assertIn("끝", text)
        self.assertEqual(sum(1 for e in data["hooks"]["Stop"] for h in e["hooks"] if "awkit hook" in h["command"]), 1)
        # The existing Git hook keeps running, and the identity check runs after it.
        self.assertEqual(hooks["connected"], [f"{mine} (after its own commands)"])
        self.assertIn(GIT_MARK, mine.read_text(encoding="utf-8"))
        self.assertTrue(mine.read_bytes().startswith(hooks_before["commit-msg"]))
        refused = self.commit(root, "Change", AGENT_TRAILER)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Co-Authored-By", refused.stderr)
        self.assertEqual(self.commit(root, "Change").returncode, 0)
        self.assertEqual((root / ".git" / "mine.log").read_text(encoding="utf-8").count("\n"), 2)
        self.undo_commit(root)
        (root / ".git" / "mine.log").unlink()
        self.assert_removed_cleanly(root, before, hooks_before)

    def test_project_with_a_method_bundle_and_a_completion_gate(self):
        files = {"AGENTS.md": "# Agents\n\nUse superpowers.\n", "gate.json": '{"check": "npm test", "rounds": 2}\n',
                 ".husky/commit-msg": 'echo "$1" >> .git/husky.log\n',
                 ".husky/_/commit-msg": '#!/bin/sh\nsh -e "$(dirname "$0")/../commit-msg" "$@"\n'}
        for name in ("brainstorming", "writing-plans", "executing-plans", "requesting-code-review"):
            files[f".claude/skills/{name}/SKILL.md"] = f"---\nname: {name}\ndescription: {name}\n---\n\nSteps.\n"
        root = self.repository("bundle", files)
        (root / ".husky" / "_" / "commit-msg").chmod(0o755)
        git(root, "config", "core.hooksPath", ".husky/_")
        before, hooks_before = tree(root), git_hooks(root)
        found = environment.detect(root)
        self.assertEqual([b["name"] for b in found["bundles"]], ["superpowers"])
        self.assertEqual(found["gates"], [{"name": "kkamak", "evidence": "gate.json"}])
        self.assertEqual(found["hooks"]["git"]["manager"], "husky")
        report, hooks = self.connect_everything(root)
        self.assertEqual(tree(root)["AGENTS.md"], before["AGENTS.md"])
        self.assertEqual(tree(root)[".claude/skills/brainstorming/SKILL.md"], before[".claude/skills/brainstorming/SKILL.md"])
        words = environment.session_words(root)
        self.assertLessEqual(max(words.values()), SESSION_WORD_LIMIT)
        # The gate already does what the done check does, so the handlers skip it and say why.
        commands = {h["command"] for e in json.loads((root / ".claude" / "settings.json").read_text("utf-8"))["hooks"]
                    .values() for x in e for h in x["hooks"]}
        self.assertEqual(commands, {"awkit hook --kit-rules --skip done-check || exit 0"})
        self.assertTrue(any("kkamak (gate.json)" in note for note in hooks["notes"]))
        # husky runs .husky/commit-msg; the line goes there, after the project's own command.
        self.assertEqual(hooks["connected"], [f"{root / '.husky' / 'commit-msg'} (after its own commands; husky runs it)"])
        self.assertFalse(any(GIT_MARK in p.read_text("utf-8") for p in (root / ".husky" / "_").iterdir()))
        self.assertNotEqual(self.commit(root, "Change", AGENT_TRAILER).returncode, 0)
        self.assertEqual(self.commit(root, "Change").returncode, 0)
        self.assertEqual((root / ".git" / "husky.log").read_text(encoding="utf-8").count("\n"), 2)
        self.undo_commit(root)
        (root / ".git" / "husky.log").unlink()
        self.assert_removed_cleanly(root, before, hooks_before)


class Writes(unittest.TestCase):
    """awkit writes only to .awkit/, checks.toml and its hook entries and line; instruction and memory files
    are read and never written."""

    def test_only_awkits_own_places_change(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(os.environ, child_env()):
            root = Path(temporary).resolve() / "project"
            root.mkdir()
            git(root, "init", "-q")
            for name, text in {"CLAUDE.md": "rules\n", "MEMORY.md": "memory\n", ".beads/issues.jsonl": "{}\n",
                               ".planning/STATE.md": "state\n", ".claude/settings.json": "{}\n"}.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text, encoding="utf-8", newline="\n")
            before = tree(root)
            stamps = {name: (root / name).stat().st_mtime_ns for name in ("MEMORY.md", ".beads/issues.jsonl",
                                                                             ".planning/STATE.md")}
            connect.init(root, hooks=False)
            changes = connect.Changes(root)
            install_hooks(root, None, True, True, True, changes)
            changes.save()
            # The hook runner, on an event, writes its log and state under .awkit/ only.
            from awkit import hooks
            hooks.run(json.dumps({"hook_event_name": "PreToolUse", "session_id": "s", "cwd": str(root),
                                  "tool_name": "WebSearch", "tool_input": {"query": "x"}}), kit_rules=True)
            after = tree(root)
            changed = {path for path in after if before.get(path) != after[path]}
            allowed = {"checks.toml", ".claude/settings.json", ".codex/hooks.json"}
            for path in changed:
                self.assertTrue(path in allowed or path.startswith(".awkit/"), path)
            self.assertEqual(after["CLAUDE.md"], before["CLAUDE.md"])
            for name, stamp in stamps.items():
                self.assertEqual((root / name).stat().st_mtime_ns, stamp, name)
                self.assertEqual(after[name], before[name])
            self.assertTrue({p for p in changed if p.startswith(".awkit/")})
            connect.remove(root, keep_records=False, hooks=False)
            self.assertEqual(tree(root), before)

    def test_line_endings_and_characters_are_kept(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            git(root, "init", "-q")
            original = "# 규칙\r\n\r\n- 한 줄\r\n".encode()
            (root / "AGENTS.md").write_bytes(original)
            checks = b'schema = 1\r\n\r\n[[checks]]\r\nname = "test"\r\nargv = ["make", "test"]\r\n'
            (root / "checks.toml").write_bytes(checks)
            settings = b'{\r\n\t"hooks": {}\r\n}\r\n'
            (root / ".codex").mkdir()
            (root / ".codex" / "hooks.json").write_bytes(settings)
            connect.init(root, hooks=False)
            changes = connect.Changes(root)
            install_hooks(root, None, False, False, True, changes)
            changes.save()
            self.assertEqual((root / "AGENTS.md").read_bytes(), original)
            table = (root / "checks.toml").read_bytes()
            self.assertTrue(table.startswith(checks + b"\r\n" + connect.KIT_MARK.encode()))
            self.assertNotIn(b"\n", table.replace(b"\r\n", b""))
            hooks_json = (root / ".codex" / "hooks.json").read_bytes()
            self.assertIn(b'\r\n\t"hooks"', hooks_json)
            # Edited after init, the files lose only awkit's part.
            (root / "checks.toml").write_bytes(table.replace(b'"test"', b'"tests"'))
            connect.remove(root, hooks=False)
            self.assertEqual((root / "checks.toml").read_bytes(), checks.replace(b'"test"', b'"tests"'))
            self.assertEqual((root / ".codex" / "hooks.json").read_bytes(), settings)

    def test_pre_commit_hook_is_chained_through_its_legacy_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            git(root, "init", "-q")
            hook = root / ".git" / "hooks" / "commit-msg"
            generated = ("#!/usr/bin/env bash\n# File generated by pre-commit: https://pre-commit.com\n"
                         'exec pre-commit hook-impl --hook-type=commit-msg -- "$@"\n')
            hook.write_text(generated, encoding="utf-8", newline="\n")
            path, what, note = install_git_hook(root)
            self.assertEqual((path.name, what), ("commit-msg.legacy", "installed"))
            self.assertIn("pre-commit runs it", note)
            self.assertEqual(hook.read_text(encoding="utf-8"), generated)

    def test_a_hook_that_ends_with_exec_gets_the_line_before_its_last_line(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            git(root, "init", "-q")
            hook = root / ".git" / "hooks" / "commit-msg"
            hook.write_text('#!/bin/sh\nset -e\nexec npx commitlint --edit "$1"\n', encoding="utf-8", newline="\n")
            _, what, note = install_git_hook(root)
            lines = hook.read_text(encoding="utf-8").splitlines()
            self.assertEqual(what, "connected")
            self.assertIn(GIT_MARK, lines[2])
            self.assertTrue(lines[3].startswith("exec npx"))
            self.assertIn("before its last line", note)


class Command(unittest.TestCase):
    def run_awkit(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-m", "awkit", *args], capture_output=True, text=True,
                              encoding="utf-8", env=child_env(), cwd=cwd, stdin=subprocess.DEVNULL)

    def test_init_scan_and_remove_from_the_command_line(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "project"
            root.mkdir()
            git(root, "init", "-q")
            git(root, "config", "user.name", "owner")
            git(root, "config", "user.email", "owner@example.com")
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "First")
            before = tree(root)
            scan = self.run_awkit("kit", "scan", str(root))
            self.assertEqual(scan.returncode, 0, scan.stderr)
            # The words the kit adds come first, before anything else is reported.
            self.assertTrue(scan.stderr.startswith("awkit adds "), scan.stderr)
            self.assertEqual(next(iter(json.loads(scan.stdout))), "session_words")
            init = self.run_awkit("kit", "init", str(root))
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertIn("created: ", init.stdout)
            self.assertIn("words added to every session:", init.stdout)
            self.assertIn("nothing was committed", init.stdout)
            # Nothing was committed and AGENTS.md is untouched; .awkit stays on this machine.
            self.assertEqual(git(root, "rev-list", "--count", "HEAD"), "1")
            self.assertEqual(tree(root)["AGENTS.md"], before["AGENTS.md"])
            self.assertIn("?? checks.toml", git(root, "status", "--porcelain").splitlines())
            self.assertNotIn(".awkit", git(root, "status", "--porcelain"))
            self.assertEqual(self.run_awkit("kit", "init", str(root)).returncode, 2)  # nothing new
            scanned = json.loads(self.run_awkit("kit", "scan", str(root)).stdout)
            self.assertEqual(scanned["kit"]["mode"], "connected")
            self.assertTrue(scanned["session_words"]["measured"])
            # A record in .awkit/ is kept without a terminal to ask, and said so.
            (root / ".awkit" / "reviews").mkdir()
            removed = self.run_awkit("kit", "remove", str(root))
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertIn("keeping .awkit/", removed.stderr)
            self.assertTrue((root / ".awkit" / "reviews").is_dir())
            self.assertFalse((root / ".awkit" / "installed.json").exists())
            self.assertEqual({k: v for k, v in tree(root).items() if not k.startswith(".awkit/")}, before)

    def test_init_commits_nothing_and_leaves_instruction_changes_alone(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            git(root, "init", "-q")
            git(root, "config", "user.name", "owner")
            git(root, "config", "user.email", "owner@example.com")
            (root / "CLAUDE.md").write_text("# Rules\n", encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "First")
            (root / "CLAUDE.md").write_text("# Rules\n\nunsaved\n", encoding="utf-8")
            init = self.run_awkit("kit", "init", str(root))
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertIn("nothing was committed", init.stdout)
            self.assertEqual(git(root, "rev-list", "--count", "HEAD"), "1")
            self.assertEqual((root / "CLAUDE.md").read_text(encoding="utf-8"), "# Rules\n\nunsaved\n")

    def test_remove_without_the_record_finds_awkits_markers(self):
        # Another clone has the committed section and skills but not .awkit/installed.json.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            git(root, "init", "-q")
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            before = tree(root)
            connect.init(root, hooks=False)
            draft = (root / "checks.toml").read_text(encoding="utf-8")
            (root / ".awkit" / "installed.json").unlink()
            report = connect.remove(root, hooks=False)
            self.assertFalse(report["recorded"])
            # Without the record, checks.toml may be the project's own by now: only the [kit] table goes.
            after = tree(root)
            self.assertEqual(after.pop("checks.toml").decode("utf-8"), draft[:draft.index(connect.KIT_MARK)].rstrip("\n") + "\n")
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
