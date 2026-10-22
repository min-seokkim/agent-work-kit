import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from awkit.review import check, git, snapshot, verify


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

    def configure(self, checks, setup=(), timeout=10, artifacts=(), required=()):
        text = f"schema = 1\ntimeout_seconds = {timeout}\n"
        if artifacts:
            text += "artifacts = " + json.dumps(list(artifacts)) + "\n"
        if required:
            text += "required_artifacts = " + json.dumps(list(required)) + "\n"
        for phase, steps in (("setup", setup), ("checks", checks)):
            for i, item in enumerate(steps):
                code = item["code"] if isinstance(item, dict) else item
                cwd = "\ncwd = " + json.dumps(item["cwd"]) if isinstance(item, dict) and "cwd" in item else ""
                text += f'\n[[{phase}]]\nname = "{phase}-{i}"\nargv = ' + json.dumps(["{python}", "-c", code]) + cwd + "\n"
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

    def test_step_directories_use_snapshot_and_setup_generated_directories(self):
        folder = self.repo / "sdk with spaces"
        folder.mkdir()
        (folder / "input.txt").write_text("snapshot input", encoding="utf-8")
        revision = snapshot(self.repo, ["sdk with spaces/input.txt"])
        (folder / "input.txt").write_text("later edit", encoding="utf-8")
        self.configure([
            {"cwd": "sdk with spaces/generated", "code":
             "from pathlib import Path; assert Path('../input.txt').read_text() == 'snapshot input'; "
             "assert Path('marker').read_text() == 'ready'"},
            {"cwd": ".", "code": "from pathlib import Path; assert Path('code.txt').read_text() == 'old'"},
        ], setup=[
            {"cwd": "sdk with spaces", "code": "from pathlib import Path; Path('generated').mkdir()"},
            {"cwd": "sdk with spaces/generated", "code":
             "from pathlib import Path; Path('marker').write_text('ready')"},
        ])
        result = check(self.repo, revision, self.config, self.root / "runs")
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(Path(result["steps"][2]["cwd"]), Path(result["worktree"]) / "sdk with spaces/generated")
        self.assertFalse((folder / "generated").exists())
        self.assertEqual((folder / "input.txt").read_text(), "later edit")

    def test_invalid_step_directory_rejected_before_execution(self):
        for cwd in ("", "..", "../outside", "a/../../outside", "/tmp", "C:/tmp", "C:tmp",
                    "a\\b", ".git", "a/.GIT", "a//b", "a/./b", "a\x00b", 4, False, []):
            with self.subTest(cwd=cwd):
                self.configure([{"cwd": cwd, "code": "raise AssertionError('must not run')"}])
                with self.assertRaises(ValueError):
                    check(self.repo, self.head, self.config, self.root / "runs")
                self.assertFalse((self.root / "runs").exists())

    def test_unavailable_step_directory_is_recorded_and_checks_continue(self):
        for cwd in ("missing", "code.txt"):
            with self.subTest(cwd=cwd):
                self.configure([
                    {"cwd": cwd, "code": "raise AssertionError('must not run')"},
                    "print('remaining check')",
                ])
                result = check(self.repo, self.head, self.config, self.root / "runs")
                self.assertEqual(result["status"], "failed")
                self.assertIn("error", result["steps"][0])
                self.assertNotIn("exit_code", result["steps"][0])
                self.assertEqual(result["steps"][1]["status"], "passed")
                self.assertFalse(result["worktree_retained"])

    def test_unavailable_setup_directory_skips_checks(self):
        self.configure(["raise AssertionError('must not run')"],
                       setup=[{"cwd": "missing", "code": "print('must not run')"}])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["steps"]), 1)
        self.assertIn("error", result["steps"][0])

    def test_setup_cannot_redirect_step_directory_outside_worktree(self):
        outside = self.root / "outside"
        outside.mkdir()
        probe = self.root / "link-probe"
        try:
            probe.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("directory symlinks unavailable")
        probe.unlink()
        self.configure([{"cwd": "redirect", "code":
                         "from pathlib import Path; Path('should-not-exist').touch()"}],
                       setup=["from pathlib import Path; "
                              f"Path('redirect').symlink_to({str(outside)!r}, target_is_directory=True)"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["steps"][0]["status"], "passed")
        self.assertEqual(result["steps"][1]["status"], "failed")
        self.assertIn("error", result["steps"][1])
        self.assertFalse((outside / "should-not-exist").exists())

    def test_artifact_example_retains_checked_input_after_worktree_cleanup(self):
        import hashlib
        git(self.repo, "config", "core.autocrlf", "false")
        examples = Path(__file__).resolve().parents[1] / "examples/review"
        target = self.repo / "examples/review"
        target.mkdir(parents=True)
        names = ["checks.toml", "subdirectory.toml"]
        for name in names:
            (target / name).write_bytes((examples / name).read_bytes())
        revision = snapshot(self.repo, ["examples/review/" + name for name in names])
        original = (target / "checks.toml").read_bytes()
        (target / "checks.toml").write_text("later edit", encoding="utf-8")
        result = check(self.repo, revision, target / "subdirectory.toml", self.root / "runs")
        self.assertEqual(result["status"], "passed", result)
        self.assertFalse(result["worktree_retained"])
        artifacts = Path(result["run_dir"]) / "artifacts"
        self.assertEqual((artifacts / "examples/review/checks.toml").read_bytes(), original)
        manifest = json.loads((artifacts / "manifest.json").read_text())
        self.assertEqual(manifest["files"]["examples/review/checks.toml"]["sha256"],
                         hashlib.sha256(original).hexdigest())
        self.assertTrue(verify(result["run_dir"])["verified"])
        record = json.loads((Path(result["run_dir"]) / "result.json").read_text())
        self.assertEqual(record["snapshot"], revision)

    def test_failed_check_retains_output_written_to_run_directory(self):
        self.configure(["import os; from pathlib import Path; "
                        "output = Path(os.environ['AWKIT_RUN_DIR']) / 'artifacts'; output.mkdir(); "
                        "(output / 'failure.txt').write_text('diagnostic'); raise SystemExit(7)"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["worktree_retained"])
        self.assertEqual((Path(result["run_dir"]) / "artifacts/failure.txt").read_text(), "diagnostic")

    def test_artifacts_are_retained_hashed_and_verifiable_after_cleanup(self):
        import hashlib
        self.configure(["from pathlib import Path; Path('out').mkdir(); Path('out/report.txt').write_text('built'); "
                        "Path('out/scratch.tmp').write_text('x')"],
                       artifacts=["out/*.txt", "code.txt"], required=["out/report.txt"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["status"], "passed", result)
        self.assertFalse(result["worktree_retained"])
        run = Path(result["run_dir"])
        self.assertEqual(set(result["artifacts"]), {"out/report.txt", "code.txt"})
        self.assertEqual(result["artifacts"]["out/report.txt"],
                         {"size": 5, "sha256": hashlib.sha256(b"built").hexdigest()})
        self.assertEqual(result["missing_artifacts"], [])
        self.assertEqual((run / "artifacts/out/report.txt").read_text(), "built")
        self.assertFalse((run / "artifacts/out/scratch.tmp").exists())
        self.assertEqual((run / "config.toml").read_bytes(), self.config.read_bytes())
        manifest = json.loads((run / "artifacts/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["snapshot"], set(manifest["files"])), (self.head, {"out/report.txt", "code.txt"}))
        report = verify(run)
        self.assertTrue(report["verified"], report)
        self.assertEqual({item["path"]: item["status"] for item in report["artifacts"]},
                         {"out/report.txt": "ok", "code.txt": "ok"})
        (run / "artifacts/out/report.txt").write_text("edited")
        (run / "artifacts/code.txt").unlink()
        (run / "artifacts/extra.txt").write_text("added later")
        report = verify(run)
        self.assertFalse(report["verified"])
        self.assertEqual({item["path"]: item["status"] for item in report["artifacts"]},
                         {"out/report.txt": "changed", "code.txt": "missing"})
        self.assertEqual(report["unexpected"], ["extra.txt"])

    def test_missing_required_artifact_fails_a_passing_check(self):
        self.configure(["print('checks passed but produced nothing')"],
                       required=["dist/*.whl"], artifacts=["code.txt"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["missing_artifacts"], ["dist/*.whl"])
        self.assertEqual(result["steps"][0]["status"], "passed")
        self.assertIn("code.txt", result["artifacts"])
        self.assertFalse(result["worktree_retained"])

    def test_artifacts_from_a_failed_check_are_retained_and_links_are_skipped(self):
        probe = self.root / "link-probe"
        try:
            probe.symlink_to(self.root / "outside.txt")
        except OSError:
            self.skipTest("symlinks unavailable")
        probe.unlink()
        (self.root / "outside.txt").write_text("secret")
        self.configure(["from pathlib import Path; Path('diag.log').write_text('why it failed'); "
                        f"Path('leak.txt').symlink_to({str(self.root / 'outside.txt')!r}); raise SystemExit(3)"],
                       artifacts=["*.log", "leak.txt"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(list(result["artifacts"]), ["diag.log"])
        self.assertEqual(result["skipped_artifacts"], ["leak.txt"])
        self.assertEqual((Path(result["run_dir"]) / "artifacts/diag.log").read_text(), "why it failed")

    def test_invalid_artifact_patterns_are_rejected_before_execution(self):
        for pattern in ("../x", "/abs", "a\\b", ".git/*", 5):
            with self.subTest(pattern=pattern):
                self.config.write_text('schema = 1\nartifacts = [' + json.dumps(pattern) + ']\n'
                                       '[[checks]]\nname = "c"\nargv = ["x"]\n', encoding="utf-8")
                with self.assertRaises(ValueError):
                    check(self.repo, self.head, self.config, self.root / "runs")
                self.assertFalse((self.root / "runs").exists())

    def test_verify_reports_an_interrupted_run_and_rejects_foreign_manifests(self):
        run = self.root / "runs" / "review-x"
        (run / "artifacts").mkdir(parents=True)
        (run / "result.json").write_text(json.dumps({"snapshot": self.head, "status": "running"}), encoding="utf-8")
        self.assertFalse(verify(run)["verified"])
        self.assertTrue(verify(run)["interrupted"])
        (run / "artifacts/manifest.json").write_text(json.dumps({"schema": 1, "snapshot": "f" * 40, "files": {}}))
        with self.assertRaises(ValueError):
            verify(run)
        with self.assertRaises(ValueError):
            verify(self.root / "nowhere")

    def test_cli_verify_exit_codes(self):
        self.configure(["from pathlib import Path; Path('a.txt').write_text('a')"], artifacts=["a.txt"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        command = [sys.executable, "-m", "awkit", "review", "verify", result["run_dir"]]
        env = {**os.environ, "PYTHONUTF8": "1"}
        ok = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(json.loads(ok.stdout)["verified"])
        (Path(result["run_dir"]) / "artifacts/a.txt").write_text("b")
        changed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(changed.returncode, 1)

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
