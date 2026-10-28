import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from awkit.cli import main
from awkit.review import git, storage
from awkit.review_storage import _linked, inspect


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "store"
        self.store.mkdir()

    def run_record(self, name="review-a", payloads=None, status="passed"):
        run = self.store / name
        run.mkdir()
        result = dict(snapshot="a" * 40, config_sha256="b" * 64, subdir=".",
                      run_dir=str(run), status=status, worktree_retained=False)
        (run / "config.toml").write_text("schema = 1\n", encoding="utf-8")
        (run / "01.log").write_text("checked\n", encoding="utf-8")
        if payloads is not None:
            files = {}
            for relative, content in payloads.items():
                path = run / "artifacts" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                files[relative] = dict(size=len(content), sha256=hashlib.sha256(content).hexdigest())
            (run / "artifacts").mkdir(exist_ok=True)
            result["artifacts"] = files
            self.write(run / "artifacts/manifest.json", dict(schema=1, run_id=name, snapshot=result["snapshot"],
                                                            config_sha256=result["config_sha256"], subdir=".", files=files))
        self.write(run / "result.json", result)
        return run

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def manifest(self, run):
        return json.loads((run / "artifacts/manifest.json").read_text())

    def state(self, root):
        return {p.relative_to(root).as_posix(): (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
                for p in [root, *root.rglob("*")]}

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["review", "--repo", str(self.root), "storage", *args])
        return code, out.getvalue(), err.getvalue()

    def test_observed_categories_duplicates_and_determinism_without_mutation(self):
        a = self.run_record("review-z", {"a.txt": b"same", "nested/b.txt": b"else"})
        self.run_record("review-a", {"c.txt": b"same"}, status="failed")
        (a / "worktree").mkdir()
        (a / "worktree/input.txt").write_bytes(b"12345")
        (a / "notes.txt").write_bytes(b"123")
        before = self.state(self.store)
        report = inspect(self.store)
        self.assertEqual(report, inspect(self.store))
        self.assertEqual(before, self.state(self.store))
        self.assertTrue(report["complete"])
        self.assertEqual([r["name"] for r in report["runs"]], ["review-a", "review-z"])
        self.assertEqual(report["observed"]["total_bytes"], sum(len(value[1]) for value in before.values() if value[1] is not None))
        self.assertEqual(report["observed"]["worktree"], dict(bytes=5, files=1))
        self.assertEqual(report["observed"]["other"], dict(bytes=3, files=1))
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 12)
        self.assertEqual(report["manifests"]["unique_recorded_payload_bytes"], 8)
        self.assertEqual(report["manifests"]["duplicate_declared_bytes"], 4)
        self.assertEqual(report["recorded_status_counts"], {"failed": 1, "passed": 1})

    def test_all_recorded_statuses_are_valid_even_when_review_failed(self):
        for index, status in enumerate(("running", "passed", "failed", "uncertain", "cleanup-failed")):
            self.run_record(f"review-{index}", status=status)
        report = inspect(self.store)
        self.assertTrue(report["complete"])
        self.assertEqual(report["manifests"]["valid_runs"], 0)
        self.assertEqual(report["run_count"], 5)
        self.assertTrue(all(r["metadata"]["manifest"] == "absent" for r in report["runs"]))

    def test_conflicting_hash_sizes_exclude_every_declaration(self):
        self.run_record("review-a", {"a": b"a"})
        b = self.run_record("review-b", {"b": b"bb"})
        manifest = self.manifest(b)
        manifest["files"]["b"]["sha256"] = hashlib.sha256(b"a").hexdigest()
        self.write(b / "artifacts/manifest.json", manifest)
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["manifests"]["declared_payload_bytes"], 3)
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 0)
        self.assertEqual(report["manifests"]["unique_recorded_payload_bytes"], 0)
        self.assertEqual(len(report["manifests"]["conflicting_hashes"]), 1)
        self.assertTrue(all(any(i["code"] == "conflicting-hash-size" for i in r["issues"]) for r in report["runs"]))

    def test_malformed_metadata_does_not_hide_observed_bytes(self):
        run = self.run_record(payloads={"a": b"payload"})
        (run / "result.json").write_text('{"status": ', encoding="utf-8")
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertGreater(report["observed"]["artifacts"]["bytes"], 7)
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 0)

    def test_unhashable_status_is_partial_not_uncaught_error(self):
        run = self.run_record()
        result = json.loads((run / "result.json").read_text())
        result["status"] = []
        self.write(run / "result.json", result)
        self.assertFalse(inspect(self.store)["complete"])

    def test_foreign_manifest_identity_and_schema_are_excluded(self):
        for field, value in (("snapshot", "c" * 40), ("config_sha256", "d" * 64), ("run_id", "review-other"),
                             ("subdir", "other"), ("schema", 2), ("schema", True)):
            with self.subTest(field=field, value=value):
                run = self.run_record(f"review-{len(list(self.store.iterdir()))}", {"a": b"x"})
                manifest = self.manifest(run)
                manifest[field] = value
                self.write(run / "artifacts/manifest.json", manifest)
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 0)

    def test_missing_result_manifest_and_payload_are_explicit(self):
        a = self.run_record("review-a", {"a": b"a"})
        (a / "result.json").unlink()
        b = self.run_record("review-b", {"b": b"b"})
        (b / "artifacts/manifest.json").unlink()
        c = self.run_record("review-c", {"c": b"c"})
        (c / "artifacts/c").unlink()
        d = self.run_record("review-d", {})
        (d / "artifacts/manifest.json").unlink()
        report = inspect(self.store)
        self.assertTrue(all(not r["complete"] for r in report["runs"]))
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 0)

    def test_invalid_declarations_unexpected_and_mismatched_sizes(self):
        run = self.run_record(payloads={"good": b"a", "wrong": b"bb", "unrecorded": b"ccc"})
        manifest = self.manifest(run)
        del manifest["files"]["unrecorded"]
        manifest["files"]["wrong"]["size"] = 3
        for name in ("../escape", "/absolute", "C:/outside", "a\\b", "a//b", "a/./b"):
            manifest["files"][name] = dict(size=1, sha256="a" * 64)
        manifest["files"]["boolean"] = dict(size=True, sha256="a" * 64)
        manifest["files"]["negative"] = dict(size=-1, sha256="a" * 64)
        manifest["files"]["hash"] = dict(size=1, sha256="not-a-hash")
        self.write(run / "artifacts/manifest.json", manifest)
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 1)
        codes = {i["code"] for i in report["runs"][0]["issues"]}
        self.assertTrue({"invalid-declaration", "artifact-size-unavailable", "unrecorded-artifact"} <= codes)

    def test_duplicate_json_keys_and_nonfinite_numbers_are_invalid(self):
        for index, data in enumerate(('{"status":"passed","status":"failed"}', '{"status":NaN}')):
            run = self.run_record(f"review-{index}")
            (run / "result.json").write_text(data, encoding="utf-8")
        self.assertFalse(inspect(self.store)["complete"])

    def test_only_direct_named_directories_and_metadata_are_read(self):
        self.run_record(payloads={"payload.json": b"not json"})
        ignored = self.store / "other" / "review-nested"
        ignored.mkdir(parents=True)
        (ignored / "result.json").write_text("invalid")
        (self.store / "review-file").write_bytes(b"ignored")
        real_open = os.open
        opened = []

        def observed_open(path, *args, **kwargs):
            opened.append(Path(path).name)
            return real_open(path, *args, **kwargs)

        with patch("awkit.review_storage.os.open", side_effect=observed_open):
            report = inspect(self.store)
        self.assertTrue(report["complete"])
        self.assertEqual(report["run_count"], 1)
        self.assertEqual(opened, ["result.json", "manifest.json"])

    def test_child_permission_and_disappearance_keep_other_runs(self):
        bad = self.run_record("review-bad", {"a": b"abc"})
        self.run_record("review-good")
        real_scan = os.scandir

        def denied(path):
            if Path(path) == bad / "artifacts":
                raise PermissionError("fixture denied")
            return real_scan(path)

        with patch("awkit.review_storage.os.scandir", side_effect=denied):
            report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["run_count"], 2)
        self.assertTrue(any(i["code"] == "scan-error" for i in report["runs"][0]["issues"]))
        original = Path.lstat

        def gone(path):
            if path == bad / "01.log":
                raise FileNotFoundError("fixture disappeared")
            return original(path)

        with patch.object(Path, "lstat", gone):
            report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertTrue(any(i["code"] == "stat-error" for i in report["runs"][0]["issues"]))

    def test_metadata_replacement_is_detected_before_reading(self):
        run = self.run_record()
        actual_open = os.open

        def replace_before_open(path, *args, **kwargs):
            path = Path(path)
            if path.name == "result.json":
                path.rename(path.with_suffix(".old"))
                path.write_text('{"foreign":"do not read"}')
            return actual_open(path, *args, **kwargs)

        with patch("awkit.review_storage.os.open", side_effect=replace_before_open):
            report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertIsNone(report["runs"][0]["recorded_status"])
        self.assertTrue((run / "result.old").is_file())

    def test_directory_replacement_is_reported_without_counting_new_entries(self):
        run = self.run_record(payloads={"a": b"abc"})
        actual_scan = os.scandir
        artifacts = run / "artifacts"

        def replaced(path):
            if Path(path) == artifacts:
                artifacts.rename(run / "original")
                artifacts.mkdir()
                (artifacts / "unrelated").write_bytes(b"new directory")
            return actual_scan(path)

        with patch("awkit.review_storage.os.scandir", side_effect=replaced):
            report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["observed"]["artifacts"]["bytes"], 0)
        self.assertTrue(any(i["code"] == "changed-directory" for i in report["runs"][0]["issues"]))

    def test_metadata_permission_error_is_partial_and_keeps_file_sizes(self):
        self.run_record(payloads={"a": b"abc"})
        with patch("awkit.review_storage.os.open", side_effect=PermissionError("fixture denied")):
            report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertGreater(report["observed"]["total_bytes"], 3)
        self.assertEqual(report["manifests"]["counted_files"], 0)

    def test_root_disappearance_is_unavailable_not_absent(self):
        with patch("awkit.review_storage.os.scandir", side_effect=FileNotFoundError("fixture disappeared")):
            with self.assertRaisesRegex(ValueError, "Cannot inspect"):
                inspect(self.store, default=True)

    def test_links_are_skipped_and_external_target_is_unchanged(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "secret.json").write_text("outside")
        run = self.run_record()
        links = ((self.store / "review-linked", outside), (run / "artifacts", outside))
        try:
            for path, target in links:
                path.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("creating symlinks is not permitted")
        before = self.state(outside)
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["run_count"], 1)
        self.assertEqual(report["observed"]["artifacts"]["bytes"], 0)
        self.assertEqual(before, self.state(outside))
        for path, _ in links:
            path.unlink()

    def test_windows_reparse_attribute_is_rejected_independent_of_mode(self):
        self.assertTrue(_linked(SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)))
        self.assertTrue(_linked(SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)))

    def test_reserved_names_that_are_files_count_as_other(self):
        run = self.run_record()
        (run / "artifacts").write_bytes(b"not a directory")
        (run / "worktree").write_bytes(b"also a file")
        report = inspect(self.store)
        self.assertEqual(report["observed"]["artifacts"]["bytes"], 0)
        self.assertEqual(report["observed"]["worktree"]["bytes"], 0)
        self.assertEqual(report["observed"]["other"]["bytes"], 26)

    def test_exhausted_walk_depth_reports_partial_coverage(self):
        run = self.run_record()
        actual_scan = os.scandir

        def too_deep(path):
            if Path(path) == run:
                raise RecursionError("fixture traversal depth")
            return actual_scan(path)

        with patch("awkit.review_storage.os.scandir", side_effect=too_deep):
            report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertTrue(any(i["code"] == "scan-error" for i in report["runs"][0]["issues"]))

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_windows_junction_is_not_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "sentinel").write_bytes(b"outside")
        run = self.run_record()
        link = run / "worktree"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        if result.returncode:
            self.skipTest("junction creation unavailable")
        try:
            report = inspect(self.store)
            self.assertFalse(report["complete"])
            self.assertEqual(report["observed"]["worktree"]["bytes"], 0)
            self.assertTrue(any(i["code"] == "skipped-link" for i in report["runs"][0]["issues"]))
            self.assertEqual((outside / "sentinel").read_bytes(), b"outside")
        finally:
            link.rmdir()

    def test_default_root_absent_is_read_only_and_uses_git_top_level(self):
        repo = self.root / "repo"
        repo.mkdir()
        git(repo, "init")
        git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "commit", "--allow-empty", "-m", "fixture")
        subdir = repo / "subdir"
        subdir.mkdir()
        before = self.state(repo)
        report = storage(subdir)
        self.assertEqual(report["status"], "absent")
        self.assertEqual(report["root"], str((repo / ".awkit/reviews").resolve()))
        self.assertEqual(before, self.state(repo))
        self.assertFalse((repo / ".awkit").exists())

    def test_explicit_root_errors_cli_exits_and_empty_store(self):
        self.assertEqual(self.cli("--runs-root", str(self.root / "missing"), "--json")[0], 2)
        with patch("awkit.review_storage.os.scandir", side_effect=PermissionError("fixture denied")):
            self.assertEqual(self.cli("--runs-root", str(self.store))[0], 2)
        code, out, _ = self.cli("--runs-root", str(self.store), "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["run_count"], 0)
        run = self.run_record(status="failed")
        self.assertEqual(self.cli("--runs-root", str(self.store))[0], 0)
        (run / "result.json").unlink()
        code, out, _ = self.cli("--runs-root", str(self.store), "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["status"], "partial")

    def test_text_displays_exact_and_readable_sizes_and_largest_run_label(self):
        self.run_record(payloads={"large": b"x" * 2048})
        code, text, _ = self.cli("--runs-root", str(self.store))
        self.assertEqual(code, 0)
        self.assertIn("2048 bytes (2.00 KiB)", text)
        self.assertIn("Largest runs:\n", text)
        self.assertIn("runs: 1", text)


if __name__ == "__main__":
    unittest.main()
