import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from awkit.cli import main
from awkit.review import check, git, storage
from awkit.review_export import export_run
from awkit.review_storage import CATEGORIES, STORE_CATEGORIES, _linked, inspect, text


def summary_fixture():
    """Representative partial/shared report; no filesystem scan or private inputs."""
    def sizes(categories, **values):
        data = {name: {'bytes': 0, 'files': 0} for name in categories}
        for name, value in values.items():
            data[name] = {'bytes': value, 'files': 1}
        data['total_bytes'] = sum(data[name]['bytes'] for name in categories)
        data['total_files'] = sum(data[name]['files'] for name in categories)
        return data


    def run(name, storage='copied', manifest='absent', issues=None):
        shared = storage == 'shared'
        return {
            'name': name, 'complete': not issues, 'recorded_status': 'passed',
            'observed': sizes(CATEGORIES, records=1), 'issues': issues or [],
            'metadata': {'result': 'valid', 'manifest': manifest, 'storage': storage,
                         'declared_files': int(shared), 'declared_payload_bytes': 4 if shared else 0,
                         'counted_files': int(shared), 'counted_payload_bytes': 4 if shared else 0},
            'shared_references': {'declared_files': int(shared), 'declared_payload_bytes': 4 if shared else 0,
                                  'counted_files': int(shared), 'counted_payload_bytes': 4 if shared else 0},
        }

    runs = [run(f'review-missing-{i:03}', manifest='invalid', issues=[{
        'path': 'artifacts/manifest.json', 'code': 'invalid-metadata',
        'detail': 'Metadata is missing or was not safely inventoried.'
    }]) for i in range(126)]
    runs += [run(f'review-artifactless-{i:02}') for i in range(20)]
    runs += [run(f'review-shared-{i:02}', storage='shared', manifest='valid') for i in range(2)]
    runs.sort(key=lambda entry: entry['name'])
    store_observed = sizes(STORE_CATEGORIES, objects=4, metadata=93)
    report = {
        'schema': 2, 'root': 'synthetic-review-collection',
        'selection': 'direct review-* directories and collection-local shared store',
        'status': 'partial', 'complete': False, 'run_count': len(runs),
        'observed': sizes(CATEGORIES, records=148),
        'collection_observed': {'total_bytes': 148 + store_observed['total_bytes'], 'total_files': 150},
        'recorded_status_counts': {'passed': 148}, 'runs': runs,
        'largest_runs': [{'name': entry['name'], 'bytes': 1} for entry in runs[:10]],
        'issues': [{'path': 'review-unreadable', 'code': 'stat-error', 'detail': 'Synthetic distinct filesystem error.'}],
        'shared_store': {
            'present': True, 'descriptor': 'valid', 'issues': [], 'observed': store_observed,
            'reference_coverage_complete': False,
            'reference_scope': 'Valid readable manifests in the selected direct review-* directories.',
            'referenced_objects': {'bytes': 4, 'files': 1},
            'unreferenced_objects': {'bytes': 0, 'files': 0, 'hashes': []},
        },
        'metadata_coverage': {'valid_results': 148, 'valid_manifests': 2, 'artifactless_runs': 20},
        'manifests': {'valid_runs': 2, 'declared_files': 2, 'declared_payload_bytes': 8,
                      'counted_files': 2, 'counted_payload_bytes': 8, 'unique_recorded_hashes': 1,
                      'unique_recorded_payload_bytes': 4, 'duplicate_declared_bytes': 4, 'conflicting_hashes': []},
        'limits': [
            'Logical file sizes, not allocated disk usage or recoverable space.',
            'Recorded payload hashes are unverified; payloads were not read or rehashed.',
            'Live filesystem inspection is not an atomic snapshot.',
            'Unreferenced objects are relative to valid readable manifests, not proven reclaimable bytes.',
        ],
    }
    report['observed']['records']['files'] = 148
    report['observed']['total_files'] = 148
    return report


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
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

    def shared_record(self, name="review-a", payloads=None, local=None, status="passed"):
        run = self.run_record(name, status=status)
        shared = self.store / ".awkit-artifacts"
        (shared / "objects").mkdir(parents=True, exist_ok=True)
        self.write(shared / "store.json", dict(schema=1, kind="sha256", collection_id="c" * 32))
        files, diagnostics = {}, {}
        for path, data in (payloads or {}).items():
            digest = hashlib.sha256(data).hexdigest()
            (shared / "objects" / digest).write_bytes(data)
            files[path] = dict(size=len(data), sha256=digest)
        (run / "artifacts").mkdir()
        for path, data in (local or {}).items():
            target = run / "artifacts" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            diagnostics[path] = dict(size=len(data), sha256=hashlib.sha256(data).hexdigest())
        result = json.loads((run / "result.json").read_text())
        result.update(run_id=name, artifact_storage="shared", artifacts=files,
                      config_sha256=hashlib.sha256((run / "config.toml").read_bytes()).hexdigest())
        manifest = dict(schema=2, run_id=name, snapshot=result["snapshot"], config_sha256=result["config_sha256"],
                        subdir=result["subdir"], files=files, local_files=diagnostics,
                        storage=dict(kind="sha256", collection_id="c" * 32))
        self.write(run / "artifacts/manifest.json", manifest)
        self.publish_shared_manifest(run, result)
        return run

    def publish_shared_manifest(self, run, result=None):
        result = result or json.loads((run / "result.json").read_text())
        result["artifact_publication"] = dict(state="complete", collection_id="c" * 32,
                                               manifest_sha256=hashlib.sha256((run / "artifacts/manifest.json").read_bytes()).hexdigest())
        self.write(run / "result.json", result)

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

    def test_shared_objects_count_once_with_run_local_diagnostics_and_staging(self):
        self.shared_record("review-a", {"a": b"same", "nested/b": b"same"}, {"failure.txt": b"diagnostic"})
        self.shared_record("review-b", {"c": b"same", "changed": b"different"}, status="failed")
        shared = self.store / ".awkit-artifacts"
        (shared / "staging").mkdir()
        (shared / "staging/payload-fixture").write_bytes(b"partial")
        before = self.state(self.store)
        report = inspect(self.store)
        self.assertEqual(report, inspect(self.store))
        self.assertEqual(before, self.state(self.store))
        self.assertEqual(report["schema"], 2)
        self.assertTrue(report["complete"])
        self.assertEqual(report["shared_store"]["observed"]["objects"], dict(bytes=13, files=2))
        self.assertEqual(report["shared_store"]["observed"]["staging"], dict(bytes=7, files=1))
        self.assertEqual(report["shared_store"]["observed"]["metadata"]["files"], 1)
        self.assertEqual(report["runs"][0]["shared_references"], dict(declared_files=2, declared_payload_bytes=8,
                                                                   counted_files=2, counted_payload_bytes=8))
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 31)
        self.assertEqual(report["manifests"]["unique_recorded_payload_bytes"], 23)
        self.assertEqual(report["manifests"]["duplicate_declared_bytes"], 8)
        self.assertEqual(report["shared_store"]["referenced_objects"], dict(bytes=13, files=2))
        self.assertEqual(report["shared_store"]["unreferenced_objects"]["bytes"], 0)
        self.assertEqual(report["collection_observed"]["total_bytes"],
                         sum(len(value[1]) for value in before.values() if value[1] is not None))
        self.assertEqual(report["collection_observed"]["total_bytes"], report["observed"]["total_bytes"]
                         + report["shared_store"]["observed"]["total_bytes"])

    def test_shared_inventory_reads_metadata_and_config_without_payloads(self):
        self.shared_record(payloads={"payload": b"same"}, local={"diagnostic.txt": b"local"})
        actual_open, opened = os.open, []

        def metadata_only(path, *args, **kwargs):
            name = Path(path).name
            self.assertIn(name, {"store.json", "result.json", "manifest.json", "config.toml"})
            opened.append(name)
            return actual_open(path, *args, **kwargs)

        with patch("awkit.review_storage.os.open", side_effect=metadata_only):
            report = inspect(self.store)
        self.assertTrue(report["complete"])
        self.assertCountEqual(opened, ["store.json", "result.json", "manifest.json", "config.toml"])

    def test_shared_and_legacy_runs_keep_local_totals_and_logical_hash_metrics_distinct(self):
        legacy = self.run_record("review-copy", {"original": b"same"})
        self.shared_record("review-shared", {"shared": b"same"})
        report = inspect(self.store)
        self.assertTrue(report["complete"])
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 8)
        self.assertEqual(report["manifests"]["duplicate_declared_bytes"], 4)
        self.assertEqual(report["shared_store"]["observed"]["objects"]["bytes"], 4)
        self.assertEqual(report["runs"][0]["shared_references"]["counted_files"], 0)
        self.assertEqual((legacy / "artifacts/original").read_bytes(), b"same")

    def test_unreferenced_objects_are_qualified_when_a_run_is_unreadable(self):
        run = self.shared_record(payloads={"payload": b"used"})
        orphan = hashlib.sha256(b"orphan").hexdigest()
        shared = self.store / ".awkit-artifacts"
        (shared / "objects" / orphan).write_bytes(b"orphan")
        report = inspect(self.store)
        self.assertTrue(report["shared_store"]["reference_coverage_complete"])
        self.assertEqual(report["shared_store"]["unreferenced_objects"], dict(hashes=[orphan], files=1, bytes=6))
        (run / "artifacts/manifest.json").write_bytes(b"unreadable")
        report = inspect(self.store)
        self.assertFalse(report["shared_store"]["reference_coverage_complete"])
        self.assertEqual(report["shared_store"]["unreferenced_objects"]["bytes"], 10)
        self.assertTrue(any("not proven reclaimable" in limit for limit in report["limits"]))

    def test_shared_missing_or_wrong_sized_objects_keep_references_and_partial_coverage(self):
        self.shared_record(payloads={"missing": b"missing", "changed": b"original"})
        objects = self.store / ".awkit-artifacts/objects"
        (objects / hashlib.sha256(b"missing").hexdigest()).unlink()
        (objects / hashlib.sha256(b"original").hexdigest()).write_bytes(b"short")
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["runs"][0]["shared_references"]["declared_payload_bytes"], 15)
        self.assertEqual(report["runs"][0]["shared_references"]["counted_payload_bytes"], 0)
        self.assertEqual(report["shared_store"]["unreferenced_objects"]["files"], 0)
        self.assertEqual(report["shared_store"]["referenced_objects"], dict(bytes=5, files=1))

    def test_shared_manifest_publication_and_config_hashes_are_required(self):
        for index, target in enumerate(("config.toml", "artifacts/manifest.json", "publication")):
            with self.subTest(target=target):
                run = self.shared_record(f"review-{index}", {"payload": b"same"})
                if target == "publication":
                    result = json.loads((run / "result.json").read_text())
                    result["artifact_publication"]["state"] = "pending"
                    self.write(run / "result.json", result)
                else:
                    with (run / target).open("ab") as stream:
                        stream.write(b"\n")
                report = inspect(self.store)
                current = next(r for r in report["runs"] if r["name"] == run.name)
                self.assertEqual(current["metadata"]["manifest"], "invalid")
                self.assertEqual(current["shared_references"]["declared_files"], 0)
                self.assertFalse(report["shared_store"]["reference_coverage_complete"])

    def test_shared_descriptor_identity_and_missing_descriptor_are_not_guessed(self):
        self.shared_record(payloads={"payload": b"same"})
        descriptor = self.store / ".awkit-artifacts/store.json"
        self.write(descriptor, dict(schema=1, kind="sha256", collection_id="d" * 32))
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["shared_store"]["unreferenced_objects"]["bytes"], 4)
        descriptor.unlink()
        report = inspect(self.store)
        self.assertEqual(report["shared_store"]["descriptor"], "invalid")
        self.assertEqual(report["shared_store"]["observed"]["objects"]["bytes"], 4)
        self.assertFalse(report["shared_store"]["reference_coverage_complete"])

    def test_shared_store_and_object_links_are_skipped(self):
        self.shared_record(payloads={"payload": b"same"})
        objects = self.store / ".awkit-artifacts/objects"
        object_path = objects / hashlib.sha256(b"same").hexdigest()
        outside = self.root / "outside-payload"
        outside.write_bytes(b"same")
        object_path.unlink()
        try:
            object_path.symlink_to(outside)
        except OSError:
            self.skipTest("creating symlinks is not permitted")
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["shared_store"]["observed"]["objects"]["bytes"], 0)
        self.assertEqual(outside.read_bytes(), b"same")
        self.assertTrue(any(i["code"] == "skipped-link" for i in report["shared_store"]["issues"]))

    def test_shared_store_staging_unknown_names_and_partial_scan_are_visible(self):
        self.shared_record(payloads={"payload": b"same"})
        shared = self.store / ".awkit-artifacts"
        (shared / "objects/not-an-object").write_bytes(b"unknown")
        (shared / "staging").mkdir()
        (shared / "staging/descriptor-incomplete").write_bytes(b"partial")
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["shared_store"]["observed"]["objects"], dict(files=2, bytes=11))
        self.assertEqual(report["shared_store"]["observed"]["staging"]["bytes"], 7)
        self.assertEqual(report["shared_store"]["unreferenced_objects"]["bytes"], 0)
        actual_scan = os.scandir

        def denied(path):
            if Path(path) == shared / "objects":
                raise PermissionError("fixture object directory denied")
            return actual_scan(path)

        with patch("awkit.review_storage.os.scandir", side_effect=denied):
            report = inspect(self.store)
        self.assertFalse(report["shared_store"]["reference_coverage_complete"])
        self.assertEqual(report["shared_store"]["observed"]["objects"]["bytes"], 0)

    def test_empty_and_pending_shared_runs_are_not_confused(self):
        complete = self.shared_record("review-empty")
        report = inspect(self.store)
        self.assertTrue(report["complete"])
        self.assertEqual(report["shared_store"]["observed"]["objects"], dict(bytes=0, files=0))
        result = json.loads((complete / "result.json").read_text())
        result["status"] = "running"
        self.write(complete / "result.json", result)
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertFalse(report["shared_store"]["reference_coverage_complete"])

    def test_real_shared_checks_and_moved_collection_are_inspected_without_original_repo(self):
        repo = self.root / "project"
        repo.mkdir()
        git(repo, "init")
        git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "commit", "--allow-empty", "-m", "fixture")
        config = self.root / "shared.toml"
        code = ("from pathlib import Path; import os; Path('out.txt').write_bytes(b'shared'); "
                "folder = Path(os.environ['AWKIT_RUN_DIR']) / 'artifacts'; folder.mkdir(); "
                "(folder / 'diagnostic.txt').write_bytes(b'diagnostic')")
        config.write_text('schema = 1\nartifact_storage = "shared"\nartifacts = ["out.txt"]\n'
                          '[[checks]]\nname = "produce"\nargv = ' + json.dumps([sys.executable, "-c", code]), encoding="utf-8")
        for _ in range(2):
            result = check(repo, "HEAD", config, self.store)
            self.assertEqual(result["status"], "passed", result)
        before = self.state(self.store)
        report = inspect(self.store)
        self.assertTrue(report["complete"], report)
        self.assertEqual(before, self.state(self.store))
        self.assertEqual(report["shared_store"]["observed"]["objects"], dict(bytes=6, files=1))
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 32)
        self.assertTrue(all(r["shared_references"]["counted_payload_bytes"] == 6 for r in report["runs"]))
        moved = self.root / "moved-collection"
        self.store.rename(moved)
        repo.rename(self.root / "unavailable-project")
        moved_report = inspect(moved)
        self.assertTrue(moved_report["complete"], moved_report)
        self.assertEqual(moved_report["collection_observed"], report["collection_observed"])
        self.assertEqual(moved_report["shared_store"]["unreferenced_objects"]["files"], 0)

    def test_conflicting_shared_sizes_remain_referenced_but_not_countable(self):
        self.shared_record("review-a", {"a": b"same"})
        run = self.shared_record("review-b", {"b": b"same"})
        manifest = self.manifest(run)
        manifest["files"]["b"]["size"] = 8
        self.write(run / "artifacts/manifest.json", manifest)
        result = json.loads((run / "result.json").read_text())
        result["artifacts"] = manifest["files"]
        self.publish_shared_manifest(run, result)
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["manifests"]["counted_payload_bytes"], 0)
        self.assertEqual(report["shared_store"]["unreferenced_objects"]["files"], 0)
        self.assertEqual(report["shared_store"]["referenced_objects"], dict(bytes=4, files=1))

    @unittest.skipUnless(os.name == "nt", "Windows managed namespace aliases")
    def test_windows_managed_names_keep_complete_metadata_and_byte_counts(self):
        run = self.shared_record(payloads={"payload": b"same"}, local={"diagnostic.txt": b"local"})
        before = inspect(self.store)
        for name in ("result.json", "config.toml", "artifacts/manifest.json", "artifacts"):
            path = run / name
            path.rename(path.with_name(path.name.upper()))
        observed = self.state(self.store)
        report = inspect(self.store)
        self.assertTrue(report["complete"], report)
        self.assertEqual(self.state(self.store), observed)
        self.assertEqual(report["observed"], before["observed"])
        self.assertEqual(report["manifests"], before["manifests"])
        self.assertEqual(report["shared_store"]["unreferenced_objects"]["files"], 0)

    def test_exported_identity_and_renamed_bundle_use_metadata_without_payload_reads(self):
        source = self.shared_record(payloads={"payload": b"same"}, local={"diagnostic.txt": b"local"})
        destination = self.store / "review-exported"
        export_run(source, destination)
        renamed = self.store / "review-renamed"
        destination.rename(renamed)
        before = self.state(self.store)
        actual_open, opened = os.open, []

        def metadata_only(path, *args, **kwargs):
            name = Path(path).name
            self.assertIn(name, {"store.json", "result.json", "manifest.json", "config.toml", "provenance.json",
                                 "original-result.json", "original-manifest.json"})
            opened.append(name)
            return actual_open(path, *args, **kwargs)

        with patch("awkit.review_storage.os.open", side_effect=metadata_only):
            report = inspect(self.store)
        self.assertTrue(report["complete"], report)
        self.assertEqual(before, self.state(self.store))
        exported = next(r for r in report["runs"] if r["name"] == renamed.name)
        self.assertEqual(exported["metadata"]["manifest"], "valid")
        self.assertTrue(exported["metadata"]["exported"])
        self.assertEqual(exported["shared_references"]["counted_files"], 0)
        self.assertEqual(exported["metadata"]["counted_payload_bytes"], 9)
        self.assertEqual(report["shared_store"]["observed"]["objects"]["bytes"], 4)
        self.assertIn("provenance.json", opened)

    def test_export_marker_cannot_bypass_provenance_association(self):
        source = self.shared_record(payloads={"payload": b"same"})
        exported = self.store / "review-exported"
        export_run(source, exported)
        provenance = exported / ".awkit-export/provenance.json"
        original = provenance.read_bytes()
        for data in (original + b"\n", b"{}"):
            with self.subTest(data=data[:10]):
                provenance.write_bytes(data)
                report = inspect(self.store)
                run = next(r for r in report["runs"] if r["name"] == exported.name)
                self.assertFalse(run["complete"])
                self.assertEqual(run["metadata"]["counted_files"], 0)
                self.assertTrue(any(i["code"] == "invalid-export-metadata" for i in run["issues"]))
        provenance.write_bytes(original)
        result = json.loads((exported / "result.json").read_text())
        result["artifact_export"] = None
        self.write(exported / "result.json", result)
        self.assertFalse(inspect(self.store)["complete"])

    def test_unmarked_legacy_run_still_requires_its_physical_identity(self):
        run = self.run_record(payloads={"a": b"a"})
        run.rename(self.store / "review-other")
        report = inspect(self.store)
        self.assertFalse(report["complete"])
        self.assertEqual(report["runs"][0]["metadata"]["result"], "invalid")


