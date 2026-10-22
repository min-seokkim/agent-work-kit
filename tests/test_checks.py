"""Each test replays a recorded occurrence from docs/failures.md that the check must catch."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit.checks import check_text, check_writing, commit_identity, done, install_hooks
from awkit.review import check, git, snapshot
from support import child_env

ROOT = Path(__file__).resolve().parents[1]
OWNER = ("-c", "user.name=owner", "-c", "user.email=owner@example.com")


def run(*args, cwd, stdin=None, env=None):
    return subprocess.run([sys.executable, "-m", "awkit", *args], cwd=cwd, input=stdin, capture_output=True,
                          text=True, encoding="utf-8", env=env or child_env())


class Repository(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "core.autocrlf", "false")
        git(self.repo, "config", "user.name", "owner")
        git(self.repo, "config", "user.email", "owner@example.com")

    def commit(self, name, text, message="Change", env=None):
        (self.repo / name).write_text(text, encoding="utf-8")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", message, env=env)


class CommitIdentityTests(Repository):
    def test_agent_identity_and_trailers_are_refused(self):
        # F9: commits authored as "Claude" with Co-Authored-By lines in a repository whose history
        # had only the owner's commits without trailers.
        self.commit("a.txt", "a", "First")
        self.commit("b.txt", "b", "Second\n\nBody text.")
        message = "Third\n\nBody.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nClaude-Session: https://x\n"
        # As a commit-msg hook: the owner's identity with the agent's trailers.
        pending = commit_identity(self.repo, message=message)
        self.assertEqual(pending["author"], "owner <owner@example.com>")
        self.assertEqual(len(pending["problems"]), 2)
        self.assertTrue(commit_identity(self.repo, message="Third\n\nPlain body.\n# a comment\n")["ok"])
        # As a CI check of a pushed commit: the agent's identity and trailers.
        env = dict(os.environ, GIT_AUTHOR_NAME="Claude", GIT_AUTHOR_EMAIL="noreply@anthropic.com")
        self.commit("c.txt", "c", message, env=env)
        report = commit_identity(self.repo, rev="HEAD")
        self.assertFalse(report["ok"])
        self.assertEqual(report["trailers"], ["Co-Authored-By", "Claude-Session"])
        self.assertEqual(len(report["problems"]), 3)
        self.assertIn("noreply@anthropic.com", report["problems"][0])

    def test_history_and_configuration_allow_what_the_project_uses(self):
        self.assertTrue(commit_identity(self.repo, message="First\n\nSigned-off-by: owner <owner@example.com>")["ok"])
        self.commit("a.txt", "a", "First\n\nSigned-off-by: owner <owner@example.com>")
        self.assertTrue(commit_identity(self.repo, message="Next\n\nSigned-off-by: owner <owner@example.com>")["ok"])
        git(self.repo, "config", "user.email", "new@example.com")
        self.assertFalse(commit_identity(self.repo, message="Next")["ok"])
        git(self.repo, "config", "--add", "awkit.allowAuthor", "New@Example.com")
        self.assertTrue(commit_identity(self.repo, message="Next")["ok"])

    def test_installed_git_hook_blocks_the_commit(self):
        self.commit("a.txt", "a", "First")
        written, kept = install_hooks(self.repo, sys.executable, use_git=True)
        self.assertEqual((len(written), kept), (1, []))
        (self.repo / "b.txt").write_text("b", encoding="utf-8")
        git(self.repo, "add", "b.txt")
        env = child_env()
        blocked = subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "Add b",
                                  "-m", "Co-Authored-By: Claude <noreply@anthropic.com>"],
                                 capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("Co-Authored-By", blocked.stderr)
        allowed = subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "Add b"],
                                 capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertEqual(install_hooks(self.repo, sys.executable, use_git=True), ([], written))  # kept


class WritingTests(unittest.TestCase):
    def test_patterns_wrong_on_one_sighting_fail(self):
        # F13: the README rewrite used em dashes. F14: middle dots joining Korean words.
        findings = check_text("Agent Work Kit — a kit for agents.\n\n행사 담당자·강연자가 확인합니다.\n")
        self.assertEqual([(f["line"], f["level"], f["pattern"]) for f in findings],
                         [(1, "error", "em-dash"), (3, "error", "middle-dot")])

    def test_mixed_polite_endings_in_one_document_fail(self):
        # F14, F32: a server guide switched from -세요 to -시오.
        text = "# 운영 안내\n\n서버를 켜기 전에 전원을 확인하세요.\n\n로그를 백업하십시오.\n"
        findings = check_text(text)
        self.assertEqual([(f["level"], f["pattern"]) for f in findings], [("error", "mixed-endings")])
        self.assertEqual(check_text("전원을 확인하세요.\n로그를 백업하세요.\n"), [])

    def test_code_quotes_and_examples_are_not_prose(self):
        text = ("Avoid `—` and \"not just X\" in prose.\n\n> Here's a quoted sample — kept.\n\n"
                "```text\n담당자·강연자\n```\n\n[link](a—b.md) `-세요` and `-시오`.\n")
        self.assertEqual(check_text(text), [])

    def test_judgment_patterns_warn_without_failing(self):
        report_text = "Here's what it does. It is not just fast, it is seamless.\n이에 있어서 중요합니다.\n"
        levels = {(f["pattern"], f["level"]) for f in check_text(report_text)}
        self.assertEqual(levels, {("lead-in", "warning"), ("contrast", "warning"), ("sales-word", "warning"),
                                  ("translationese", "warning")})

    def test_folders_are_searched_so_other_documents_are_covered(self):
        # F32: the pattern fixed in one document stayed in another.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "guide").mkdir()
            (root / "guide" / "server.md").write_text("확인하세요.\n백업하시오.\n", encoding="utf-8")
            (root / "index.md").write_text("확인하세요.\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "x.md").write_text("a — b\n", encoding="utf-8")
            report = check_writing([root])
            self.assertEqual((report["files"], report["errors"], report["ok"]), (2, 1, False))
            self.assertTrue(report["findings"][0]["path"].endswith("guide/server.md"))
            result = run("check", "writing", str(root), cwd=root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("mixed-endings", result.stdout)

    def test_repository_documents_have_no_errors(self):
        paths = [ROOT / name for name in ("README.md", "README.ko.md", "AGENTS.md", "CHANGELOG.md")]
        report = check_writing([*paths, ROOT / "docs", ROOT / "kit", ROOT / "examples"])
        errors = [f"{f['path']}:{f['line']} {f['pattern']}" for f in report["findings"] if f["level"] == "error"]
        self.assertEqual(errors, [])


class DoneTests(Repository):
    def test_changed_files_need_a_passing_check_of_their_current_state(self):
        # F1: work reported as done while the checks ran on another state of the files, or not at all.
        self.commit("value.txt", "1\n", "First")
        (self.repo / "check.py").write_text(
            "import sys\nsys.exit(0 if open('value.txt').read().strip() == '2' else 1)\n", encoding="utf-8")
        (self.repo / "checks.toml").write_text(
            'schema = 1\n[[checks]]\nname = "value"\nargv = ["{python}", "check.py"]\n', encoding="utf-8")
        git(self.repo, "add", "check.py", "checks.toml")
        git(self.repo, "commit", "-q", "-m", "Add the check")
        runs = self.root / "runs"
        self.assertEqual(done(self.repo, runs, "s", mark=True)["status"], "marked")
        self.assertEqual(done(self.repo, runs, "s")["status"], "unchanged")
        (self.repo / "value.txt").write_text("2\n", encoding="utf-8")
        report = done(self.repo, runs, "s")
        self.assertEqual((report["ok"], report["changed"]), (False, ["value.txt"]))
        commit = snapshot(self.repo, ["value.txt"])
        self.assertEqual(check(self.repo, commit, self.repo / "checks.toml", runs)["status"], "passed")
        self.assertEqual(done(self.repo, runs, "s")["status"], "checked")
        # Editing after the check makes the passing run stale again; untracked files count too.
        (self.repo / "notes.md").write_text("new", encoding="utf-8")
        self.assertEqual(done(self.repo, runs, "s")["changed"], ["notes.md", "value.txt"])
        # Run records under .awkit are not part of the state.
        (self.repo / "notes.md").unlink()
        (self.repo / ".awkit").mkdir(exist_ok=True)
        (self.repo / ".awkit" / "x.json").write_text("{}", encoding="utf-8")
        self.assertTrue(done(self.repo, runs, "s")["ok"])

    def test_claude_code_hook_blocks_once_per_turn(self):
        self.commit("value.txt", "1\n", "First")
        start = run("check", "done", "--hook", cwd=self.repo,
                    stdin=json.dumps({"session_id": "abc", "hook_event_name": "SessionStart"}))
        self.assertEqual(start.returncode, 0, start.stderr)
        (self.repo / "value.txt").write_text("2\n", encoding="utf-8")
        stop = json.dumps({"session_id": "abc", "hook_event_name": "Stop", "stop_hook_active": False})
        blocked = run("check", "done", "--hook", cwd=self.repo, stdin=stop)
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("value.txt", blocked.stderr)
        again = run("check", "done", "--hook", cwd=self.repo,
                    stdin=json.dumps({"session_id": "abc", "hook_event_name": "Stop", "stop_hook_active": True}))
        self.assertEqual(again.returncode, 0)
        plain = run("check", "done", "--session", "abc", cwd=self.repo)
        self.assertEqual(plain.returncode, 1)
        written, _ = install_hooks(self.repo, sys.executable, use_git=False, use_claude=True)
        settings = json.loads((self.repo / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(settings["hooks"]), ["SessionStart", "Stop"])
        self.assertEqual(install_hooks(self.repo, sys.executable, use_git=False, use_claude=True)[0], [])
        self.assertEqual(len(written), 1)


if __name__ == "__main__":
    unittest.main()
