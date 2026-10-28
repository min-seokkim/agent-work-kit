"""Shared payload publication and existing-reader behavior on disposable repositories."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from awkit.artifact_store import STORE, ObjectStore, SafeRoot, SharedRun, declaration, encode, relative
from awkit.review import accept, check, compare, git, verify
from support import child_env


class SharedArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "source project"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@localhost")
        (self.repo / "seed.txt").write_text("source", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "Fixture")
        self.revision = git(self.repo, "rev-parse", "HEAD")
        self.collection = self.root / "collection"
        self.config = self.root / "checks.toml"

    def make_run(self, payload=b"payload", *, code=None, artifacts=("out.txt",), required=(), mode="shared", keep=False):
        code = code or f"from pathlib import Path; Path('out.txt').write_bytes({payload!r})"
        setting = "" if mode is None else "artifact_storage = " + json.dumps(mode) + "\n"
        self.config.write_text("schema = 1\n" + setting + "artifacts = " + json.dumps(artifacts)
            + "\nrequired_artifacts = " + json.dumps(required) + '\n[[checks]]\nname = "produce"\nargv = '
            + json.dumps(["{python}", "-c", code]) + "\n", encoding="utf-8")
        return check(self.repo, self.revision, self.config, self.collection, keep=keep)

    def object_path(self, result, name="out.txt"):
        return self.collection / STORE / "objects" / result["artifacts"][name]["sha256"]

    def read_result(self, run):
        return json.loads((Path(run) / "result.json").read_text(encoding="utf-8"))

    def test_descriptor_loss_does_not_mint_identity_or_change_objects(self):
        first = self.make_run()
        descriptor = self.collection / STORE / "store.json"
        original = descriptor.read_bytes()
        payload = self.object_path(first).read_bytes()
        descriptor.unlink()
        with self.assertRaisesRegex(ValueError, "descriptor"):
            self.make_run()
        self.assertFalse(descriptor.exists())
        self.assertEqual(self.object_path(first).read_bytes(), payload)
        descriptor.write_bytes(original)
        self.assertTrue(verify(first["run_dir"])["verified"])

    def test_corrupt_or_missing_shared_comparison_is_integrity_error_without_diff(self):
        run = self.make_run()
        accept(self.repo, run["run_dir"])
        target = self.object_path(run)
        for defect in ("corrupt", "missing"):
            with self.subTest(defect=defect):
                if defect == "corrupt":
                    target.write_bytes(b"changed")
                else:
                    target.unlink()
                report = compare(self.repo, run_dir=run["run_dir"], diff=True)
                self.assertFalse(report["unchanged"])
                self.assertEqual(report["files"][0]["status"], "integrity-error")
                self.assertNotIn("diff", report["files"][0])
        command = [sys.executable, "-m", "awkit", "review", "--repo", str(self.repo), "compare",
                   "--run", run["run_dir"], "--diff"]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=child_env())
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["files"][0]["status"], "integrity-error")

    def test_collision_is_failed_incomplete_and_preserves_diagnostic_and_worktree(self):
        result = self.make_run(code="import os; from pathlib import Path; Path('out.txt').write_text('configured'); "
            "p=Path(os.environ['AWKIT_RUN_DIR'])/'artifacts'; p.mkdir(); (p/'out.txt').write_text('diagnostic')")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["artifact_publication"]["state"], "incomplete")
        self.assertIn("out.txt", result["artifact_publication"]["collisions"])
        self.assertEqual((Path(result["run_dir"]) / "artifacts/out.txt").read_text(), "diagnostic")
        self.assertTrue(result["worktree_retained"])
        self.assertEqual((Path(result["worktree"]) / "out.txt").read_text(), "configured")
        self.assertFalse((Path(result["run_dir"]) / "artifacts/manifest.json").exists())
        with self.assertRaises(ValueError):
            verify(result["run_dir"])

    def test_missing_legacy_run_keeps_original_errors(self):
        missing = self.root / "no run"
        with self.assertRaisesRegex(ValueError, "No result.json"):
            verify(missing)
        with self.assertRaisesRegex(ValueError, "No result.json"):
            accept(self.repo, missing)
        run = self.make_run(mode="copy")
        accept(self.repo, run["run_dir"])
        with self.assertRaisesRegex(ValueError, "no retained artifacts"):
            compare(self.repo, run_dir=missing)

    def test_added_inventory_includes_declared_direct_diagnostics_without_reading_them(self):
        first = self.make_run()
        accept(self.repo, first["run_dir"])
        second = self.make_run(code="import os; from pathlib import Path; Path('out.txt').write_bytes(b'payload'); "
            "p=Path(os.environ['AWKIT_RUN_DIR'])/'artifacts'; p.mkdir(); (p/'diagnostic.txt').write_text('detail')")
        original = SharedRun.read

        def guarded(reader, name, **kwargs):
            if name == "diagnostic.txt":
                raise AssertionError("added inventory must not open added diagnostic bytes")
            return original(reader, name, **kwargs)

        with patch.object(SharedRun, "read", guarded):
            report = compare(self.repo, run_dir=second["run_dir"], include_added=True)
        self.assertTrue(report["unchanged"])
        self.assertEqual(report["added_artifacts"]["files"], [dict(path="diagnostic.txt")])

    def test_identical_payloads_share_one_object_and_accepted_bytes_are_independent(self):
        first, second = self.make_run(), self.make_run()
        changed = self.make_run(b"different")
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["artifacts"], second["artifacts"])
        self.assertEqual(len(list((self.collection / STORE / "objects").iterdir())), 2)
        self.assertFalse((Path(first["run_dir"]) / "artifacts/out.txt").exists())
        for run in (first, second, changed):
            self.assertTrue(verify(run["run_dir"])["verified"])
        accepted = accept(self.repo, first["run_dir"])
        materialized = Path(accepted["folder"]) / "out.txt"
        self.assertFalse(materialized.samefile(self.object_path(first)))
        materialized.write_bytes(b"local edit")
        self.assertEqual(self.object_path(first).read_bytes(), b"payload")
        self.assertTrue(verify(second["run_dir"])["verified"])
        report = compare(self.repo, run_dir=changed["run_dir"], diff=True)
        self.assertEqual(report["files"][0]["status"], "changed")
        self.assertIn("+different", report["files"][0]["diff"])

    def test_failed_check_can_have_complete_verified_artifacts(self):
        result = self.make_run(code="from pathlib import Path; Path('out.txt').write_bytes(b'failure evidence'); "
            "raise SystemExit(7)")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["artifact_publication"]["state"], "complete")
        self.assertTrue(verify(result["run_dir"])["verified"])
        self.assertEqual(verify(result["run_dir"])["check_status"], "failed")

    def test_copied_default_is_preserved_and_invalid_modes_do_not_start(self):
        default = self.make_run(mode=None)
        copied = self.make_run(mode="copy")
        for result in (default, copied):
            self.assertEqual(result["artifact_storage"], "copy")
            self.assertEqual((Path(result["run_dir"]) / "artifacts/out.txt").read_bytes(), b"payload")
            self.assertTrue(verify(result["run_dir"])["verified"])
        self.assertFalse((self.collection / STORE).exists())
        before = set(self.collection.iterdir())
        for mode in ("unknown", True, [], {}):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.make_run(mode=mode)
            self.assertEqual(set(self.collection.iterdir()), before)

    def test_existing_corrupt_object_is_never_repaired_or_reused(self):
        first = self.make_run()
        target = self.object_path(first)
        target.write_bytes(b"damaged")
        with self.assertRaisesRegex(ValueError, "corrupt"):
            self.make_run()
        self.assertEqual(target.read_bytes(), b"damaged")
        latest = sorted(self.collection.glob("review-*/result.json"), key=lambda p: p.stat().st_mtime_ns)[-1]
        result = json.loads(latest.read_text())
        self.assertEqual(result["status"], "uncertain")
        self.assertEqual(result["artifact_publication"]["state"], "incomplete")
        self.assertFalse(verify(first["run_dir"])["verified"])

    def test_empty_store_descriptor_loss_is_not_reinitialized(self):
        result = self.make_run(artifacts=())
        descriptor = self.collection / STORE / "store.json"
        descriptor.unlink()
        self.assertEqual(list((self.collection / STORE / "objects").iterdir()), [])
        with self.assertRaisesRegex(ValueError, "descriptor"):
            ObjectStore(self.collection, create=True)
        self.assertFalse(descriptor.exists())
        with self.assertRaises(ValueError):
            verify(result["run_dir"])

    def test_two_process_descriptor_and_payload_publication_races(self):
        code = """
