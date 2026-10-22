"""The kit installed in three layers: the user's computer (awkit, the guides, the skills in the user folder),
what a project commits (checks.toml and rules.toml) and what stays in the clone (hooks, .awkit/).

`kit init` calls `kit hooks`, whose files belong to the hook runner; most tests replace that call with a
stand-in that writes the files the two sides agreed on (rules.toml and a Git hook), so they check the rest
of init. The write guarantee and the end-to-end test call the real command.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from awkit import __version__, connect, environment
from awkit.doctor import diagnose
from awkit.kit_install import SITUATIONS, WORKFLOW, install_user_skills
from awkit.review import git
from support import child_env

ROOT = Path(__file__).resolve().parents[1]
NAMES = [name for name, *_ in (WORKFLOW, *SITUATIONS)]
# What the skills in the user folder add to every session: one line per skill.
SESSION_WORD_LIMIT = 150


def tree(root, skip=(".git",)):
    """Every file under `root` except the named top folders, as {relative path: bytes}."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] in skip or not path.is_file():
            continue
        found[relative.as_posix()] = path.read_bytes()
    return found


def git_state(root):
    """The files under .git that awkit may touch: the hooks and the exclude file."""
    folder = Path(root) / ".git"
    hooks = {p.name: p.read_bytes() for p in (folder / "hooks").iterdir() if not p.name.endswith(".sample")}
    exclude = folder / "info" / "exclude"
    return hooks, exclude.read_bytes() if exclude.is_file() else None


def candidates(root):
    """Paths Git would offer to commit: changed and untracked files, ignoring what is excluded."""
    lines = git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
    return sorted(line[3:] for line in lines)


class StandInHooks:
    """Stands in for `awkit kit hooks`: writes rules.toml and a commit-msg hook, and takes both out again on
    `--remove`. It records the arguments init passed."""

    def __init__(self):
        self.calls = []

    def __call__(self, top, *arguments):
        top = Path(top)
        self.calls.append(list(arguments))
        hook = top / ".git" / "hooks" / "commit-msg"
        if "--remove" in arguments:
            for path in (top / "rules.toml", hook):
                if path.exists():
                    path.unlink()
            return 0
        (top / "rules.toml").write_text("schema = 1\n", encoding="utf-8")
        hook.write_text("#!/bin/sh\n# awkit check commit\n", encoding="utf-8")
        return 0


