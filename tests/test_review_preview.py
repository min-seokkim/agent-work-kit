"""Current-folder selection, collector parity and read-only preview boundaries."""

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from awkit.artifact_store import ObjectStore, SafeRoot, collect
from awkit.cli import main
from awkit.review import check, collect_artifacts, git
from awkit.review_selection import candidates, preview, text
from support import child_env


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "project with spaces"
        self.repo.mkdir()
        git(self.repo, "init")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@localhost")
        self.write("tracked.txt", b"old")
        self.write(".gitignore", b"ignored.txt\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "Fixture")
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.config = self.root / "checks.toml"

    def write(self, name, data):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def configure(self, artifacts=(), required=(), mode="copy", code="raise SystemExit(93)"):
        self.config.write_text("schema = 1\nartifact_storage = " + json.dumps(mode)
            + "\nartifacts = " + json.dumps(artifacts) + "\nrequired_artifacts = " + json.dumps(required)
            + '\n[[setup]]\nname = "prepare"\nargv = ' + json.dumps(["{python}", "-c", code])
            + '\n[[checks]]\nname = "check"\nargv = ["must-not-execute"]\n', encoding="utf-8")

    def cli(self, *args, repo=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["review", "--repo", str(repo or self.repo), "preview", "--config", str(self.config), *args])
        return code, out.getvalue(), err.getvalue()

    def test_union_associations_current_sizes_and_missing_are_observations(self):
        self.write("tracked.txt", b"changed")
        self.write("ignored.txt", b"ignore")
        self.write("added.txt", b"new")
        self.write("nested/deep.txt", b"deep")
        self.configure(["*.txt", "absent*.txt", "*.txt"], ["tracked.txt", "*.txt", "future/*.txt"])
        report = preview(self.repo, self.config)
        self.assertTrue(report["complete"])
        self.assertEqual(report["head"], self.head)
        self.assertEqual(report["scope"], "current-working-tree-before-checks")
        self.assertEqual(report["config_sha256"], hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.assertEqual(report["totals"], dict(files=3, logical_bytes=16, complete=True))
        self.assertEqual([item["path"] for item in report["files"]], ["added.txt", "ignored.txt", "tracked.txt"])
        self.assertEqual(report["files"][-1]["patterns"], ["*.txt", "tracked.txt"])
        self.assertEqual(report["unmatched_optional"], ["absent*.txt"])
        self.assertEqual(report["unmatched_required"], ["future/*.txt"])
        first = report["patterns"][0]
        self.assertEqual((first["optional"], first["required"], first["match_count"]), (True, True, 3))
        code, out, err = self.cli("--json")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out), report)
        self.assertIn("do not predict check failure", text(report))

    def test_preview_does_not_read_payloads_execute_steps_or_mutate_repository(self):
        self.write("untracked.txt", b"payload")
        self.configure(["*.txt"], mode="shared")
        before = {p.relative_to(self.repo).as_posix(): (p.stat().st_mtime_ns, p.read_bytes())
                  for p in self.repo.rglob("*") if p.is_file()}
        original = Path.read_bytes

        def read_config_only(path):
            if path != self.config:
                self.fail("Preview read artifact content: " + str(path))
            return original(path)

        with patch.object(Path, "read_bytes", read_config_only), \
                patch("awkit.review.run_to_files", side_effect=AssertionError("executed a command")), \
                patch("awkit.local_state.prepare", side_effect=AssertionError("changed exclusions")), \
                patch("awkit.artifact_store.ObjectStore", side_effect=AssertionError("opened a store")):
            self.assertTrue(preview(self.repo, self.config)["complete"])
        after = {p.relative_to(self.repo).as_posix(): (p.stat().st_mtime_ns, p.read_bytes())
                 for p in self.repo.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.repo / ".awkit").exists())
        self.assertEqual(len(git(self.repo, "worktree", "list", "--porcelain").split("worktree ")) - 1, 1)

    def test_regular_glob_shapes_match_each_actual_collector(self):
        for name in ("a.txt", "b.TXT", ".hidden.txt", "bracket[1].txt", "nested/c.txt", "nested/deeper/d.txt"):
            self.write(name, name.encode())
        patterns = ["*.txt", "?.txt", "[ab].*", "bracket[[]1].txt", "nested/*", "nested/**/*.txt",
                    "**/*.txt", "**/**/d.txt", "TRACKED.txt", "**", "nested**/*.txt"]
        for mode in ("copy", "shared"):
            for index, pattern in enumerate(patterns):
                with self.subTest(mode=mode, pattern=pattern):
                    self.configure([pattern], ["missing.txt"], mode)
                    run = self.root / f"run-{mode}-{index}"
                    run.mkdir()
                    try:
                        if mode == "copy":
                            files, missing, skipped = collect_artifacts(self.repo, run, [pattern], ["missing.txt"])
                        else:
                            collection = self.root / f"store-{index}"
                            collection.mkdir()
                            store = ObjectStore(collection, create=True)
                            files, missing, skipped, _ = collect(self.repo, run, [pattern], ["missing.txt"], store)
                    except ValueError:
                        # Path.glob grammar and bare ** differ across supported Python versions;
                        # shared collection also refuses the root path yielded by bare **.
                        try:
                            report = preview(self.repo, self.config)
                        except ValueError:
                            continue
                        self.assertFalse(report["complete"], report)
                        continue
                    report = preview(self.repo, self.config)
                    self.assertTrue(report["complete"], report["errors"])
                    self.assertEqual({item["path"]: item["size"] for item in report["files"]},
                                     {name: entry["size"] for name, entry in files.items()})
                    self.assertEqual(report["unmatched_required"], missing)
                    self.assertEqual(report["skipped"], skipped)

    @unittest.skipUnless(sys.version_info[:2] == (3, 12), "Python 3.12 literal enumeration")
    def test_literal_spelling_parent_and_union_match_python312_collectors(self):
        self.write("MixedParent/MixedFile.txt", b"literal")
        optional = ["MixedParent/MixedFile.txt", "mixedparent/mixedfile.txt", "MixedParent/*.txt"]
        required = ["MIXEDPARENT/MIXEDFILE.TXT", "MixedParent/MixedFile.txt"]
        for mode in ("copy", "shared"):
            with self.subTest(mode=mode):
                run = self.root / ("literal-run-" + mode)
                run.mkdir()
                if mode == "copy":
                    files, missing, skipped = collect_artifacts(self.repo, run, optional, required)
                else:
                    collection = self.root / "literal-store"
                    collection.mkdir()
                    files, missing, skipped, _ = collect(self.repo, run, optional, required,
                                                        ObjectStore(collection, create=True))
                self.configure(optional, required, mode)
                report = preview(self.repo, self.config)
                self.assertTrue(report["complete"], report["errors"])
                self.assertEqual({item["path"]: item["size"] for item in report["files"]},
                                 {name: entry["size"] for name, entry in files.items()})
                self.assertEqual(report["totals"], dict(files=1, logical_bytes=7, complete=True))
                self.assertEqual(report["unmatched_required"], missing)
                self.assertEqual(report["skipped"], skipped)
                expected_patterns = [pattern for pattern in dict.fromkeys(optional + required)
                                     if list(self.repo.glob(pattern))]
                self.assertEqual(report["files"][0]["patterns"], expected_patterns)
                for entry in report["patterns"]:
                    self.assertEqual(entry["matches"], sorted(path.relative_to(self.repo).as_posix()
                                                            for path in self.repo.glob(entry["pattern"])))

    @unittest.skipUnless(os.name == "nt" and sys.version_info[:2] == (3, 12),
                         "Windows Python 3.12 Unicode literal enumeration")
    def test_unicode_literals_match_python312_collectors(self):
        names = ["i.txt", "\u0130.txt", "\u0131.txt", "s.txt", "\u017f.txt", "k.txt", "\u212a.txt"]
        for index, name in enumerate(names):
            self.write(f"literal/{index}/{name}", b"literal")
        patterns = ["literal/*/i.txt", "literal/*/s.txt", "literal/*/k.txt"]
        for mode in ("copy", "shared"):
            with self.subTest(mode=mode):
                run = self.root / ("unicode-literal-run-" + mode)
                run.mkdir()
                if mode == "copy":
                    files, _, _ = collect_artifacts(self.repo, run, [], patterns)
                else:
                    collection = self.root / "unicode-literal-store"
                    collection.mkdir()
                    files, _, _, _ = collect(self.repo, run, [], patterns, ObjectStore(collection, create=True))
                self.assertEqual(len(files), 7)
                self.configure([], patterns, mode)
                report = preview(self.repo, self.config)
                self.assertTrue(report["complete"], report["errors"])
                self.assertEqual({item["path"]: item["size"] for item in report["files"]},
                                 {name: entry["size"] for name, entry in files.items()})
                self.assertEqual([entry["match_count"] for entry in report["patterns"]], [3, 2, 2])
                self.assertEqual(report["unmatched_required"], [])

    @unittest.skipUnless(os.name == "nt", "Windows Unicode case-insensitive wildcard matching")
    def test_windows_unicode_ranges_match_both_collectors(self):
        names = ["i.txt", "\u0130.txt", "\u0131.txt", "\u017f.txt", "\u212a.txt", "s.txt", "k.txt", "a.TXT"]
        # Separate directories keep shared storage's case-alias collision rule
        # distinct from the wildcard matching behavior being compared here.
        for index, name in enumerate(names):
            self.write(f"unicode/{index}/{name}", b"payload")
        for mode in ("copy", "shared"):
            for index, (segment, count) in enumerate((("[a-z].txt", 8), ("[s].txt", 2), ("[i].txt", 3))):
                pattern = "unicode/*/" + segment
                with self.subTest(mode=mode, pattern=pattern):
                    expected = {path.relative_to(self.repo).as_posix() for path in self.repo.glob(pattern)}
                    self.assertEqual(len(expected), count)
                    run = self.root / f"unicode-run-{mode}-{index}"
                    run.mkdir()
                    if mode == "copy":
                        files, _, _ = collect_artifacts(self.repo, run, [pattern], [])
                    else:
                        collection = self.root / f"unicode-store-{index}"
                        collection.mkdir()
                        files, _, _, _ = collect(self.repo, run, [pattern], [], ObjectStore(collection, create=True))
                    self.assertEqual(set(files), expected)
                    self.configure([pattern], mode=mode)
                    report = preview(self.repo, self.config)
                    self.assertTrue(report["complete"], report["errors"])
                    self.assertEqual({item["path"] for item in report["files"]}, expected)
                    self.assertEqual(report["patterns"][0]["match_count"], count)

    def test_subdirectory_base_and_generated_after_preview_outputs(self):
        folder = self.repo / "sub"
        self.write("sub/input.txt", b"input")
        git(self.repo, "add", "sub/input.txt")
        git(self.repo, "commit", "-m", "Subdirectory")
        self.configure(["*.txt"], ["generated.txt"])
        report = preview(folder, self.config)
        self.assertEqual((report["base"], report["subdir"]), (str(folder), "sub"))
        self.assertEqual(report["unmatched_required"], ["generated.txt"])
        self.assertEqual([item["path"] for item in report["files"]], ["input.txt"])
        self.config.write_text('schema = 1\nartifacts = ["*.txt"]\nrequired_artifacts = ["generated.txt"]\n'
            '[[checks]]\nname = "generate"\nargv = ' + json.dumps(["{python}", "-c",
            "from pathlib import Path; Path('generated.txt').write_text('later')"]) + "\n", encoding="utf-8")
        result = check(folder, "HEAD", self.config, self.root / "generated-runs")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(set(result["artifacts"]), {"input.txt", "generated.txt"})
        self.assertFalse((folder / "generated.txt").exists())

    def test_invalid_inputs_and_empty_selection_create_nothing(self):
        for settings in ("schema = 2", 'schema = 1\nartifacts = ["../outside"]',
                         'schema = 1\nartifact_storage = "other"'):
            self.config.write_text(settings + '\n[[checks]]\nname = "x"\nargv = ["never"]\n', encoding="utf-8")
            self.assertEqual(self.cli()[0], 2)
            self.assertFalse((self.repo / ".awkit").exists())
        self.configure()
        report = preview(self.repo, self.config)
        self.assertEqual(report["totals"], dict(files=0, logical_bytes=0, complete=True))
        self.assertTrue(report["complete"])
        self.assertEqual(self.cli(repo=self.root)[0], 2)
        self.assertEqual(self.cli(repo=self.root / "missing")[0], 2)

    def test_metadata_errors_are_partial_not_silently_empty(self):
        self.write("nested/item.txt", b"item")
        self.configure(["nested/*.txt"], ["nested/*.txt"])
        original = os.scandir

        nested_info = (self.repo / "nested").stat()

        def denied_directory(path):
            # Deny the selected directory, even when literal parent segments
            # are enumerated first or POSIX supplies an anchored descriptor.
            info = os.fstat(path) if isinstance(path, int) else Path(path).stat()
            if (info.st_dev, info.st_ino) == (nested_info.st_dev, nested_info.st_ino):
                raise PermissionError("injected enumeration denial")
            return original(path)

        with patch("awkit.review_selection.os.scandir", denied_directory):
            code, out, _ = self.cli("--json")
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertFalse(report["complete"])
        self.assertFalse(report["patterns"][0]["complete"])
        self.assertEqual(report["errors"][0]["path"], "nested")
        self.assertIn("injected enumeration denial", report["errors"][0]["message"])

    def test_disappearing_match_is_partial_and_other_patterns_survive(self):
        vanished = self.write("vanished.txt", b"gone")
        self.configure(["vanished.txt", "tracked.txt"])
        original = candidates

        def disappear(source, pattern):
            result = original(source, pattern)
            if pattern == "vanished.txt":
                vanished.unlink()
            return result

        with patch("awkit.review_selection.candidates", disappear):
            code, out, _ = self.cli("--json")
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual([item["path"] for item in report["files"]], ["tracked.txt"])
        self.assertEqual(report["errors"][0]["path"], "vanished.txt")

    def test_linked_branch_is_named_without_enumerating_outside(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "private.txt").write_bytes(b"outside")
        link = self.repo / "redirect"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("native symlink creation unavailable")
        self.configure(["redirect/*.txt", "tracked.txt"], ["redirect/*.txt"])
        original = os.scandir

        def guarded(path):
            if not isinstance(path, int) and Path(path) in (outside, link):
                self.fail("Preview enumerated a linked branch")
            return original(path)

        with patch("awkit.review_selection.os.scandir", guarded):
            report = preview(self.repo, self.config)
        self.assertFalse(report["complete"])
        self.assertEqual([item["path"] for item in report["files"]], ["tracked.txt"])
        self.assertEqual(report["skipped"][0]["path"], "redirect")
        self.assertEqual(report["skipped"][0]["reason"], "linked-branch")
        self.assertEqual((outside / "private.txt").read_bytes(), b"outside")

    def test_shared_reserved_path_collision_does_not_change_copied_selection(self):
        self.write("manifest.json", b"payload")
        self.configure(["manifest.json"])
        self.assertTrue(preview(self.repo, self.config)["complete"])
        self.configure(["manifest.json"], mode="shared")
        report = preview(self.repo, self.config)
        self.assertFalse(report["complete"])
        self.assertEqual(report["errors"][0]["operation"], "selection-collision")

    @unittest.skipUnless(os.name == "nt", "Windows junction containment")
    def test_junction_branch_is_partial_without_following_it(self):
        outside = self.root / "outside"
        outside.mkdir()
        payload = outside / "outside.txt"
        payload.write_bytes(b"external")
        link = self.repo / "redirect"
        created = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        if created.returncode:
            self.skipTest("junction creation unavailable")
        try:
            original = os.scandir

            def guarded(path):
                self.assertNotIn(Path(path), (link, outside), "followed a junction")
                return original(path)

            for mode in ("copy", "shared"):
                self.configure(["redirect/*.txt", "tracked.txt"], mode=mode)
                with patch("awkit.review_selection.os.scandir", guarded):
                    code, out, _ = self.cli("--json")
                report = json.loads(out)
                self.assertEqual(code, 1)
                self.assertEqual([item["path"] for item in report["files"]], ["tracked.txt"])
                self.assertEqual(report["skipped"][0]["path"], "redirect")
                self.assertEqual(report["skipped"][0]["reason"], "linked-branch")
            self.assertEqual(payload.read_bytes(), b"external")
        finally:
            link.rmdir()

    @unittest.skipUnless(os.name == "nt", "Windows directory replacement containment")
    def test_replaced_copy_parent_is_partial_without_outside_metadata_access(self):
        selected = self.write("selected/item.txt", b"inside")
        outside = self.root / "outside-race"
        outside.mkdir()
        (outside / "item.txt").write_bytes(b"outside")
        original_folder = self.repo / "original"
        self.configure(["selected/item.txt"])
        original_info, original_resolve, original_is_file = SafeRoot.info, Path.resolve, Path.is_file
        calls, swapped, unanchored = 0, False, []

        def swap_after_info(source, name):
            nonlocal calls, swapped
            info = original_info(source, name)
            if source.root == self.repo and name == "selected/item.txt":
                calls += 1
                if calls == 2:
                    selected.parent.rename(original_folder)
                    result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(selected.parent), str(outside)],
                                            capture_output=True)
                    if result.returncode:
                        original_folder.rename(selected.parent)
                        self.skipTest("junction creation unavailable")
                    swapped = True
            return info

        def observe_resolve(path, *args, **kwargs):
            if swapped and path == selected:
                unanchored.append("resolve")
            return original_resolve(path, *args, **kwargs)

        def observe_is_file(path, *args, **kwargs):
            if swapped and path == selected:
                unanchored.append("is_file")
            return original_is_file(path, *args, **kwargs)

        try:
            with patch.object(SafeRoot, "info", swap_after_info), patch.object(Path, "resolve", observe_resolve), \
                    patch.object(Path, "is_file", observe_is_file):
                report = preview(self.repo, self.config)
            self.assertTrue(swapped, "fixture must replace the parent after anchored metadata observation")
            self.assertEqual(unanchored, [], "preview re-entered unanchored path traversal after the swap")
            self.assertFalse(report["complete"])
            self.assertEqual(report["files"], [])
            self.assertEqual(report["errors"][0]["path"], "selected/item.txt")
            self.assertEqual((outside / "item.txt").read_bytes(), b"outside")
        finally:
            if swapped:
                selected.parent.rmdir()

    def test_explicit_base_and_config_through_a_link_use_the_canonical_base(self):
        self.configure(["*.txt"])
        configured = self.repo / "preview-config.toml"
        configured.write_bytes(self.config.read_bytes())
        alias = self.root / "old location"
        if os.name == "nt":
            created = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(self.repo)],
                                     capture_output=True)
            if created.returncode:
                self.skipTest("junction creation unavailable")
        else:
            alias.symlink_to(self.repo, target_is_directory=True)
        try:
            report = preview(alias, alias / configured.name)
            self.assertTrue(report["complete"])
            self.assertEqual(report["base"], str(self.repo))
            self.assertEqual(report["config"], str(configured))
            self.assertEqual(report["repository"], str(self.repo))
            for mode in ("copy", "shared"):
                run = self.root / ("alias-run-" + mode)
                run.mkdir()
                if mode == "copy":
                    files, _, _ = collect_artifacts(alias, run, ["*.txt"], [])
                else:
                    collection = self.root / "alias-store"
                    collection.mkdir()
                    files, _, _, _ = collect(alias, run, ["*.txt"], [], ObjectStore(collection, create=True))
                self.assertEqual({item["path"]: item["size"] for item in report["files"]},
                                 {name: entry["size"] for name, entry in files.items()})
        finally:
            alias.rmdir() if os.name == "nt" else alias.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows supplied alias replacement")
    def test_supplied_alias_is_resolved_once_before_repository_identity(self):
        self.configure(["*.txt"])
        alias = self.root / "changing alias"
        outside = self.root / "outside-project"
        outside.mkdir()
        (outside / "outside.txt").write_bytes(b"outside")

        def point_to(target):
            if alias.exists():
                alias.rmdir()
            result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(target)], capture_output=True)
            if result.returncode:
                self.skipTest("junction creation unavailable")

        point_to(self.repo)
        original_resolve, resolutions = Path.resolve, 0

        def retarget_on_third_resolution(path, *args, **kwargs):
            nonlocal resolutions
            if path == alias:
                resolutions += 1
                if resolutions == 3:
                    point_to(outside)
            return original_resolve(path, *args, **kwargs)

        try:
            with patch.object(Path, "resolve", retarget_on_third_resolution):
                report = preview(alias, self.config)
            self.assertEqual(resolutions, 1, "supplied alias must not be resolved again after choosing its base")
            self.assertTrue(report["complete"])
            self.assertEqual((report["base"], report["repository"]), (str(self.repo), str(self.repo)))
            self.assertEqual([item["path"] for item in report["files"]], ["tracked.txt"])
        finally:
            if alias.exists():
                alias.rmdir()

    def test_pattern_scope_avoids_unrelated_directories_and_git(self):
        self.write("selected/item.txt", b"item")
        self.write("unrelated/item.txt", b"unrelated")
        self.configure(["selected/*.txt"])
        forbidden = {((self.repo / name).stat().st_dev, (self.repo / name).stat().st_ino)
                     for name in ("unrelated", ".git")}
        original = os.scandir

        def guarded(path):
            info = os.fstat(path) if isinstance(path, int) else Path(path).stat()
            self.assertNotIn((info.st_dev, info.st_ino), forbidden)
            return original(path)

        with patch("awkit.review_selection.os.scandir", guarded):
            report = preview(self.repo, self.config)
        self.assertTrue(report["complete"])
        self.assertEqual([item["path"] for item in report["files"]], ["selected/item.txt"])

    def test_stat_denial_is_partial_with_its_path_and_other_matches(self):
        from awkit.artifact_store import SafeRoot
        self.write("denied.txt", b"payload")
        self.configure(["denied.txt", "tracked.txt"])
        original = SafeRoot.info
        original_stat = os.stat

        def denied(source, name):
            if name == "denied.txt":
                raise PermissionError("injected metadata denial")
            return original(source, name)

        def denied_stat(path, *args, **kwargs):
            if not isinstance(path, int) and Path(path).name == "denied.txt":
                raise PermissionError("injected metadata denial")
            return original_stat(path, *args, **kwargs)

        with patch.object(SafeRoot, "info", denied), patch("awkit.review_selection.os.stat", denied_stat):
            code, out, _ = self.cli("--json")
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(report["errors"][0]["path"], "denied.txt")
        self.assertEqual(report["errors"][0]["operation"], "stat")
        self.assertEqual([item["path"] for item in report["files"]], ["tracked.txt"])

    @unittest.skipIf(os.name == "nt", "nonportable filename fixture requires POSIX")
    def test_copied_nonportable_file_remains_collectible_but_preview_is_partial(self):
        self.write("unportable:name.txt", b"payload")
        self.configure(["*.txt"])
        run = self.root / "copied"
        run.mkdir()
        retained, _, _ = collect_artifacts(self.repo, run, ["*.txt"], [])
        self.assertIn("unportable:name.txt", retained)
        report = preview(self.repo, self.config)
        self.assertFalse(report["complete"])
        self.assertFalse(report["totals"]["complete"])
        self.assertEqual(report["skipped"], [dict(path="unportable:name.txt", reason="nonportable-path",
                                                 scope="path", pattern="*.txt")])
        self.assertIn("partial totals", text(report))
        self.assertIn("Skipped unportable:name.txt (nonportable-path", text(report))

    def test_text_shows_largest_twenty_and_json_keeps_all_paths(self):
        for index in range(25):
            self.write(f"file-{index:02}.dat", b"x" * index)
        self.configure(["*.dat"])
        report = preview(self.repo, self.config)
        rendered = text(report)
        self.assertIn("showing 20 of 25", rendered)
        self.assertIn("file-24.dat", rendered)
        self.assertNotIn("file-00.dat", rendered)
        self.assertLess(rendered.index("file-24.dat"), rendered.index("file-23.dat"))
        self.assertEqual(len(json.loads(self.cli("--json")[1])["files"]), 25)

    def test_cli_help_and_revision_argument_refusal(self):
        result = subprocess.run([sys.executable, "-m", "awkit", "review", "preview", "--help"],
                                text=True, capture_output=True, env=child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("without running checks", result.stdout)
        self.configure()
        result = subprocess.run([sys.executable, "-m", "awkit", "review", "--repo", str(self.repo),
                                 "preview", "HEAD", "--config", str(self.config)],
                                text=True, capture_output=True, env=child_env())
        self.assertEqual(result.returncode, 2)