import json, sys
from pathlib import Path
from awkit.artifact_store import ObjectStore, SafeRoot
collection, ready, payload = Path(sys.argv[1]), Path(sys.argv[2]), bytes.fromhex(sys.argv[3])
original = SafeRoot.link_new
def synchronized(self, source, destination):
    phase = 'descriptor' if destination == 'store.json' else 'object'
    ready.with_suffix('.' + phase).touch()
    if sys.stdin.readline().strip() != 'go':
        raise RuntimeError('publication barrier not released')
    return original(self, source, destination)
SafeRoot.link_new = synchronized
store = ObjectStore(collection, create=True)
entry = store.put(payload)
print(json.dumps({'identity': store.collection_id, 'entry': entry, 'bytes': store.read(entry).hex()}))
"""
        for same in (True, False):
            with self.subTest(same=same):
                collection = self.root / ("same" if same else "different")
                collection.mkdir()
                payloads = [b"first", b"first" if same else b"second"]
                children = []
                try:
                    for index, payload in enumerate(payloads):
                        ready = collection / f"ready-{index}"
                        children.append(subprocess.Popen([sys.executable, "-c", code, str(collection), str(ready), payload.hex()],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", env=child_env()))
                    for phase in ("descriptor", "object"):
                        deadline = time.monotonic() + 30
                        while not all((collection / f"ready-{index}.{phase}").exists() for index in range(2)):
                            for child in children:
                                if child.poll() is not None:
                                    self.fail("writer exited before " + phase + ": " + child.communicate()[1])
                            if time.monotonic() > deadline:
                                self.fail("writers did not reach " + phase + " publication barrier")
                            time.sleep(0.01)
                        for child in children:
                            child.stdin.write("go\n")
                            child.stdin.flush()
                    results = []
                    for child in children:
                        output, errors = child.communicate(timeout=30)
                        self.assertEqual(child.returncode, 0, errors)
                        results.append(json.loads(output))
                    self.assertEqual(results[0]["identity"], results[1]["identity"])
                    self.assertEqual([bytes.fromhex(r["bytes"]) for r in results], payloads)
                    self.assertEqual(len(list((collection / STORE / "objects").iterdir())), 1 if same else 2)
                    self.assertEqual(list((collection / STORE / "staging").iterdir()), [])
                finally:
                    for child in children:
                        if child.poll() is None:
                            child.kill()
                        child.communicate(timeout=10)

    def test_process_exit_before_and_after_manifest_never_commits_partial_collection(self):
        first = self.make_run()
        original_object = self.object_path(first).read_bytes()
        code = """