class Isolated(unittest.TestCase):
    """A temporary home folder, so the user's real skill folders are never read or written."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        patch = mock.patch.dict(os.environ, {**child_env(), "HOME": str(self.home), "USERPROFILE": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)

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
        git(root, "commit", "-q", "--allow-empty", "-m", "First")
        return root

    def awkit(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-m", "awkit", *args], capture_output=True, text=True,
                              encoding="utf-8", env=os.environ.copy(), cwd=cwd, stdin=subprocess.DEVNULL)


KINDS = {
    "empty": {"README.md": "# Empty\n"},
    "claude": {"CLAUDE.md": "# 프로젝트 규칙\n\n- 테스트: `make test`\n", "MEMORY.md": "- 결정: A\n",
               ".claude/settings.json": '{\n  "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo done"}]}]}\n}\n'},
    "bundle": {"AGENTS.md": "# Agents\n\nUse superpowers.\n",
               **{f".claude/skills/{name}/SKILL.md": f"---\nname: {name}\ndescription: {name}\n---\n\nSteps.\n"
                  for name in ("brainstorming", "writing-plans", "executing-plans", "requesting-code-review")}},
}


class ProjectLayer(Isolated):
    def install(self, kind):
        root = self.repository(kind, KINDS[kind])
        before, state = tree(root), git_state(root)
        hooks = StandInHooks()
        with mock.patch.object(connect, "run_kit_hooks", hooks):
            report = connect.init(root)
        return root, before, state, hooks, report

    def remove(self, root, hooks, **options):
        with mock.patch.object(connect, "run_kit_hooks", hooks):
            return connect.remove(root, **options)

    def check_kind(self, kind, flags):
        root, before, state, hooks, report = self.install(kind)
        self.assertEqual(report["checks"], "created")
        # init committed nothing; what Git offers to commit is the completion conditions only.
        self.assertEqual(git(root, "rev-list", "--count", "HEAD"), "1")
        self.assertEqual(candidates(root), ["checks.toml", "rules.toml"])
        # The project's own files are byte for byte as they were.
        after = tree(root)
        for path, data in before.items():
            self.assertEqual(after[path], data, path)
        self.assertEqual(hooks.calls, [flags])
        table = connect.kit_table(root / "checks.toml")
        self.assertEqual(set(table), set(connect.KIT_KEYS))
        self.assertEqual(table["version"], __version__)
        self.assertIn(".awkit/", (root / ".git" / "info" / "exclude").read_text(encoding="utf-8"))
        self.assertLessEqual(max(environment.session_words(root).values()), SESSION_WORD_LIMIT)
        removed = self.remove(root, hooks, keep_records=False)
        self.assertEqual(hooks.calls[-1], ["--remove"])
        self.assertEqual(tree(root), before, removed)
        self.assertEqual(git_state(root), state)
        return table

    def test_empty_project(self):
        self.check_kind("empty", ["--git", "--claude", "--codex"])

    def test_project_with_claude_md_hooks_and_memory(self):
        table = self.check_kind("claude", ["--git", "--claude"])
        self.assertEqual(table["records"], "MEMORY.md")

    def test_project_with_a_skill_bundle(self):
        self.check_kind("bundle", ["--git", "--claude", "--codex"])

    def test_existing_checks_are_never_overwritten_only_completed(self):
        checks = 'schema = 1\n\n[[checks]]\nname = "unit"\nargv = ["make", "test"]\n\n[kit]\ndone = "CI is green"\n'
        root = self.repository("checks", {"checks.toml": checks})
        hooks = StandInHooks()
        with mock.patch.object(connect, "run_kit_hooks", hooks):
            report = connect.init(root)
            self.assertEqual(report["checks"], "filled")
            text = (root / "checks.toml").read_text(encoding="utf-8")
            self.assertTrue(text.startswith(checks.split("[kit]")[0]))
            table = connect.kit_table(root / "checks.toml")
            self.assertEqual(table["done"], "CI is green")
            self.assertEqual(table["version"], __version__)
            self.assertEqual(connect.init(root)["checks"], "kept")
            # Edited after init, checks.toml loses only the keys init added.
            (root / "checks.toml").write_text(text.replace('"unit"', '"units"'), encoding="utf-8")
            connect.remove(root, keep_records=False)
        self.assertEqual((root / "checks.toml").read_text(encoding="utf-8"), checks.replace('"unit"', '"units"'))

    def test_a_project_without_a_table_gets_one_appended(self):
        checks = 'schema = 1\n\n[[checks]]\nname = "unit"\nargv = ["make", "test"]\n'
        root = self.repository("plain", {"checks.toml": checks})
        before = tree(root)
        hooks = StandInHooks()
        with mock.patch.object(connect, "run_kit_hooks", hooks):
            self.assertEqual(connect.init(root)["checks"], "appended")
            self.assertTrue((root / "checks.toml").read_text(encoding="utf-8").startswith(checks + "\n"))
            connect.remove(root, keep_records=False)
        self.assertEqual(tree(root), before)

    def test_the_exclude_file_keeps_its_bytes(self):
        # Seen on Windows CI: the exclude line was added and removed in text mode, which rewrote every line of
        # .git/info/exclude with CRLF. A CRLF file shows the same defect everywhere, as LF.
        for newline in (b"\n", b"\r\n"):
            root = self.repository(f"exclude{len(newline)}", {"README.md": "# P\n"})
            exclude = root / ".git" / "info" / "exclude"
            exclude.write_bytes(b"# mine" + newline + b"*.tmp" + newline)
            before = exclude.read_bytes()
            hooks = StandInHooks()
            with mock.patch.object(connect, "run_kit_hooks", hooks):
                connect.init(root)
                self.assertEqual(exclude.read_bytes(), before + b".awkit/" + newline)
                connect.remove(root, keep_records=False)
            self.assertEqual(exclude.read_bytes(), before)

    def test_the_instruction_line_is_printed_not_written(self):
        root = self.repository("line", {"AGENTS.md": "# Agents\n"})
        before = (root / "AGENTS.md").read_bytes()
        with mock.patch.object(connect, "run_kit_hooks", StandInHooks()):
            from awkit.cli import _report_init
            with mock.patch("sys.stdout") as out:
                code = _report_init(connect.init(root))
        printed = "".join(call.args[0] for call in out.write.call_args_list)
        self.assertEqual(code, 0)
        self.assertIn(connect.INSTRUCTION_LINE, printed)
        self.assertIn("nothing was committed", printed)
        self.assertEqual((root / "AGENTS.md").read_bytes(), before)

    def test_real_hooks_and_init_restore_excludes_with_no_final_newline(self):
        for original in (None, b"", b"# mine\xff", b"# mine\r\n*.tmp\r\n"):
            with self.subTest(original=original):
                root = self.repository(f"real-exclude-{len(original) if original is not None else 'missing'}",
                                       {"README.md": "# P\n"})
                exclude = root / ".git/info/exclude"
                exclude.unlink(missing_ok=True)
                if original is not None:
                    exclude.write_bytes(original)
                self.assertEqual(self.awkit("kit", "init", cwd=root).returncode, 0)
                self.awkit("kit", "init", cwd=root)
                result = self.awkit("kit", "remove", "--delete-records", cwd=root)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(exclude.read_bytes() if exclude.exists() else None, original)


class UserRemoval(Isolated):
    def test_remove_user_restores_the_home_folder(self):
        mine = self.home / ".claude" / "skills" / "mine" / "SKILL.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("---\nname: mine\ndescription: mine\n---\n", encoding="utf-8")
        before = tree(self.home)
        self.assertEqual(self.awkit("kit", "skills").returncode, 0)
        result = self.awkit("kit", "remove", "--user", cwd=self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree(self.home), before)
        self.assertFalse((self.home / ".agents").exists())


class Doctor(Isolated):
    def findings(self, folder):
        return {f["item"]: f for f in diagnose(folder)}

    def test_layers_are_checked(self):
        root = self.repository("doc", {"checks.toml": 'schema = 1\n\n[kit]\nversion = "0.0.1"\n'})
        (root / "agent-work-kit").mkdir()
        (root / "agent-work-kit" / "workflow.md").write_text("# Workflow\n", encoding="utf-8")
        found = self.findings(root)
        self.assertEqual(found["claude user skills"]["status"], "warning")
        self.assertIn("awkit kit skills", found["claude user skills"]["fix"])
        self.assertEqual(found["hooks"]["status"], "warning")
        self.assertEqual(found["kit version"]["status"], "warning")
        self.assertIn("0.0.1", found["kit version"]["detail"])
        self.assertIn("delete the folder", found["copied kit folder"]["fix"])
        install_user_skills()
        (root / ".claude").mkdir()
        (root / ".claude" / "settings.json").write_text(
            '{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "awkit hook || exit 0"}]}]}}', encoding="utf-8")
        (root / "checks.toml").write_text(f'schema = 1\n\n[kit]\nversion = "{__version__}"\n', encoding="utf-8")
        found = self.findings(root)
        self.assertEqual(found["claude user skills"]["status"], "ok")
        self.assertNotIn("hooks", found)
        self.assertEqual(found["kit version"]["status"], "ok")
        self.assertIn("hold the guides now", found["copied kit folder"]["detail"])


class WriteGuarantee(Isolated):
    """awkit writes only to the places in connect.WRITES; memory and instruction files are only read. The real
    `kit hooks` runs here, since its files are part of what awkit writes."""

    def test_only_awkits_places_change(self):
        root = self.repository("writes", {
            "CLAUDE.md": "rules\n", "AGENTS.md": "agents\n", "MEMORY.md": "memory\n", ".beads/issues.jsonl": "{}\n",
            ".planning/STATE.md": "state\n", ".claude/skills/mine/SKILL.md": "---\nname: mine\ndescription: x\n---\n"})
        auto = environment.auto_memory(root)
        auto.mkdir(parents=True)
        (auto / "MEMORY.md").write_text("automatic\n", encoding="utf-8")
        read_only = ["CLAUDE.md", "AGENTS.md", "MEMORY.md", ".beads/issues.jsonl", ".planning/STATE.md"]
        stamps = {name: (root / name).stat().st_mtime_ns for name in read_only}
        stamps[str(auto / "MEMORY.md")] = (auto / "MEMORY.md").stat().st_mtime_ns
        project_before, home_before, state = tree(root), tree(self.home), git_state(root)
        for args in (("kit", "skills"), ("kit", "init", str(root))):
            result = self.awkit(*args, cwd=root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        allowed = [pattern.removeprefix("~/") for pattern in connect.WRITES]

        def outside(before, after, home):
            changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
            return [p for p in changed if not any(
                (p == a or (a.endswith("/") and p.startswith(a)) or (a.endswith("*") and p.startswith(a[:-1])))
                for a in allowed if a.startswith((".claude/skills", ".agents/skills", ".awkit/")) == home or a == ".awkit/")]

        project_after = tree(root)
        self.assertEqual(outside(project_before, project_after, False), [])
        home_files = {p: v for p, v in tree(self.home).items() if not p.startswith(".claude/projects/")}
        self.assertEqual(outside({p: v for p, v in home_before.items() if not p.startswith(".claude/projects/")},
                                 home_files, True), [])
        for name, stamp in stamps.items():
            path = Path(name) if Path(name).is_absolute() else root / name
            self.assertEqual(path.stat().st_mtime_ns, stamp, name)
        for args in (("kit", "remove", "--project", "--delete-records", str(root)), ("kit", "remove", "--user")):
            result = self.awkit(*args, cwd=root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(tree(root), project_before)
        self.assertEqual(git_state(root), state)
        self.assertEqual(tree(self.home), home_before)


class EndToEnd(Isolated):
    def test_empty_project_from_install_to_a_passing_done_check(self):
        self.check_project("empty", {})

    def test_existing_instructions_hooks_and_memory(self):
        self.check_project("claude", KINDS["claude"])

    def test_skill_bundle_and_completion_gate(self):
        self.check_project("bundle", {**KINDS["bundle"], "gate.json": '{"check": "make test"}\n'})

    def check_project(self, name, files):
        root = self.repository(name, files)
        result = self.awkit("kit", "init", cwd=root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(candidates(root), ["checks.toml", "rules.toml"])
        installed, state = tree(root), git_state(root)
        self.awkit("kit", "init", cwd=root)
        self.assertEqual(tree(root), installed)
        self.assertEqual(git_state(root), state)
        if name == "bundle":
            self.assertIn("--skip done-check", (root / ".codex/hooks.json").read_text(encoding="utf-8"))
        # Connecting: the agent fills the [kit] table with the user and adds the project's check.
        text = (root / "checks.toml").read_text(encoding="utf-8")
        text = text.replace('done = ""', 'done = "README.md says what the project is"')
        text = text.replace('recipient = ""', 'recipient = "the owner"')
        text += '\n[[checks]]\nname = "readme"\nargv = ["{python}", "-c", "import pathlib; assert pathlib.Path(\'README.md\').read_text().strip()"]\n'
        (root / "checks.toml").write_text(text, encoding="utf-8")
        doctor = {f["item"]: f for f in diagnose(root)}
        self.assertEqual(doctor["kit version"]["status"], "ok")
        self.assertNotIn("hooks", doctor)
        self.assertTrue((root / "rules.toml").is_file())
        self.assertEqual(self.awkit("check", "done", "--mark", "--repo", str(root)).returncode, 0)
        (root / "README.md").write_text("# First\n\nA project.\n", encoding="utf-8")
        self.assertEqual(self.awkit("check", "done", "--repo", str(root)).returncode, 1)
        # Exactly the documented recipe, with no test-only path filters.
        changed = (git(root, "diff", "--name-only", "--no-renames", "HEAD").splitlines()
                   + git(root, "ls-files", "--others", "--exclude-standard").splitlines())
        self.assertIn("README.md", changed)
        snap = self.awkit("review", "--repo", str(root), "snapshot", *changed)
        self.assertEqual(snap.returncode, 0, snap.stderr)
        checked = self.awkit("review", "--repo", str(root), "check", snap.stdout.strip(), "--config",
                             str(root / "checks.toml"))
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        done = self.awkit("check", "done", "--repo", str(root))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        (root / "README.md").write_text("# Later edit\n", encoding="utf-8")
        stale = self.awkit("check", "done", "--repo", str(root))
        self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)
        self.assertIn("README.md", stale.stdout + stale.stderr)


if __name__ == "__main__":
    unittest.main()