class StorageSummaryTests(unittest.TestCase):
    def invoke(self, *options):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["review", "storage", *options])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_default_text_retains_baseline_bytes(self):
        report = summary_fixture()
        original = json.dumps(report, sort_keys=True)
        expected = "b2e79cca8e1bfea6681f760742b45482cacbc540157d89b463d504688360e39e"
        self.assertEqual(hashlib.sha256(text(report).encode()).hexdigest(), expected)
        self.assertEqual(text(report), text(report, summary=False))
        self.assertEqual(json.dumps(report, sort_keys=True), original)

    def test_summary_retains_every_scalar_qualifier_and_limitation(self):
        report = summary_fixture()
        report["recorded_status_counts"] = {status: index + 1 for index, status in enumerate(
            ("running", "passed", "failed", "uncertain", "cleanup-failed", "unknown"))}
        report["limits"].append("Additional inspection limitation remains visible.")
        original = json.dumps(report, sort_keys=True)
        output = text(report, summary=True)
        prefixes = ("Review storage:", "Inspection:", "Observed run-local", "Observed collection",
                    "Shared store:", "Objects unreferenced", "Metadata coverage:",
                    "Manifest-declared payload:", "Counted manifest payload:",
                    "Unique recorded hash size (unverified):", "Duplicate declared size (not recoverable space):")
        for line in text(report).splitlines():
            if line.startswith(prefixes) or line.startswith(tuple("  " + name + ":" for name in CATEGORIES)) \
                    or line.startswith(tuple("  shared " + name + ":" for name in STORE_CATEGORIES)):
                self.assertIn(line, output)
        for status, count in report["recorded_status_counts"].items():
            self.assertIn(f"{status}={count}", output)
        for limit in report["limits"]:
            self.assertIn(limit, output)
        self.assertIn("reference coverage complete: false", output)
        self.assertIn("Shared logical references per run: 2 rows omitted.", output)
        self.assertIn("Largest runs: 10 rows omitted.", output)
        self.assertIn("Individual issue details: 127 omitted.", output)
        self.assertIn("omit --summary or use --json", output)
        self.assertNotIn("review-missing-", output)
        self.assertNotIn("Synthetic distinct filesystem error", output)
        self.assertEqual(json.dumps(report, sort_keys=True), original)

    def test_issue_counts_distinguish_scopes_and_unique_affected_runs(self):
        report = summary_fixture()
        issue = {"path": "hidden-path", "code": "invalid-metadata", "detail": "hidden-detail"}
        report["issues"].append(issue)
        report["shared_store"]["issues"].append(issue)
        run = next(run for run in report["runs"] if run["issues"])
        run["issues"].append(issue)
        output = text(report, summary=True)
        self.assertIn("Issues: 130; runs with run-scoped issues: 126. Counts are classifications, not causes.", output)
        self.assertIn("collection / invalid-metadata: 1 issue", output)
        self.assertIn("collection / stat-error: 1 issue", output)
        self.assertIn("shared store / invalid-metadata: 1 issue", output)
        self.assertIn("runs / invalid-metadata: 127 issues; affected runs: 126", output)
        self.assertNotIn("hidden-path", output)
        self.assertNotIn("hidden-detail", output)
        report["runs"].reverse()
        report["issues"].reverse()
        self.assertEqual(text(report, summary=True), output)

    def test_no_run_identity_is_inferred_from_root_or_store_issue_paths(self):
        report = summary_fixture()
        for run in report["runs"]:
            run["issues"] = []
        report["shared_store"]["issues"] = [{"code": "scan-error", "path": "review-name", "detail": "denied"}]
        output = text(report, summary=True)
        self.assertIn("Issues: 2; runs with run-scoped issues: 0.", output)

    def test_zero_issues_absent_and_complete_reports_remain_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            for root, default in ((Path(temporary), False), (Path(temporary) / "absent", True)):
                report = inspect(root, default=default)
                output = text(report, summary=True)
                self.assertIn(f"Inspection: {report['status']}; runs: 0", output)
                self.assertIn("Issues: 0; runs with run-scoped issues: 0.", output)
                self.assertIn("Individual issue details: 0 omitted.", output)
                self.assertIn("Shared logical references per run: 0 rows omitted.", output)
                self.assertIn("Largest runs: 0 rows omitted.", output)
                self.assertTrue(all(limit in output for limit in report["limits"]))

    def test_cli_summary_default_and_json_use_the_same_report_and_exits(self):
        report = summary_fixture()
        for status, complete, expected in (("partial", False, 1), ("complete", True, 0), ("absent", True, 0)):
            with self.subTest(status=status):
                report.update(status=status, complete=complete)
                original = json.dumps(report, sort_keys=True)
                with patch("awkit.review.storage", return_value=report) as scan:
                    code, output, error = self.invoke("--summary")
                    self.assertEqual((code, output, error), (expected, text(report, summary=True) + "\n", ""))
                    self.assertEqual(self.invoke(), (expected, text(report) + "\n", ""))
                    self.assertEqual(self.invoke("--json"),
                                     (expected, json.dumps(report, ensure_ascii=False, indent=2) + "\n", ""))
                self.assertEqual(scan.call_count, 3)
                self.assertEqual(scan.call_args_list[0], scan.call_args_list[1])
                self.assertEqual(scan.call_args_list[1], scan.call_args_list[2])
                self.assertEqual(json.dumps(report, sort_keys=True), original)
                self.assertEqual(report["schema"], 2)

    def test_cli_unavailable_keeps_exit_two(self):
        with patch("awkit.review.storage", side_effect=ValueError("cannot inspect fixture")):
            code, output, error = self.invoke("--summary")
        self.assertEqual((code, output), (2, ""))
        self.assertIn("cannot inspect fixture", error)

    def test_cli_rejects_summary_and_json_before_scanning(self):
        for options in (("--summary", "--json"), ("--json", "--summary")):
            with self.subTest(options=options), patch("awkit.review.storage") as scan:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    self.invoke(*options)
                self.assertEqual(caught.exception.code, 2)
                scan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
