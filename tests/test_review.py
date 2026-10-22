import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from awkit.review import check, git, snapshot


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "project with spaces"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@localhost")
        for name, data in {"code.txt": "old", "other.txt": "original", ".gitignore": "ignored.txt\n"}.items():
            (self.repo / name).write_text(data, encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "Fixture")
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.config = self.root / "checks.toml"

    def configure(self, checks, setup=(), timeout=10):
        text = f"schema = 1\ntimeout_seconds = {timeout}\n"
        for phase, steps in (("setup", setup), ("checks", checks)):
            for i, code in enumerate(steps):
                text += f'\n[[{phase}]]\nname = "{phase}-{i}"\nargv = ' + json.dumps(["{python}", "-c", code]) + "\n"
        self.config.write_text(text, encoding="utf-8")

    def test_snapshot_preserves_index_head_and_unselected_changes(self):
        (self.repo / "other.txt").write_text("staged", encoding="utf-8")
        git(self.repo, "add", "other.txt")
        (self.repo / "code.txt").write_text("new", encoding="utf-8")
        (self.repo / "added.txt").write_text("included", encoding="utf-8")
        (self.repo / "secret.txt").write_text("not selected", encoding="utf-8")
        status = git(self.repo, "status", "--porcelain")
        index = (self.repo / ".git/index").read_bytes()
        revision = snapshot(self.repo, ["code.txt", "added.txt"])
        self.assertEqual(git(self.repo, "show", revision + ":code.txt"), "new")
        self.assertEqual(git(self.repo, "show", revision + ":other.txt"), "original")
        self.assertNotIn("secret.txt", git(self.repo, "ls-tree", "--name-only", revision))
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)
        self.assertEqual(git(self.repo, "status", "--porcelain"), status)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.head)

    def test_snapshot_deletion_and_literal_filename(self):
        (self.repo / "code.txt").unlink()
        (self.repo / "literal[1].txt").write_text("selected", encoding="utf-8")
        revision = snapshot(self.repo, ["code.txt", "literal[1].txt"])
        tree = git(self.repo, "ls-tree", "--name-only", revision)
        self.assertNotIn("code.txt", tree)
        self.assertIn("literal[1].txt", tree)

    def test_rejects_broad_paths_traversal_and_ignored_files(self):
        (self.repo / "ignored.txt").write_text("excluded", encoding="utf-8")
        for paths in (["."], ["../outside"], [".git/config"], ["ignored.txt"], []):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                snapshot(self.repo, paths)

    def test_setup_and_checks_use_fixed_version_and_unique_worktree(self):
        self.configure(["from pathlib import Path; assert Path('code.txt').read_text() == 'old'; assert Path('generated').exists()"],
                       ["from pathlib import Path; Path('generated').touch()"])
        (self.repo / "code.txt").write_text("changed after snapshot", encoding="utf-8")
        first = check(self.repo, self.head, self.config, self.root / "runs")
        second = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual((first["status"], second["status"]), ("passed", "passed"))
        self.assertNotEqual(first["run_dir"], second["run_dir"])
        self.assertFalse(Path(first["worktree"]).exists())
        self.assertEqual((self.repo / "code.txt").read_text(), "changed after snapshot")
        self.assertEqual(len(git(self.repo, "worktree", "list", "--porcelain").split("worktree ")) - 1, 1)

    def test_failures_are_recorded_and_other_checks_continue(self):
        self.configure(["print('diagnostic'); raise SystemExit(7)", "print('next check')"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["steps"][0]["exit_code"], 7)
        self.assertEqual(result["steps"][1]["status"], "passed")
        self.assertIn("diagnostic", (Path(result["run_dir"]) / "01.log").read_text())

    def test_setup_failure_skips_checks(self):
        self.configure(["raise AssertionError('should not run')"], ["raise SystemExit(2)"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["status"], "failed")

    def test_timeout_keeps_owned_worktree_and_evidence(self):
        self.configure(["import time; time.sleep(5)"], timeout=0.1)
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["status"], "uncertain")
        self.assertTrue(result["worktree_retained"])
        self.assertTrue((Path(result["run_dir"]) / "result.json").exists())
        git(self.repo, "worktree", "remove", "--force", result["worktree"])

    def test_timeout_stops_processes_started_by_the_check(self):
        marker = self.root / "orphan-alive.txt"
        child = f"import sys, time; time.sleep(3); open({str(marker)!r}, 'w').write('alive')"
        code = ("import subprocess, sys, time; "
                f"subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(30)")
        self.configure([code], timeout=1)
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["status"], "uncertain")
        import time
        time.sleep(4)
        self.assertFalse(marker.exists(), "check child survived the timeout")

    def test_invalid_config_creates_no_worktree(self):
        self.configure([])
        with self.assertRaises(ValueError):
            check(self.repo, self.head, self.config, self.root / "runs")
        self.assertFalse((self.root / "runs").exists())

    def test_cli_failure_exit(self):
        self.configure(["raise SystemExit(9)"])
        result = subprocess.run([sys.executable, "-m", "awkit", "review", "--repo", str(self.repo),
                                 "check", self.head, "--config", str(self.config), "--runs-root", str(self.root / "runs")],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(result.stdout, result.stderr)
        self.assertEqual(json.loads(result.stdout)["steps"][0]["exit_code"], 9)


if __name__ == "__main__":
    unittest.main()
