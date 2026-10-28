"""Portable review exports, interruption boundaries and independent legacy verification."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from awkit.artifact_store import ObjectStore, SafeRoot, declaration, encode
from awkit.review import check, git, verify
from awkit.review_export import (
    EXPORT_METADATA,
    MANIFEST,
    ORIGINAL_MANIFEST,
    ORIGINAL_RESULT,
    PROVENANCE,
    PROVENANCE_FILE,
    export_metadata,
    export_run,
    validate_export,
)
from awkit.review_storage import inspect
from support import child_env

# Unmodified verify() source from f167f42:src/awkit/review.py. This frozen reader
# deliberately knows nothing about shared stores or export provenance.
LEGACY_VERIFY_SOURCE = '''def verify(run_dir):
    """Compare the artifacts retained by `check` with the manifest written at that time."""
    run = Path(run_dir).resolve()
    record_path = run / "result.json"
    if not record_path.is_file():
        raise ValueError(f"No result.json in the run folder: {run}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    report = {"run_dir": str(run), "snapshot": record.get("snapshot"),
              "config_sha256": record.get("config_sha256"), "check_status": record.get("status"),
              "interrupted": record.get("status") == "running", "artifacts": [], "unexpected": []}
    manifest_path = run / "artifacts" / "manifest.json"
    expected = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != 1 or not isinstance(manifest.get("files"), dict):
            raise ValueError("The artifact manifest is not in a known format.")
        if manifest.get("snapshot") != record.get("snapshot"):
            raise ValueError("The artifact manifest belongs to a different snapshot than result.json.")
        expected = manifest["files"]
    for relative, entry in sorted(expected.items()):
        path = run / "artifacts" / PurePosixPath(relative)
        item = {"path": relative, "status": "ok"}
        if path.is_symlink() or not path.is_file():
            item["status"] = "missing"
        else:
            data = path.read_bytes()
            if len(data) != entry.get("size") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                item["status"] = "changed"
        report["artifacts"].append(item)
    folder = run / "artifacts"
    if folder.is_dir():
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(folder).as_posix()
            if path.is_file() and relative != "manifest.json" and relative not in expected:
                report["unexpected"].append(relative)
    report["verified"] = (not report["interrupted"] and not report["unexpected"]
                          and all(item["status"] == "ok" for item in report["artifacts"]))
    return report
'''
_legacy_globals = dict(Path=Path, PurePosixPath=PurePosixPath, json=json, hashlib=hashlib)
exec(LEGACY_VERIFY_SOURCE, _legacy_globals)
legacy_verify = _legacy_globals["verify"]


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.collection = self.root / "collection"
        self.collection.mkdir()
        self.run = self.collection / "review-fixture"
        self.run.mkdir()
        self.destination = self.root / "exported evidence"

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else encode(data))

    def fixture(self, *, mode="shared", status="passed", local=True):
        config = ('schema = 1\nartifact_storage = "' + mode + '"\n').encode()
        self.write(self.run / "config.toml", config)
        self.write(self.run / "01.log", b"exact log\r\n\x00")
        self.write(self.run / "notes/detail.txt", b"direct run output")
        self.write(self.run / "worktree/source.txt", b"must not export")
        files = {"report.txt": declaration(b"report\r\n"), "nested/한글.bin": declaration(b"\0\xff\xfe")}
        local_files = {"diagnostic.txt": declaration(b"failure details")} if local else {}
        manifest = dict(schema=2 if mode == "shared" else 1, snapshot="a" * 40,
            config_sha256=hashlib.sha256(config).hexdigest(), subdir="", run_id=self.run.name, files=files)
        result = dict(run_id=self.run.name, snapshot=manifest["snapshot"], config_sha256=manifest["config_sha256"],
            subdir="", run_dir=str(self.run), worktree=str(self.run / "worktree"), worktree_retained=True,
            status=status, steps=[dict(name="fixture", status=status, log="01.log")], artifacts=files,
            artifact_storage=mode)
        if mode == "shared":
            store = ObjectStore(self.collection, create=True)
            store.put(b"report\r\n")
            store.put(b"\0\xff\xfe")
            manifest.update(local_files=local_files, storage=dict(kind="sha256", collection_id=store.collection_id))
            for name in local_files:
                self.write(self.run / "artifacts" / name, b"failure details")
        else:
            self.write(self.run / "artifacts/report.txt", b"report\r\n")
            self.write(self.run / "artifacts/nested/한글.bin", b"\0\xff\xfe")
        manifest_raw = encode(manifest)
        if mode == "shared":
            result["artifact_publication"] = dict(state="complete", collection_id=store.collection_id,
                manifest_sha256=hashlib.sha256(manifest_raw).hexdigest())
        self.write(self.run / MANIFEST, manifest_raw)
        self.write(self.run / "result.json", result)
        return result, manifest

    def real_run(self, *, mode="copy", code="pass", artifacts=(), keep=False):
        repo = self.root / "real source"
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.name", "Fixture")
        git(repo, "config", "user.email", "fixture@localhost")
        (repo / "source.txt").write_text("source", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "Fixture")
        config = self.root / "real-checks.toml"
        config.write_text('schema = 1\nartifact_storage = ' + json.dumps(mode)
            + '\nartifacts = ' + json.dumps(artifacts) + '\n[[checks]]\nname = "produce"\nargv = '
            + json.dumps(["{python}", "-c", code]) + '\n', encoding="utf-8")
        result = check(repo, "HEAD", config, self.collection, keep=keep)
        self.run = Path(result["run_dir"])
        return result

    def test_shared_export_verifies_without_collection_and_preserves_identity_and_bytes(self):
        original, manifest = self.fixture()
        original_result = (self.run / "result.json").read_bytes()
        original_manifest = (self.run / MANIFEST).read_bytes()
        report = export_run(self.run, self.destination)
        self.assertEqual(report["status"], "exported")
        self.assertFalse((self.destination / "worktree").exists())
        self.assertEqual((self.destination / "01.log").read_bytes(), b"exact log\r\n\x00")
        self.assertEqual((self.destination / "notes/detail.txt").read_bytes(), b"direct run output")
        self.assertEqual((self.destination / ORIGINAL_RESULT).read_bytes(), original_result)
        self.assertEqual((self.destination / ORIGINAL_MANIFEST).read_bytes(), original_manifest)
        result = json.loads((self.destination / "result.json").read_text(encoding="utf-8"))
        for key in ("run_id", "snapshot", "config_sha256", "subdir", "status", "steps"):
            self.assertEqual(result[key], original[key])
        self.assertEqual(result["artifact_storage"], "copy")
        self.assertEqual(result["artifact_publication"]["manifest_sha256"],
                         hashlib.sha256((self.destination / MANIFEST).read_bytes()).hexdigest())
        provenance = json.loads((self.destination / PROVENANCE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(provenance["artifacts"]["diagnostic.txt"]["association"], "direct-diagnostic")
        self.assertEqual(provenance["artifacts"]["report.txt"]["association"], "configured")
        exported_manifest = json.loads((self.destination / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(exported_manifest["files"], {**manifest["files"], **manifest["local_files"]})
        self.collection.rename(self.root / "unavailable original collection")
        self.assertTrue(legacy_verify(self.destination)["verified"])
        self.assertEqual(validate_export(self.destination)["status"], "passed")
        self.assertTrue(verify(self.destination)["verified"])

    def test_materialized_files_are_independent_and_changes_are_detected(self):
        original, _ = self.fixture()
        store = ObjectStore(self.collection)
        obj = store.files.root / "objects" / original["artifacts"]["report.txt"]["sha256"]
        export_run(self.run, self.destination)
        copied = self.destination / "artifacts/report.txt"
        self.assertFalse(copied.samefile(obj))
        copied.write_bytes(b"edited")
        self.assertEqual(obj.read_bytes(), b"report\r\n")
        self.assertTrue(verify(self.run)["verified"])
        self.assertFalse(legacy_verify(self.destination)["verified"])
        with self.assertRaises(ValueError):
            validate_export(self.destination)

    def test_failed_check_with_complete_evidence_can_export(self):
        self.fixture(status="failed")
        export_run(self.run, self.destination)
        self.assertTrue(legacy_verify(self.destination)["verified"])
        self.assertEqual(validate_export(self.destination)["status"], "failed")

    def test_copied_input_retains_original_schema_and_legacy_readability(self):
        self.fixture(mode="copy", local=False)
        export_run(self.run, self.destination)
        provenance = json.loads((self.destination / PROVENANCE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(provenance["original_manifest"]["schema"], 1)
        self.assertEqual(provenance["source_storage"], "copy")
        self.assertTrue(legacy_verify(self.destination)["verified"])
        self.assertEqual(validate_export(self.destination)["artifact_storage"], "copy")

    def test_real_artifactless_copied_run_exports_with_explicit_original_manifest_absence(self):
        original = self.real_run(code="import os; from pathlib import Path; "
            "(Path(os.environ['AWKIT_RUN_DIR'])/'diagnostic.txt').write_text('no artifacts configured')")
        self.assertTrue(verify(self.run)["verified"])
        self.assertFalse((self.run / MANIFEST).exists())
        exported_collection = self.root / "export collection"
        exported_collection.mkdir()
        destination = exported_collection / "review-exported"
        export_run(self.run, destination)
        self.assertFalse((destination / ORIGINAL_MANIFEST).exists())
        provenance = json.loads((destination / PROVENANCE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(provenance["original_manifest"], dict(present=False, path=None))
        self.assertNotIn(ORIGINAL_MANIFEST, provenance["evidence_files"])
        self.assertEqual(json.loads((destination / MANIFEST).read_text(encoding="utf-8"))["files"], {})
        self.assertEqual(json.loads((destination / ORIGINAL_RESULT).read_text(encoding="utf-8")), original)
        self.assertEqual((destination / "diagnostic.txt").read_text(), "no artifacts configured")
        self.collection.rename(self.root / "source unavailable")
        self.assertTrue(legacy_verify(destination)["verified"])
        self.assertTrue(verify(destination)["verified"])
        report = inspect(exported_collection)
        self.assertTrue(report["complete"], report)
        self.assertEqual(report["runs"][0]["metadata"]["manifest"], "valid")
        self.assertTrue(report["runs"][0]["metadata"]["exported"])

    def test_missing_expected_original_manifest_is_not_treated_as_original_absence(self):
        self.fixture()
        export_run(self.run, self.destination)
        (self.destination / ORIGINAL_MANIFEST).unlink()
        with self.assertRaisesRegex(ValueError, "not explicitly declared absent"):
            validate_export(self.destination)

    def test_missing_copied_manifest_with_patterns_is_refused(self):
        self.real_run(code="from pathlib import Path; Path('report.txt').write_text('report')", artifacts=("report.txt",))
        (self.run / MANIFEST).unlink()
        with self.assertRaisesRegex(ValueError, "artifactless"):
            export_run(self.run, self.destination)
        self.assertFalse(self.destination.exists())

    @unittest.skipUnless(os.name == "nt", "Windows managed-directory case aliases")
    def test_real_uppercase_artifacts_and_worktree_are_managed_on_windows(self):
        self.real_run(mode="shared", artifacts=("report.txt",), keep=True,
            code="import os; from pathlib import Path; Path('report.txt').write_text('report'); "
                 "p=Path(os.environ['AWKIT_RUN_DIR'])/'ARTIFACTS'; p.mkdir(); "
                 "(p/'diagnostic.txt').write_text('direct diagnostic')")
        self.assertTrue(verify(self.run)["verified"])
        self.assertIn("ARTIFACTS", os.listdir(self.run))
        (self.run / "worktree").rename(self.run / "renaming-tree")
        (self.run / "renaming-tree").rename(self.run / "WORKTREE")
        self.assertIn("WORKTREE", os.listdir(self.run))
        export_run(self.run, self.destination)
        self.assertFalse(any(name.casefold() == "worktree" for name in os.listdir(self.destination)))
        self.assertEqual((self.destination / "artifacts/diagnostic.txt").read_text(), "direct diagnostic")
        self.assertTrue(legacy_verify(self.destination)["verified"])
        self.assertTrue(verify(self.destination)["verified"])

    @unittest.skipUnless(os.name == "nt", "Windows managed-metadata case aliases")
    def test_real_uppercase_metadata_preserves_other_manifest_named_diagnostics(self):
        self.real_run(mode="shared", artifacts=("report.txt",),
            code="import os; from pathlib import Path; Path('report.txt').write_text('report'); "
                 "r=Path(os.environ['AWKIT_RUN_DIR']); (r/'MANIFEST.JSON').write_text('root diagnostic'); "
                 "p=r/'artifacts'/'nested'; p.mkdir(parents=True); "
                 "(p/'MANIFEST.JSON').write_text('nested diagnostic')")
        for name in ("result.json", "config.toml"):
            path = self.run / name
            path.rename(path.with_name("renaming-metadata"))
            path.with_name("renaming-metadata").rename(path.with_name(name.upper()))
        self.assertTrue(verify(self.run)["verified"])
        manifest = self.run / MANIFEST
        manifest.rename(manifest.with_name("renaming-metadata"))
        manifest.with_name("renaming-metadata").rename(manifest.with_name("MANIFEST.JSON"))
        self.assertTrue(verify(self.run)["verified"])
        export_run(self.run, self.destination)
        self.assertEqual((self.destination / "MANIFEST.JSON").read_text(), "root diagnostic")
        self.assertEqual((self.destination / "artifacts/nested/MANIFEST.JSON").read_text(), "nested diagnostic")
        self.assertTrue(legacy_verify(self.destination)["verified"])
        self.assertTrue(verify(self.destination)["verified"])

    @unittest.skipIf(os.name == "nt", "Linux case-distinct direct evidence")
    def test_case_distinct_uppercase_worktree_is_preserved_on_linux(self):
        self.fixture()
        self.write(self.run / "WORKTREE/direct.txt", b"case-distinct diagnostic")
        export_run(self.run, self.destination)
        self.assertFalse((self.destination / "worktree").exists())
        self.assertEqual((self.destination / "WORKTREE/direct.txt").read_bytes(), b"case-distinct diagnostic")
        self.assertTrue(verify(self.destination)["verified"])

    def test_existing_destination_is_refused_without_changing_contents(self):
        self.fixture()
        self.destination.mkdir()
        sentinel = self.destination / "keep.txt"
        sentinel.write_bytes(b"untouched")
        with self.assertRaisesRegex(ValueError, "already exists"):
            export_run(self.run, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"untouched")

    def test_destination_race_cannot_overwrite_the_other_writer(self):
        self.fixture()

        def occupy(destination):
            destination.mkdir()
            (destination / "other.txt").write_bytes(b"another writer")

        with patch("awkit.review_export._prepare_output", side_effect=occupy), self.assertRaises(FileExistsError):
            export_run(self.run, self.destination)
        self.assertEqual((self.destination / "other.txt").read_bytes(), b"another writer")
        self.assertFalse((self.destination / "result.json").exists())

    def test_replaced_destination_parent_is_rejected_without_writing_through_it(self):
        self.fixture()
        parent = self.root / "exports"
        parent.mkdir()
        destination = parent / "bundle"

        def replace_parent(_):
            parent.rename(self.root / "original exports")
            parent.mkdir()
            (parent / "keep.txt").write_bytes(b"replacement")

        with patch("awkit.review_export._prepare_output", side_effect=replace_parent), self.assertRaisesRegex(ValueError, "root changed"):
            export_run(self.run, destination)
        self.assertFalse(destination.exists())
        self.assertFalse((self.root / "original exports/bundle").exists())
        self.assertEqual((parent / "keep.txt").read_bytes(), b"replacement")

    def test_two_processes_compete_for_one_destination_without_merging(self):
        self.fixture()
        code = '''import json, sys, time
from pathlib import Path
import awkit.review_export as module
ready, release, source, destination = map(Path, sys.argv[1:])
def wait_for_peer(_):
    ready.write_text('ready')
    deadline = time.monotonic() + 15
    while not release.exists():
        if time.monotonic() >= deadline:
            raise ValueError('export fixture peer did not arrive')
        time.sleep(.01)
module._prepare_output = wait_for_peer
try:
    print(json.dumps(module.export_run(source, destination)))
except (OSError, ValueError) as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(2)
'''
        ready = [self.root / f"ready-{index}" for index in range(2)]
        release = self.root / "release"
        children = [subprocess.Popen([sys.executable, "-c", code, str(path), str(release),
                                      str(self.run), str(self.destination)], env=child_env(),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
                    for path in ready]
        try:
            deadline = time.monotonic() + 15
            while not all(path.exists() for path in ready) and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(all(path.exists() for path in ready), "both exporters must reach destination publication")
            release.write_bytes(b"go")
            outputs = [child.communicate(timeout=20) for child in children]
            self.assertEqual(sorted(child.returncode for child in children), [0, 2], outputs)
            self.assertTrue(legacy_verify(self.destination)["verified"])
            validate_export(self.destination)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()

    def test_partial_claimed_export_is_retained_without_a_verifiable_result(self):
        self.fixture()
        write_new = SafeRoot.write_new

        def fail_output(target, name, data):
            if target.root == self.destination and name == "config.toml":
                raise OSError("injected export interruption")
            return write_new(target, name, data)

        with patch.object(SafeRoot, "write_new", fail_output), self.assertRaisesRegex(ValueError, "incomplete at"):
            export_run(self.run, self.destination)
        self.assertTrue(self.destination.is_dir())
        self.assertTrue(any(self.destination.iterdir()))
        self.assertFalse((self.destination / "result.json").exists())
        with self.assertRaisesRegex(ValueError, "No result.json"):
            legacy_verify(self.destination)

    def test_source_metadata_mutation_is_rejected_before_destination_claim(self):
        self.fixture()
        write_new = SafeRoot.write_new

        def mutate(target, name, data):
            result = write_new(target, name, data)
            if name == PROVENANCE_FILE:
                path = self.run / "result.json"
                record = json.loads(path.read_text(encoding="utf-8"))
                record["status"] = "failed"
                self.write(path, record)
            return result

        with patch.object(SafeRoot, "write_new", mutate), self.assertRaisesRegex(ValueError, "changed"):
            export_run(self.run, self.destination)
        self.assertFalse(self.destination.exists())

    def test_destination_mutation_prevents_result_publication(self):
        self.fixture()
        write_new = SafeRoot.write_new

        def mutate(target, name, data):
            result = write_new(target, name, data)
            if target.root == self.destination and name == "notes/detail.txt":
                (self.destination / "artifacts/report.txt").write_bytes(b"changed")
            return result

        with patch.object(SafeRoot, "write_new", mutate), self.assertRaisesRegex(ValueError, "incomplete at"):
            export_run(self.run, self.destination)
        self.assertFalse((self.destination / "result.json").exists())

    def test_source_direct_output_mutation_after_copy_is_rejected(self):
        self.fixture()
        write_new = SafeRoot.write_new

        def mutate(target, name, data):
            result = write_new(target, name, data)
            if name == PROVENANCE_FILE:
                (self.run / "notes/detail.txt").write_bytes(b"changed after copy")
            return result

        with patch.object(SafeRoot, "write_new", mutate), self.assertRaisesRegex(ValueError, "changed"):
            export_run(self.run, self.destination)
        self.assertFalse(self.destination.exists())

    def test_incomplete_publication_is_refused_with_diagnostics_untouched(self):
        result, _ = self.fixture(status="failed")
        result["artifact_publication"]["state"] = "incomplete"
        self.write(self.run / "result.json", result)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            export_run(self.run, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.run / "artifacts/diagnostic.txt").read_bytes(), b"failure details")

    def test_reserved_provenance_collision_preserves_diagnostic(self):
        self.fixture()
        for name in (PROVENANCE, PROVENANCE.upper()):
            with self.subTest(name=name):
                path = self.run / name
                path.write_bytes(b"direct diagnostic")
                with self.assertRaisesRegex(ValueError, "provenance"):
                    export_run(self.run, self.destination)
                self.assertEqual(path.read_bytes(), b"direct diagnostic")
                path.unlink()
        self.assertFalse(self.destination.exists())

    def test_corrupted_shared_object_prevents_export(self):
        result, _ = self.fixture()
        store = ObjectStore(self.collection)
        (store.files.root / "objects" / result["artifacts"]["report.txt"]["sha256"]).write_bytes(b"broken!!")
        with self.assertRaisesRegex(ValueError, "corrupt"):
            export_run(self.run, self.destination)
        self.assertFalse(self.destination.exists())

    def test_unexpected_artifacts_are_not_silently_blessed_by_export(self):
        self.fixture()
        (self.run / "artifacts/unrecorded.txt").write_bytes(b"not declared")
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            export_run(self.run, self.destination)
        self.assertFalse(self.destination.exists())

    def test_destination_inside_source_is_rejected(self):
        self.fixture()
        with self.assertRaisesRegex(ValueError, "inside the source"):
            export_run(self.run, self.run / "nested export")
        self.assertFalse((self.run / "nested export").exists())

    def test_linked_direct_evidence_is_not_followed(self):
        self.fixture()
        outside = self.root / "outside.txt"
        outside.write_bytes(b"outside")
        try:
            (self.run / "linked.txt").symlink_to(outside)
        except OSError as exc:
            self.skipTest("Symlink creation unavailable: " + str(exc))
        with self.assertRaisesRegex(ValueError, "Linked|linked"):
            export_run(self.run, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(outside.read_bytes(), b"outside")

    @unittest.skipUnless(os.name == "nt", "Windows junction containment")
    def test_windows_junction_direct_evidence_is_not_followed(self):
        self.fixture()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_bytes(b"outside")
        junction = self.run / "junction"
        created = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True)
        self.assertEqual(created.returncode, 0, created.stderr)
        try:
            with self.assertRaisesRegex(ValueError, "reparse"):
                export_run(self.run, self.destination)
            self.assertFalse(self.destination.exists())
            self.assertEqual((outside / "keep.txt").read_bytes(), b"outside")
        finally:
            junction.rmdir()

    def test_provenance_and_original_identity_tampering_fail_current_validation(self):
        self.fixture()
        export_run(self.run, self.destination)
        original = self.destination / ORIGINAL_RESULT
        raw = original.read_bytes()
        original.write_bytes(raw.replace(b'"passed"', b'"failed"'))
        with self.assertRaisesRegex(ValueError, "Original export evidence changed"):
            validate_export(self.destination)

    def test_metadata_inventory_validation_opens_no_payloads(self):
        self.fixture()
        export_run(self.run, self.destination)
        raw = {name: (self.destination / name).read_bytes() for name in EXPORT_METADATA}
        with patch.object(SafeRoot, "read", side_effect=AssertionError("metadata validator must not open files")):
            self.assertEqual(export_metadata(raw)["run_id"], self.run.name)
        altered = json.loads(raw["result.json"])
        altered["status"] = "failed"
        raw["result.json"] = encode(altered)
        with self.assertRaisesRegex(ValueError, "original evidence identity"):
            export_metadata(raw)

    def test_cli_exports_without_repository_context(self):
        self.fixture()
        process = subprocess.run([sys.executable, "-m", "awkit", "review", "export", str(self.run),
                                  "--output", str(self.destination)], cwd=self.root, env=child_env(),
                                 capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "exported")
        self.assertTrue(legacy_verify(self.destination)["verified"])