import os, sys
from awkit.artifact_store import SafeRoot
from awkit.review import check
original = SafeRoot.write_new
def interrupted(self, name, data):
    if name == 'artifacts/manifest.json' and sys.argv[5] == 'before':
        os._exit(23)
    original(self, name, data)
    if name == 'artifacts/manifest.json':
        os._exit(23)
SafeRoot.write_new = interrupted
check(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
"""
        for phase in ("before", "after"):
            with self.subTest(phase=phase):
                previous = set(self.collection.glob("review-*"))
                child = subprocess.run([sys.executable, "-c", code, str(self.repo), self.revision,
                    str(self.config), str(self.collection), phase], capture_output=True, text=True,
                    encoding="utf-8", env=child_env(), timeout=30)
                self.assertEqual(child.returncode, 23, child.stderr)
                run, = set(self.collection.glob("review-*")) - previous
                result = self.read_result(run)
                self.assertEqual(result["status"], "running")
                self.assertEqual(result["artifact_publication"]["state"], "pending")
                self.assertEqual((run / "artifacts/manifest.json").exists(), phase == "after")
                self.assertTrue((run / "worktree").exists())
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    verify(run)
                self.assertEqual(self.object_path(first).read_bytes(), original_object)
                self.assertTrue(verify(first["run_dir"])["verified"])

    def test_missing_and_mismatched_shared_metadata_fails_closed(self):
        result = self.make_run()
        run = Path(result["run_dir"])
        accept(self.repo, run)
        for name in ("result.json", "artifacts/manifest.json", "config.toml"):
            with self.subTest(missing=name):
                path = run / name
                raw = path.read_bytes()
                path.unlink()
                try:
                    for operation in (lambda: verify(run), lambda: accept(self.repo, run),
                                      lambda: compare(self.repo, run_dir=run)):
                        with self.assertRaises((ValueError, OSError)):
                            operation()
                finally:
                    path.write_bytes(raw)
        manifest_path, result_path = run / "artifacts/manifest.json", run / "result.json"
        manifest_raw, result_raw = manifest_path.read_bytes(), result_path.read_bytes()
        for field, value in (("run_id", "review-foreign"), ("snapshot", "0" * 40),
                             ("config_sha256", "0" * 64), ("subdir", "other"), ("schema", True)):
            with self.subTest(field=field):
                manifest = json.loads(manifest_raw)
                manifest[field] = value
                raw = encode(manifest)
                record = json.loads(result_raw)
                record["artifact_publication"]["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
                manifest_path.write_bytes(raw)
                result_path.write_bytes(encode(record))
                with self.assertRaises(ValueError):
                    verify(run)
        manifest_path.write_bytes(manifest_raw)
        result_path.write_bytes(result_raw)
        self.assertTrue(verify(run)["verified"])

    def test_shared_manifest_cannot_be_downgraded_to_legacy_comparison(self):
        result = self.make_run()
        run = Path(result["run_dir"])
        accept(self.repo, run)
        record = self.read_result(run)
        record.pop("artifact_storage")
        record.pop("artifact_publication")
        (run / "result.json").write_bytes(encode(record))
        with self.assertRaisesRegex(ValueError, "storage mode disagree"):
            compare(self.repo, run_dir=run)

    def test_invalid_shared_declarations_and_unknown_modes_are_rejected(self):
        result = self.make_run()
        run = Path(result["run_dir"])
        manifest_path, result_path = run / "artifacts/manifest.json", run / "result.json"
        manifest_raw, result_raw = manifest_path.read_bytes(), result_path.read_bytes()
        entries = [("../outside", declaration(b"payload")), ("out.txt", dict(size=True, sha256="0" * 64)),
                   ("out.txt", dict(size=7, sha256="bad")), ("NUL.txt", declaration(b"payload"))]
        for name, entry in entries:
            with self.subTest(name=name, entry=entry):
                manifest = json.loads(manifest_raw)
                record = json.loads(result_raw)
                manifest["files"] = record["artifacts"] = {name: entry}
                raw = encode(manifest)
                record["artifact_publication"]["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
                manifest_path.write_bytes(raw)
                result_path.write_bytes(encode(record))
                with self.assertRaises(ValueError):
                    verify(run)
        manifest_path.write_bytes(manifest_raw)
        for mode in (None, {}, "future", "copy"):
            record = json.loads(result_raw)
            record["artifact_storage"] = mode
            result_path.write_bytes(encode(record))
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify(run)
        result_path.write_bytes(result_raw)

    def test_direct_manifest_and_directory_collisions_preserve_evidence(self):
        for name, directory in (("manifest.json", False), ("manifest.json", True), ("out.txt", True), ("OUT.TXT", False)):
            with self.subTest(name=name, directory=directory):
                code = "import os; from pathlib import Path; Path('out.txt').write_bytes(b'configured'); "
                code += f"p=Path(os.environ['AWKIT_RUN_DIR'])/'artifacts'/{name!r}; p.parent.mkdir(); "
                code += "p.mkdir(); (p/'detail').write_bytes(b'direct')" if directory else "p.write_bytes(b'direct')"
                result = self.make_run(code=code)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["artifact_publication"]["state"], "incomplete")
                self.assertIn(name, result["artifact_publication"]["collisions"])
                direct = Path(result["run_dir"]) / "artifacts" / name
                self.assertEqual((direct / "detail" if directory else direct).read_bytes(), b"direct")

    def test_missing_configured_path_is_distinct_from_broken_shared_object(self):
        first = self.make_run()
        accept(self.repo, first["run_dir"])
        second = self.make_run(artifacts=())
        report = compare(self.repo, run_dir=second["run_dir"], diff=True)
        self.assertEqual(report["files"], [dict(path="out.txt", status="missing")])
        self.assertFalse(report["unchanged"])

    def test_moved_and_copied_collection_keep_identity_but_lone_run_fails(self):
        result = self.make_run()
        run_name = Path(result["run_dir"]).name
        moved, copied = self.root / "moved", self.root / "copied"
        self.collection.rename(moved)
        self.assertTrue(verify(moved / run_name)["verified"])
        shutil.copytree(moved, copied)
        self.assertTrue(verify(copied / run_name)["verified"])
        lone = self.root / "lone" / run_name
        shutil.copytree(copied / run_name, lone)
        with self.assertRaises(ValueError):
            verify(lone)
        descriptor = copied / STORE / "store.json"
        value = json.loads(descriptor.read_bytes())
        value["collection_id"] = "0" * 32
        descriptor.write_bytes(encode(value))
        with self.assertRaisesRegex(ValueError, "not this run"):
            verify(copied / run_name)

    def test_permission_and_disappearing_source_do_not_complete_collection(self):
        original = SafeRoot.read
        for error in (PermissionError("denied fixture"), FileNotFoundError("disappeared fixture")):
            def broken(reader, name, expected=None, failure=error):
                if reader.root.name == "worktree" and name == "out.txt":
                    raise failure
                return original(reader, name, expected)
            with self.subTest(error=type(error).__name__), patch.object(SafeRoot, "read", broken):
                previous = set(self.collection.glob("review-*"))
                with self.assertRaises(type(error)):
                    self.make_run()
                run, = set(self.collection.glob("review-*")) - previous
                result = self.read_result(run)
                self.assertEqual(result["artifact_publication"]["state"], "incomplete")
                self.assertEqual(result["status"], "uncertain")
                self.assertTrue(result["worktree_retained"])

    def test_portable_paths_reject_traversal_and_windows_aliases(self):
        for name in ("../secret", "/root", "a\\b", "C:foo", "NUL", "con.txt", "a.", "a ", "a//b", ".git/key"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                relative(name)

    def test_symlink_object_and_parent_are_not_followed(self):
        result = self.make_run()
        target = self.object_path(result)
        outside = self.root / "outside"
        outside.mkdir()
        payload = outside / target.name
        payload.write_bytes(b"payload")
        probe = self.root / "probe"
        try:
            probe.symlink_to(payload)
        except OSError as exc:
            self.skipTest("native symlink creation unavailable: " + str(exc))
        probe.unlink()
        target.unlink()
        target.symlink_to(payload)
        self.assertFalse(verify(result["run_dir"])["verified"])
        target.unlink()
        objects = target.parent
        objects.rmdir()
        objects.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            verify(result["run_dir"])
        self.assertEqual(payload.read_bytes(), b"payload")

    @unittest.skipUnless(os.name == "nt", "Windows reparse-point containment")
    def test_windows_junction_and_live_parent_replacement_are_blocked(self):
        result = self.make_run()
        objects = self.object_path(result).parent
        outside = self.root / "outside"
        objects.rename(outside)
        subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(objects), str(outside)],
                       check=True, capture_output=True)
        try:
            with self.assertRaises(ValueError):
                verify(result["run_dir"])
        finally:
            objects.rmdir()
            outside.rename(objects)
        safe = SafeRoot(self.collection / STORE)
        with safe.parent("objects/" + self.object_path(result).name):
            with self.assertRaises(PermissionError):
                objects.rename(outside)
        self.assertTrue(verify(result["run_dir"])["verified"])

    @unittest.skipIf(os.name == "nt", "POSIX descriptor-relative parent replacement")
    def test_posix_parent_replacement_is_detected_without_following_link(self):
        result = self.make_run()
        objects = self.object_path(result).parent
        outside, retained = self.root / "outside", self.root / "retained"
        outside.mkdir()
        sentinel = outside / self.object_path(result).name
        sentinel.write_bytes(b"outside secret")
        safe = SafeRoot(self.collection / STORE)
        with self.assertRaisesRegex(ValueError, "parent changed"):
            with safe.parent("objects/" + sentinel.name) as (name, descriptor):
                objects.rename(retained)
                objects.symlink_to(outside, target_is_directory=True)
                with os.fdopen(os.open(name, os.O_RDONLY, dir_fd=descriptor), "rb") as stream:
                    self.assertEqual(stream.read(), b"payload")
        self.assertEqual(sentinel.read_bytes(), b"outside secret")
