"""Local selector ownership is independent of handler ownership and shared commands."""

import hashlib
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from awkit import commit_paths, hooks, kit_hooks
from awkit.review import git


class LocalPathSettings(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        git(self.root, "init", "-q")
        git(self.root, "config", "core.autocrlf", "false")
        self.path = self.root / ".claude/settings.local.json"
        self.path.parent.mkdir()
        self.mutable_before = []

    def preflight(self, root=None, *, git_root=True):
        root = (root or self.root).resolve()
        self.assertEqual(kit_hooks._top(root), (root, git_root))
        if not git_root:
            for parent in (root, *root.parents):
                self.assertFalse((parent / ".git").exists(), str(parent))
                probe = subprocess.run(["git", "-C", str(parent), "rev-parse", "--is-inside-work-tree"],
                                       capture_output=True, text=True, encoding="utf-8", errors="replace")
                self.assertTrue((probe.returncode == 128 and "not a git repository" in probe.stderr.lower())
                                or (probe.returncode == 0 and probe.stdout.strip() == "false"),
                                f"Unverified non-Git ancestor {parent}: {probe.stderr}")
        paths = ["rules.toml", ".claude/settings.local.json", ".claude/settings.json", ".codex/hooks.json",
                 ".awkit/kit-hooks.json", ".git/info/exclude", ".git/hooks/commit-msg"]
        backup = root / ".awkit/kit-hooks"
        if backup.is_dir():
            paths.extend(path.relative_to(root).as_posix() for path in backup.rglob("*") if path.is_file())
        before = {}
        for name in paths:
            path = root / name
            self.assertTrue(path.resolve().is_relative_to(root), name)
            raw = path.read_bytes() if path.is_file() else None
            before[name] = {"bytes": raw, "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None}
        self.mutable_before.append({"root": root, "git_root": git_root, "files": before})
        return root

    def install(self):
        return kit_hooks.install(self.preflight(), use_git=False, use_codex=False)

    def remove(self):
        return kit_hooks.remove(self.preflight())

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def entry(self):
        return json.loads((self.root / kit_hooks.RECORD).read_text(encoding="utf-8"))["files"].get(
            ".claude/settings.local.json", {})

    def test_fixed_local_value_one_handler_and_repeat_preserves_ownership(self):
        shared = self.path.with_name("settings.json")
        shared.write_text(json.dumps({"hooks": {event: [{"hooks": [{"type": "command", "command": hooks.hook_command()}]}]
                                                for event in kit_hooks.EVENTS}}), encoding="utf-8")
        before = shared.read_bytes()
        self.install()
        self.assertEqual(shared.read_bytes(), before)
        self.assertEqual(self.read()["env"], {commit_paths.ENV_KEY: "git-bash"})
        self.assertEqual(self.read()["hooks"], {})
        self.assertEqual(self.entry()["owned_env"], {commit_paths.ENV_KEY: "git-bash"})
        once = self.path.read_bytes()
        self.install()
        self.assertEqual(self.path.read_bytes(), once)
        self.remove()
        self.assertFalse(self.path.exists())
        self.assertEqual(shared.read_bytes(), before)

    def test_unchanged_file_restores_exact_bytes_and_existing_environment(self):
        original = b'{\r\n\t"env": {"MINE": "keep"},\r\n\t"model": "mine"\r\n}'
        self.path.write_bytes(original)
        self.install()
        self.assertEqual(self.read()["env"]["MINE"], "keep")
        self.remove()
        self.assertEqual(self.path.read_bytes(), original)

    def test_existing_settings_and_missing_record_preserve_an_orphan_backup(self):
        original = b'{\r\n  "model": "original"\r\n}'
        self.path.write_bytes(original)
        orphan = self.root / kit_hooks.BACKUP / ".claude/settings.local.json"
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(b"earlier orphan contents")
        self.assertFalse((self.root / kit_hooks.RECORD).exists())
        self.install()
        fresh = self.root / self.entry()["backup"]
        self.assertNotEqual(fresh, orphan)
        self.assertEqual(fresh.read_bytes(), original)
        self.assertEqual(orphan.read_bytes(), b"earlier orphan contents")
        self.remove()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(orphan.read_bytes(), b"earlier orphan contents")
        self.assertFalse(fresh.exists())

    def test_existing_selector_values_are_never_overwritten_or_claimed(self):
        for value in ("git-bash", "other", "", None, 7, {"custom": True}):
            with self.subTest(value=value):
                self.write({"env": {commit_paths.ENV_KEY: value, "MINE": "keep"}})
                self.install()
                self.assertEqual(self.read()["env"][commit_paths.ENV_KEY], value)
                self.assertNotIn("owned_env", self.entry())
                data = self.read()
                data["later"] = True
                self.write(data)
                self.remove()
                self.assertEqual(self.read()["env"], {commit_paths.ENV_KEY: value, "MINE": "keep"})

    def test_edited_file_removes_only_matching_owned_value_and_preserves_user_hooks(self):
        shared_hook = {"hooks": [{"type": "command", "command": "echo user"}]}
        self.write({"hooks": {"Stop": [shared_hook]}})
        self.install()
        data = self.read()
        data["env"]["MINE"] = "keep"
        data["model"] = "later"
        self.write(data)
        self.remove()
        self.assertEqual(self.read(), {"hooks": {"Stop": [shared_hook]}, "env": {"MINE": "keep"}, "model": "later"})

    def test_changed_owned_value_survives_and_env_only_file_is_supported(self):
        for value in ("custom", "git-bash"):
            with self.subTest(value=value):
                self.path.unlink(missing_ok=True)
                self.install()
                self.write({"env": {commit_paths.ENV_KEY: value, "MINE": "keep"}, "later": True})
                self.remove()
                expected = {"MINE": "keep"}
                if value != "git-bash":
                    expected[commit_paths.ENV_KEY] = value
                self.assertEqual(self.read(), {"env": expected, "later": True})

    def test_missing_record_and_old_remover_preserve_environment_in_edited_files(self):
        self.install()
        self.write({**self.read(), "later": True})
        # An older remover calls _strip_settings(path) without optional ownership metadata.
        self.preflight()
        kit_hooks._strip_settings(self.path)
        self.assertEqual(self.read()["env"][commit_paths.ENV_KEY], "git-bash")
        (self.root / kit_hooks.RECORD).unlink()
        self.remove()
        self.assertEqual(self.read()["env"][commit_paths.ENV_KEY], "git-bash")

    def test_staged_tracked_and_staged_deletion_local_settings_are_refused(self):
        self.write({"model": "tracked", "hooks": {
            event: [{"hooks": [{"type": "command", "command": kit_hooks.handler_command(event)}]}]
            for event in kit_hooks.EVENTS}})
        git(self.root, "add", ".claude/settings.local.json")
        for stage in ("staged", "tracked", "staged deletion"):
            with self.subTest(stage=stage):
                if stage == "tracked":
                    git(self.root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                        "commit", "-q", "-m", "Fixture")
                elif stage == "staged deletion":
                    git(self.root, "rm", "--cached", ".claude/settings.local.json")
                before, index = self.path.read_bytes(), git(self.root, "ls-files", "--stage")
                result = self.install()
                self.assertTrue(any("tracked or staged" in note for note in result["notes"]))
                self.assertEqual(self.path.read_bytes(), before)
                self.assertEqual(git(self.root, "ls-files", "--stage"), index)
                self.assertNotIn("owned_env", self.entry())

    def test_invalid_environment_container_is_preserved(self):
        for value in (None, [], "custom"):
            with self.subTest(value=value):
                self.write({"env": value})
                self.assertTrue(any("env" in note for note in self.install()["notes"]))
                self.assertEqual(self.read()["env"], value)
                self.assertEqual(set(self.read()["hooks"]), set(kit_hooks.EVENTS))
                self.assertNotIn("owned_env", self.entry())

    def test_git_inventory_error_refuses_local_write(self):
        self.write({"model": "keep"})
        from awkit.review import _probe

        def probe(top, *args):
            if args[0] == "ls-files":
                return SimpleNamespace(returncode=128, stdout="", stderr="inventory unavailable")
            return _probe(top, *args)

        notes = []
        with mock.patch("awkit.review._probe", side_effect=probe):
            kit_hooks.install_settings(self.preflight(), "claude", kit_hooks.Record(self.root), notes=notes)
        self.assertTrue(any("could not establish" in note and "was not inserted" in note for note in notes))
        self.assertNotIn("env", self.read())
        self.assertEqual(self.read()["model"], "keep")
        self.assertEqual(set(self.read()["hooks"]), set(kit_hooks.EVENTS))

    def test_staged_settings_still_receive_existing_handlers_without_the_selector(self):
        self.write({"model": "tracked"})
        git(self.root, "add", ".claude/settings.local.json")
        index = git(self.root, "ls-files", "--stage")
        result = self.install()
        self.assertTrue(any("tracked or staged" in note and "was not inserted" in note for note in result["notes"]))
        self.assertNotIn("env", self.read())
        self.assertEqual(set(self.read()["hooks"]), set(kit_hooks.EVENTS))
        self.assertEqual(git(self.root, "ls-files", "--stage"), index)

    def test_known_non_git_folder_gets_the_fixed_selector(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result = kit_hooks.install(self.preflight(root, git_root=False), use_git=False, use_codex=False)
            local = json.loads((root / ".claude/settings.local.json").read_text(encoding="utf-8"))
            self.assertEqual(local["env"], {commit_paths.ENV_KEY: "git-bash"})
            self.assertFalse(any("not inserted" in note for note in result["notes"]))

    def test_remove_preserves_unknown_and_changed_backups_and_keeps_their_exclusion(self):
        self.write({"model": "original"})
        self.install()
        record = json.loads((self.root / kit_hooks.RECORD).read_text(encoding="utf-8"))
        original_copy = self.root / record["files"][".claude/settings.local.json"]["backup"]
        original_copy.write_bytes(b"changed copy must survive")
        orphan = self.root / kit_hooks.BACKUP / "unrecorded"
        orphan.write_bytes(b"orphan must survive")
        self.remove()
        self.assertEqual(original_copy.read_bytes(), b"changed copy must survive")
        self.assertEqual(orphan.read_bytes(), b"orphan must survive")
        self.assertFalse((self.root / kit_hooks.RECORD).exists())
        self.assertEqual(git(self.root, "check-ignore", "--", orphan.relative_to(self.root).as_posix()),
                         orphan.relative_to(self.root).as_posix())

    def test_remove_does_not_delete_a_recorded_backup_outside_managed_backup_folder(self):
        self.write({"model": "original"})
        self.install()
        record_path = self.root / kit_hooks.RECORD
        record = json.loads(record_path.read_text(encoding="utf-8"))
        entry = record["files"][".claude/settings.local.json"]
        outside = self.root / "outside-backup"
        outside.write_bytes((self.root / entry["backup"]).read_bytes())
        entry["backup"] = outside.relative_to(self.root).as_posix()
        record_path.write_text(json.dumps(record), encoding="utf-8")
        before = outside.read_bytes()
        self.remove()
        self.assertEqual(outside.read_bytes(), before)

    def redirected_backup_fixture(self, kind, location):
        self.write({"model": "original"})
        self.install()
        managed = self.root / kit_hooks.BACKUP
        record_path = self.root / kit_hooks.RECORD
        record = json.loads(record_path.read_text(encoding="utf-8"))
        entry = record["files"][".claude/settings.local.json"]
        original = (self.root / entry["backup"]).read_bytes()
        target = (managed if location == "inside" else self.root) / "unknown-target"
        if location == "managed":
            managed.rename(target)
            redirect = managed
        else:
            target.mkdir()
            redirect = managed / "unknown-redirect"
        child = target / "unknown-empty-child"
        child.mkdir()
        if location == "inside":
            # Ordinary empty directories inside BACKUP may be pruned through their real path.
            # Unknown content must survive, including when a recorded path aliases it.
            (child / "unknown-content").write_bytes(b"keep inside target content")
        sentinel = target / "sentinel"
        sentinel.write_bytes(b"unknown target bytes must survive")
        copied = target / "original"
        copied.write_bytes(original)
        self.assertTrue(target.resolve().is_relative_to(self.root))
        self.assertEqual(target.resolve(), target)
        self.assertFalse(redirect.exists())
        if kind == "junction":
            created = subprocess.run(["cmd", "/c", "mklink", "/J", str(redirect), str(target)],
                                     capture_output=True, text=True)
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.assertTrue(redirect.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
            self.addCleanup(redirect.rmdir)
        else:
            try:
                redirect.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Directory symlink unavailable: {exc}")
            self.addCleanup(redirect.unlink)
        self.assertEqual(redirect.resolve(), target)
        if location == "inside":
            entry["backup"] = (redirect / "original").relative_to(self.root).as_posix()
            record_path.write_text(json.dumps(record), encoding="utf-8")
        before = {path.relative_to(target).as_posix(): path.read_bytes() if path.is_file() else None
                  for path in target.rglob("*")}
        before_hashes = {name: hashlib.sha256(raw).hexdigest() if raw is not None else None
                         for name, raw in before.items()}
        self.assertIsNone(kit_hooks._matching_backup(self.root, {
            "backup": (redirect / "original").relative_to(self.root).as_posix(), "before": kit_hooks._sha(original)}))
        self.remove()
        self.assertEqual(redirect.resolve(), target)
        self.assertTrue(redirect.is_dir())
        after = {path.relative_to(target).as_posix(): path.read_bytes() if path.is_file() else None
                 for path in target.rglob("*")}
        self.assertEqual(after, before)
        self.assertEqual({name: hashlib.sha256(raw).hexdigest() if raw is not None else None
                          for name, raw in after.items()}, before_hashes)
        self.assertFalse(record_path.exists())
        self.assertEqual(git(self.root, "check-ignore", "--", redirect.relative_to(self.root).as_posix()),
                         redirect.relative_to(self.root).as_posix())

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_remove_preserves_unknown_junction_and_outside_target(self):
        self.redirected_backup_fixture("junction", "outside")

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_remove_preserves_recorded_backup_through_inside_junction(self):
        self.redirected_backup_fixture("junction", "inside")

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_remove_preserves_redirected_managed_backup_directory(self):
        self.redirected_backup_fixture("junction", "managed")

    def test_remove_preserves_unknown_symlink_and_target(self):
        self.redirected_backup_fixture("symlink", "outside")

    def test_shared_generator_and_codex_have_no_selector(self):
        hooks.install_settings(self.preflight(), "claude")
        shared = json.loads(self.path.with_name("settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("env", shared)
        kit_hooks.install(self.preflight(), use_git=False, use_claude=False)
        codex = json.loads((self.root / ".codex/hooks.json").read_text(encoding="utf-8"))
        self.assertNotIn("env", codex)
