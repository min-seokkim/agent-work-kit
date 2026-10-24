import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from awkit.review import accept, check, compare, git, snapshot, verify
from support import child_env


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

    def test_snapshot_of_files_removed_with_git_rm_and_git_mv(self):
        # git mv and git rm take the old path out of the index too; HEAD still has it, and the snapshot
        # must record the removal (found when this repository moved its failure catalogue).
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "notes.md").write_text("notes", encoding="utf-8")
        git(self.repo, "add", "docs/notes.md")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@localhost", "commit", "-q", "-m", "notes")
        git(self.repo, "mv", "docs/notes.md", "notes.md")
        git(self.repo, "rm", "-q", "code.txt")
        revision = snapshot(self.repo, ["docs/notes.md", "notes.md", "code.txt"])
        tree = git(self.repo, "ls-tree", "-r", "--name-only", revision).split()
        self.assertIn("notes.md", tree)
        self.assertNotIn("docs/notes.md", tree)
        self.assertNotIn("code.txt", tree)
        with self.assertRaisesRegex(ValueError, "File not found"):
            snapshot(self.repo, ["never-existed.md"])

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

    def test_accept_keeps_artifacts_and_compare_reports_regressions(self):
        self.configure(["from pathlib import Path; Path('out').mkdir(exist_ok=True); "
                        "Path('out/report.md').write_text(Path('code.txt').read_text() + ' report')"],
                       artifacts=["out/report.md", "code.txt"])
        first = check(self.repo, self.head, self.config, self.root / "runs")
        record = accept(self.repo, first["run_dir"])
        folder = self.repo / ".awkit" / "accepted" / "accepted"
        # Git reports the long path; a Windows temp folder may come as an 8.3 short name.
        self.assertEqual(Path(record["folder"]).resolve(), folder.resolve())
        self.assertEqual((folder / "out/report.md").read_text(), "old report")
        self.assertEqual(json.loads((folder / "accepted.json").read_text())["snapshot"], self.head)
        # The working tree has no out/report.md (it was produced in the worktree), code.txt is unchanged.
        report = compare(self.repo)
        self.assertEqual({f["path"]: f["status"] for f in report["files"]}, {"out/report.md": "missing", "code.txt": "same"})
        self.assertIn("--run", report["note"])
        self.assertNotIn("note", compare(self.repo, run_dir=first["run_dir"]))
        self.assertFalse(report["unchanged"])
        # A new run against an edited snapshot compares its own artifacts with the accepted ones.
        (self.repo / "code.txt").write_text("new", encoding="utf-8")
        revision = snapshot(self.repo, ["code.txt"])
        second = check(self.repo, revision, self.config, self.root / "runs")
        report = compare(self.repo, run_dir=second["run_dir"], diff=True)
        statuses = {f["path"]: f for f in report["files"]}
        self.assertEqual(statuses["out/report.md"]["status"], "changed")
        self.assertIn("-old report", statuses["out/report.md"]["diff"])
        self.assertIn("+new report", statuses["out/report.md"]["diff"])
        self.assertEqual(statuses["code.txt"]["status"], "changed")
        self.assertEqual(report["compared"], second["run_dir"])
        # Accepting the second run replaces the first; the same run then compares as unchanged.
        accept(self.repo, second["run_dir"])
        self.assertTrue(compare(self.repo, run_dir=second["run_dir"])["unchanged"])
        self.assertEqual((folder / "code.txt").read_text(), "new")
        self.assertEqual([p.name for p in folder.parent.iterdir()], ["accepted"])

    def test_accept_rejects_unverified_runs_bad_labels_and_missing_versions(self):
        self.configure(["print('nothing retained')"])
        bare = check(self.repo, self.head, self.config, self.root / "runs")
        with self.assertRaises(ValueError):
            accept(self.repo, bare["run_dir"])
        self.configure(["from pathlib import Path; Path('a.txt').write_text('a')"], artifacts=["a.txt"])
        run = check(self.repo, self.head, self.config, self.root / "runs")
        for label in ("", "../x", "a/b", "x" * 81, 5):
            with self.subTest(label=label), self.assertRaises(ValueError):
                accept(self.repo, run["run_dir"], label)
        # A second accept changes nothing while another one holds the lock.
        state = self.repo / ".awkit"
        state.mkdir(exist_ok=True)
        holder = sqlite3.connect(state / "accept.lock.sqlite3")
        holder.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(ValueError, "Another accept is running"):
                accept(self.repo, run["run_dir"])
            self.assertEqual([p.name for p in (state / "accepted").iterdir()], [])
        finally:
            holder.rollback()
            holder.close()
        self.assertTrue(accept(self.repo, run["run_dir"])["folder"].endswith("accepted"))
        (Path(run["run_dir"]) / "artifacts/a.txt").write_text("tampered")
        with self.assertRaises(ValueError):
            accept(self.repo, run["run_dir"])
        with self.assertRaises(ValueError):
            compare(self.repo, "nothing-accepted")

    def test_cli_accept_and_compare(self):
        self.configure(["from pathlib import Path; Path('a.txt').write_text('a')"], artifacts=["a.txt", "code.txt"])
        run = check(self.repo, self.head, self.config, self.root / "runs")
        env = child_env()
        base = [sys.executable, "-m", "awkit", "review", "--repo", str(self.repo)]
        accepted = subprocess.run(base + ["accept", run["run_dir"], "--label", "v1"], capture_output=True,
                                  text=True, encoding="utf-8", env=env)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["label"], "v1")
        same = subprocess.run(base + ["compare", "--label", "v1", "--run", run["run_dir"]], capture_output=True,
                              text=True, encoding="utf-8", env=env)
        self.assertEqual(same.returncode, 0, same.stderr)
        (self.repo / "code.txt").write_text("edited", encoding="utf-8")
        changed = subprocess.run(base + ["compare", "--label", "v1", "--diff"], capture_output=True,
                                 text=True, encoding="utf-8", env=env)
        self.assertEqual(changed.returncode, 1)
        self.assertIn("+edited", json.loads(changed.stdout)["files"][1]["diff"])

    def inventory_runs(self):
        self.configure(["from pathlib import Path; Path('kept.txt').write_text('same'); "
                        "Path('removed.txt').write_text('old')"], artifacts=["kept.txt", "removed.txt"])
        first = check(self.repo, self.head, self.config, self.root / "runs")
        accept(self.repo, first["run_dir"], "inventory")
        self.configure(["from pathlib import Path; Path('kept.txt').write_text('same'); "
                        "Path('removed.txt').write_text('old'); Path('z new.txt').write_text('new'); "
                        "Path('한글.txt').write_text('new')"], artifacts=["*.txt"])
        second = check(self.repo, self.head, self.config, self.root / "runs")
        return Path(first["run_dir"]), Path(second["run_dir"])

    def inventory_cli(self, run=None, include_added=False, expected=0):
        argv = [sys.executable, "-m", "awkit", "review", "--repo", str(self.repo), "compare", "--label", "inventory"]
        if run is not None:
            argv += ["--run", str(run)]
        if include_added:
            argv += ["--include-added"]
        result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", env=child_env())
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_include_added_cli_preserves_default_and_additions_only_exit(self):
        first, second = self.inventory_runs()
        before = self.inventory_cli(second).stdout
        self.assertNotIn("added_artifacts", json.loads(before))
        accepted = self.repo / ".awkit/accepted/inventory"
        protected = [path for folder in (first, second, accepted) for path in folder.rglob("*") if path.is_file()]
        states = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in protected}
        result = json.loads(self.inventory_cli(second, True).stdout)
        self.assertTrue(result["unchanged"])
        self.assertEqual(result["files"], json.loads(before)["files"])
        self.assertEqual(result["added_artifacts"]["source"], str(second.resolve() / "artifacts/manifest.json"))
        self.assertIn("not verified", result["added_artifacts"]["scope"])
        self.assertEqual(result["added_artifacts"]["files"], [{"path": "code.txt"}, {"path": "other.txt"},
                         {"path": "z new.txt"}, {"path": "한글.txt"}])
        self.assertEqual(self.inventory_cli(second).stdout, before)
        self.assertEqual({path: (path.read_bytes(), path.stat().st_mtime_ns) for path in protected}, states)
        no_added = json.loads(self.inventory_cli(first, True).stdout)
        self.assertEqual(no_added["added_artifacts"]["files"], [])
        self.assertTrue(no_added["unchanged"])
        (second / "artifacts/unrecorded.txt").write_text("not retained")
        (second / "artifacts/kept.txt").write_text("changed")
        (second / "artifacts/removed.txt").unlink()
        default = json.loads(self.inventory_cli(second, expected=1).stdout)
        changed = json.loads(self.inventory_cli(second, True, expected=1).stdout)
        self.assertEqual(changed["files"], default["files"])
        self.assertEqual(changed["unchanged"], default["unchanged"])
        self.assertEqual({item["path"]: item["status"] for item in changed["files"]},
                         {"kept.txt": "changed", "removed.txt": "missing"})
        self.assertNotIn("unrecorded.txt", [item["path"] for item in changed["added_artifacts"]["files"]])

    def test_include_added_requires_explicit_run_and_does_not_change_default(self):
        first, _ = self.inventory_runs()
        with self.assertRaisesRegex(ValueError, "--include-added requires --run"):
            compare(self.repo, "inventory", include_added=True)
        result = self.inventory_cli(include_added=True, expected=2)
        self.assertIn("--include-added requires --run", result.stderr)
        self.assertNotIn("added_artifacts", compare(self.repo, "inventory", first))

    def test_include_added_inventory_errors_leave_default_comparison_usable(self):
        _, second = self.inventory_runs()
        manifest_path = second / "artifacts/manifest.json"
        original = manifest_path.read_bytes()
        valid = json.loads(original)
        baseline = self.inventory_cli(second).stdout
        variants = [None, [], dict(valid, schema=2), dict(valid, schema=True), dict(valid, files=[]),
                    dict(valid, snapshot="other"), dict(valid, config_sha256="other"),
                    dict(valid, files={"new.txt": {"size": True, "sha256": "a" * 64}}),
                    dict(valid, files={"new.txt": {"size": -1, "sha256": "a" * 64}}),
                    dict(valid, files={"new.txt": {"size": 0, "sha256": "invalid"}})]
        variants += [dict(valid, files={name: {"size": 0, "sha256": "a" * 64}})
                     for name in ("../outside.txt", "/absolute.txt", "C:/outside.txt", "dir\\outside.txt", "a//b", ".git/config", "bad\0path")]
        for variant in variants:
            with self.subTest(variant=variant):
                manifest_path.write_text(json.dumps(variant), encoding="utf-8")
                self.assertEqual(self.inventory_cli(second).stdout, baseline)
                self.inventory_cli(second, True, expected=2)
        for data in (b'{"schema":', b"\xff"):
            with self.subTest(data=data):
                manifest_path.write_bytes(data)
                self.assertEqual(self.inventory_cli(second).stdout, baseline)
                self.inventory_cli(second, True, expected=2)
        manifest_path.unlink()
        self.assertEqual(self.inventory_cli(second).stdout, baseline)
        self.inventory_cli(second, True, expected=2)
        manifest_path.write_bytes(original)
        result_path = second / "result.json"
        saved = result_path.read_bytes()
        result_path.write_text("[]", encoding="utf-8")
        self.assertEqual(self.inventory_cli(second).stdout, baseline)
        self.inventory_cli(second, True, expected=2)
        result_path.write_bytes(saved)

    def test_include_added_uses_only_declared_names_without_opening_added_contents(self):
        _, second = self.inventory_runs()
        source = (second / "artifacts").resolve()
        manifest_path = source / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["manifest.json"] = {"size": 0, "sha256": "a" * 64}
        manifest["files"]["not-present.txt"] = {"size": 0, "sha256": "a" * 64}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        original = Path.read_bytes

        def guarded(path):
            if path.parent == source and path.name not in ("kept.txt", "removed.txt"):
                raise AssertionError("added contents must not be read")
            return original(path)

        with patch.object(Path, "read_bytes", guarded):
            report = compare(self.repo, "inventory", second, diff=True, include_added=True)
        added = report["added_artifacts"]["files"]
        self.assertIn({"path": "manifest.json"}, added)
        self.assertIn({"path": "not-present.txt"}, added)
        self.assertTrue(all(set(item) == {"path"} for item in added))
        self.assertTrue(report["unchanged"])

    def test_include_added_rejects_unsafe_accepted_paths_before_reading_outside(self):
        _, second = self.inventory_runs()
        accepted_path = self.repo / ".awkit/accepted/inventory/accepted.json"
        record = json.loads(accepted_path.read_text())
        record["files"] = {"../outside.txt": {"size": 0, "sha256": "a" * 64}}
        accepted_path.write_text(json.dumps(record), encoding="utf-8")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("must not read outside artifacts")):
            with self.assertRaises(ValueError):
                compare(self.repo, "inventory", second, include_added=True)

    def test_include_added_rejects_metadata_and_accepted_parent_links(self):
        _, second = self.inventory_runs()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "kept.txt").write_text("outside contents")
        link = second / "artifacts/linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlinks unavailable: {error}")
        record_path = self.repo / ".awkit/accepted/inventory/accepted.json"
        record = json.loads(record_path.read_text())
        original = copy.deepcopy(record)
        record["files"] = {"linked/kept.txt": {"size": 0, "sha256": "a" * 64}}
        record_path.write_text(json.dumps(record), encoding="utf-8")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("must not read linked contents")):
            with self.assertRaises(ValueError):
                compare(self.repo, "inventory", second, include_added=True)
        record_path.write_text(json.dumps(original), encoding="utf-8")
        manifest_path = second / "artifacts/manifest.json"
        metadata = self.root / "external-manifest.json"
        metadata.write_bytes(manifest_path.read_bytes())
        manifest_path.unlink()
        manifest_path.symlink_to(metadata)
        self.inventory_cli(second, expected=0)
        self.inventory_cli(second, True, expected=2)

    def test_cli_verify_exit_codes(self):
        self.configure(["from pathlib import Path; Path('a.txt').write_text('a')"], artifacts=["a.txt"])
        result = check(self.repo, self.head, self.config, self.root / "runs")
        command = [sys.executable, "-m", "awkit", "review", "verify", result["run_dir"]]
        env = child_env()
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
