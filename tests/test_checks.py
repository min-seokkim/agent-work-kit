"""Each test replays a recorded occurrence from kit/failures.md that the check must catch."""

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
        self.assertNotIn(sys.executable, Path(written[0]).read_text(encoding="utf-8"))


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
        report_text = ("Here's what it does. It is not just fast, it is seamless.\n이에 있어서 중요합니다.\n"
                       "The question is whether it happens here is unclear.\n")  # mid-sentence: not a lead-in
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


class KitCommitIdentityTests(Repository):
    """The planning session's install: Git's identity was "Claude", doctor passed it and the kit's commit
    did not belong to the owner."""

    def test_kit_commit_follows_the_owner_or_is_skipped(self):
        from awkit.doctor import diagnose
        from awkit.kit_install import install
        from awkit.review import track
        self.commit("app.py", "print(1)\n", "Owner's work")
        git(self.repo, "config", "user.name", "Claude")
        git(self.repo, "config", "user.email", "noreply@anthropic.com")
        warning = [f for f in diagnose(self.repo) if f["item"] == "commit identity"]
        self.assertEqual(len(warning), 1)
        self.assertIn("looks like a coding agent's identity", warning[0]["detail"])
        target, _ = install(self.repo)
        skipped = track(self.repo, [target], "Add agent-work-kit")
        self.assertFalse(skipped["committed"])
        self.assertIn("coding agent's identity", skipped["skipped"])
        self.assertEqual(git(self.repo, "log", "--format=%an"), "owner")  # nothing committed as the agent
        git(self.repo, "config", "user.name", "owner")
        git(self.repo, "config", "user.email", "owner@example.com")
        self.assertEqual([f for f in diagnose(self.repo) if f["item"] == "commit identity"], [])
        self.assertTrue(track(self.repo, [target], "Add agent-work-kit")["committed"])
        self.assertEqual(git(self.repo, "log", "-1", "--format=%an"), "owner")

    def test_awkit_commits_are_not_history(self):
        from awkit.kit_install import install
        from awkit.review import track
        fresh = self.root / "fresh"
        fresh.mkdir()
        target, _ = install(fresh)
        self.assertTrue(track(fresh, [target], "Add agent-work-kit")["committed"])
        self.assertEqual(git(fresh, "log", "--format=%an"), "Agent Work Kit")
        git(fresh, "config", "user.name", "owner")
        git(fresh, "config", "user.email", "owner@example.com")
        self.assertTrue(commit_identity(fresh, message="Start the project")["ok"])


class RunRecordTests(Repository):
    def test_run_records_stay_in_the_project_and_out_of_git(self):
        # The default used to be the system temp folder, outside the project the runs belong to.
        self.commit("check.py", "print('ok')\n", "First")
        (self.repo / "checks.toml").write_text('schema = 1\n[[checks]]\nname = "ok"\nargv = ["{python}", "check.py"]\n',
                                               encoding="utf-8")
        git(self.repo, "add", "checks.toml")
        git(self.repo, "commit", "-q", "-m", "Add the check")
        result = check(self.repo, "HEAD", self.repo / "checks.toml")
        self.assertEqual(result["status"], "passed")
        self.assertTrue(Path(result["run_dir"]).resolve().is_relative_to((self.repo / ".awkit" / "reviews").resolve()))
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(done(self.repo)["status"], "unchanged")


class NestedRepositoryTests(Repository):
    """A clone inside the project is not supported; every command that meets one says so."""

    def setUp(self):
        super().setUp()
        self.commit("app.py", "print(1)\n", "First")
        clone = self.repo / "awkit-src"
        (clone / "src" / "awkit").mkdir(parents=True)
        (clone / "src" / "awkit" / "__init__.py").write_text("", encoding="utf-8")
        (clone / "README.md").write_text("a — b\n", encoding="utf-8")
        git(clone, "init", "-q")

    def test_done_explains_why_it_can_never_pass(self):
        # The clone has no commit, so Git could not even add it; the check must still explain itself.
        report = done(self.repo, self.root / "runs")
        self.assertEqual((report["ok"], report["status"]), (False, "nested-repository"))
        self.assertEqual(report["nested"], [{"path": "awkit-src", "awkit": True}])
        result = run("check", "done", cwd=self.repo)
        self.assertIn("awkit-src is a clone of awkit inside this project", result.stderr)
        (self.repo / ".gitignore").write_text("awkit-src/\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "Ignore the clone")
        self.assertTrue(done(self.repo, self.root / "runs")["ok"])

    def test_writing_doctor_and_scan(self):
        (self.repo / "guide.md").write_text("plain\n", encoding="utf-8")
        (self.repo / "build").mkdir()
        (self.repo / "build" / "out.md").write_text("a — b\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("build/\n", encoding="utf-8")
        report = check_writing([self.repo])
        self.assertEqual((report["files"], report["errors"]), (1, 0))  # not the clone, not the ignored build
        from awkit.doctor import diagnose
        from awkit.scan import scan
        nested = [f for f in diagnose(self.repo) if f["item"] == "nested repository"]
        self.assertEqual(len(nested), 1)
        self.assertIn("a clone of awkit", nested[0]["detail"])
        self.assertEqual(scan(self.repo)["git"]["nested_repositories"], [{"path": "awkit-src", "awkit": True}])


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
        # Run records under .awkit are not part of the state, whether or not .awkit is ignored.
        (self.repo / "notes.md").unlink()
        (self.repo / ".awkit").mkdir(exist_ok=True)
        (self.repo / ".awkit" / "x.json").write_text("{}", encoding="utf-8")
        self.assertTrue(done(self.repo, runs, "s")["ok"])
        (self.repo / ".git" / "info" / "exclude").write_text(".awkit/\n", encoding="utf-8")
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
        # Compaction fires SessionStart again; the unchecked change must not be forgotten.
        compacted = run("check", "done", "--hook", cwd=self.repo,
                        stdin=json.dumps({"session_id": "abc", "hook_event_name": "SessionStart", "source": "compact"}))
        self.assertEqual(compacted.returncode, 0, compacted.stderr)
        self.assertEqual(run("check", "done", "--hook", cwd=self.repo, stdin=stop).returncode, 2)
        again = run("check", "done", "--hook", cwd=self.repo,
                    stdin=json.dumps({"session_id": "abc", "hook_event_name": "Stop", "stop_hook_active": True}))
        self.assertEqual(again.returncode, 0)
        plain = run("check", "done", "--session", "abc", cwd=self.repo)
        self.assertEqual(plain.returncode, 1)
        written, _ = install_hooks(self.repo, sys.executable, use_git=False, use_claude=True)
        settings = json.loads((self.repo / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(settings["hooks"]), ["SessionStart", "Stop"])
        # The hooks call awkit by name, not this machine's interpreter, so a moved environment cannot break them.
        commands = [h["command"] for e in settings["hooks"]["Stop"] for h in e["hooks"]]
        self.assertEqual(commands, ["if command -v awkit >/dev/null 2>&1; then awkit check done --hook; fi"])
        self.assertNotIn(sys.executable, (self.repo / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
        # The settings file the kit wrote is local: it never counts as unchecked work.
        (self.repo / "value.txt").write_text("1\n", encoding="utf-8")
        self.assertTrue(done(self.repo, self.root / "runs")["ok"])
        self.assertIn(".claude/settings.local.json", (self.repo / ".git" / "info" / "exclude").read_text(encoding="utf-8"))
        self.assertEqual(install_hooks(self.repo, sys.executable, use_git=False, use_claude=True)[0], [])
        self.assertEqual(len(written), 1)


if __name__ == "__main__":
    unittest.main()
