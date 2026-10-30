import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from awkit import cli, review
from awkit.review_export import export_run


class ReviewFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "project"
        self.repo.mkdir()
        review.git(self.repo, "init")
        review.git(self.repo, "config", "user.name", "Fixture")
        review.git(self.repo, "config", "user.email", "fixture@localhost")
        (self.repo / "input.txt").write_text("tracked input", encoding="utf-8")
        review.git(self.repo, "add", ".")
        review.git(self.repo, "commit", "-m", "Fixture")
        self.original_git = review.git
        self.original_save = review.atomic_json

    def configure(self, mode):
        config = self.root / f"{mode}.toml"
        config.write_text(f'schema = 1\nartifact_storage = "{mode}"\nartifacts = ["input.txt"]\n'
                          '[[checks]]\nname = "read-input"\n'
                          'argv = ["{python}", "-c", "from pathlib import Path; '
                          'assert Path(\'input.txt\').read_text() == \'tracked input\'"]\n', encoding="utf-8")
        return config

    def run_cli(self, mode, cleanup=True):
        config = self.configure(mode)
        runs = self.root / (mode + "-runs")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(["review", "--repo", str(self.repo), "check", "HEAD",
                             "--config", str(config), "--runs-root", str(runs)])
        run, = runs.glob("review-*")
        # Windows TEMP may use an 8.3 alias; the diagnostic reports the resolved directory.
        run = run.resolve()
        result = json.loads((run / "result.json").read_text(encoding="utf-8"))
        if cleanup and result.get("worktree_retained"):
            self.addCleanup(self.original_git, self.repo, "worktree", "remove", "--force", result["worktree"])
        return code, stdout.getvalue(), stderr.getvalue(), run, result

    def refuse_checkout(self, repo, *args, **kwargs):
        if args[:2] == ("worktree", "add"):
            raise ValueError("synthetic checkout refusal")
        return self.original_git(repo, *args, **kwargs)

    def test_checkout_failure_records_cause_phase_and_location_in_both_modes(self):
        for mode in ("copy", "shared"):
            with self.subTest(mode=mode), patch("awkit.review.git", side_effect=self.refuse_checkout), \
                    patch("awkit.review.run_to_files") as run_step:
                code, stdout, stderr, run, result = self.run_cli(mode)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertIn("cannot run: synthetic checkout refusal", stderr)
                self.assertIn(str(run), stderr)
                self.assertEqual(result["status"], "uncertain")
                self.assertEqual(result["failure"], {"phase": "worktree-creation", "error": "synthetic checkout refusal"})
                self.assertEqual(result["steps"], [])
                self.assertFalse(result["worktree_retained"])
                self.assertNotIn("artifacts", result)
                run_step.assert_not_called()
                if mode == "shared":
                    self.assertEqual(result["artifact_publication"]["state"], "incomplete")
                    self.assertEqual(result["artifact_publication"]["error"], "synthetic checkout refusal")
                with self.assertRaises(ValueError):
                    export_run(run, self.root / (mode + "-export"))

    def test_failed_checkout_preserves_actual_partial_files(self):
        def partial(repo, *args, **kwargs):
            if args[:2] == ("worktree", "add"):
                worktree = Path(args[3])
                worktree.mkdir()
                (worktree / "partial.txt").write_text("partial", encoding="utf-8")
                raise ValueError("partial checkout refusal")
            return self.original_git(repo, *args, **kwargs)

        with patch("awkit.review.git", side_effect=partial):
            # This partial directory was never registered, so only the owned temp fixture cleans it.
            code, _, _, _, result = self.run_cli("copy", cleanup=False)
        self.assertEqual(code, 2)
        self.assertTrue(result["worktree_retained"])
        self.assertEqual((Path(result["worktree"]) / "partial.txt").read_text(), "partial")
        self.assertEqual(result["steps"], [])

    def test_collection_exception_after_checks_retains_completed_steps(self):
        for mode, collector in (("copy", "awkit.review.collect_artifacts"), ("shared", "awkit.artifact_store.collect")):
            with self.subTest(mode=mode), patch(collector, side_effect=OSError("synthetic collection refusal")):
                code, stdout, stderr, run, result = self.run_cli(mode)
                self.assertEqual((code, stdout), (2, ""))
                self.assertIn("synthetic collection refusal", stderr)
                self.assertIn(str(run), stderr)
                self.assertEqual(result["status"], "uncertain")
                self.assertEqual(result["failure"], {"phase": "artifact-collection", "error": "synthetic collection refusal"})
                self.assertEqual(len(result["steps"]), 1)
                self.assertEqual(result["steps"][0]["status"], "passed")
                self.assertTrue(result["worktree_retained"])
                if mode == "shared":
                    self.assertEqual(result["artifact_publication"]["state"], "incomplete")

    def test_diagnostic_write_failure_does_not_replace_the_original_error(self):
        def refuse_failure_record(path, value):
            if value.get("status") == "uncertain":
                raise OSError("synthetic diagnostic write refusal")
            return self.original_save(path, value)

        for mode in ("copy", "shared"):
            with self.subTest(mode=mode), patch("awkit.review.git", side_effect=self.refuse_checkout), \
                    patch("awkit.review.atomic_json", side_effect=refuse_failure_record):
                code, stdout, stderr, run, result = self.run_cli(mode)
                self.assertEqual((code, stdout), (2, ""))
                self.assertIn("cannot run: synthetic checkout refusal", stderr)
                self.assertIn("Could not save review failure: synthetic diagnostic write refusal", stderr)
                self.assertIn(str(run), stderr)
                self.assertEqual(result["status"], "running")
                self.assertNotIn("failure", result)
                self.assertEqual(result["steps"], [])

    def test_step_record_write_failure_keeps_step_history(self):
        failed = False

        def refuse_once(path, value):
            nonlocal failed
            if value.get("steps") and value.get("status") == "running" and not failed:
                failed = True
                raise OSError("synthetic step record refusal")
            return self.original_save(path, value)

        with patch("awkit.review.atomic_json", side_effect=refuse_once):
            code, _, stderr, run, result = self.run_cli("copy")
        self.assertEqual(code, 2)
        self.assertIn(str(run), stderr)
        self.assertEqual(result["failure"], {"phase": "step-result", "error": "synthetic step record refusal"})
        self.assertEqual(result["steps"][0]["status"], "passed")
        self.assertEqual(result["status"], "uncertain")

    def test_interruption_keeps_existing_exit_and_reports_run(self):
        with patch("awkit.review.run_to_files", side_effect=KeyboardInterrupt):
            code, stdout, stderr, run, result = self.run_cli("copy")
        self.assertEqual(code, 130)
        self.assertEqual(stdout, "")
        self.assertIn("Interrupted. Check the run record", stderr)
        self.assertIn(str(run), stderr)
        self.assertEqual(result["failure"], {"phase": "check", "error": "KeyboardInterrupt"})
        self.assertEqual(result["status"], "uncertain")
        self.assertEqual(len(result["steps"]), 1)
        self.assertNotIn("status", result["steps"][0])
        self.assertTrue(result["worktree_retained"])


if __name__ == "__main__":
    unittest.main()
