"""Real-Git protection, writer admission and exclusion ownership boundaries."""

import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from awkit import checks, connect, hooks, kit_hooks, local_state, review
from awkit.channel import Channel
from awkit.channel_status import _read_channel
from awkit.extras.pipeline import Pipeline
from awkit.session_history import HistoryViews
from awkit.session_store import SessionStore
from awkit.sessions import SessionController
from support import child_env

ROOT = Path(__file__).resolve().parents[1]


class LocalStateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.git(self.project, "init", "-q")
        self.git(self.project, "config", "user.name", "owner")
        self.git(self.project, "config", "user.email", "owner@example.com")
        self.git(self.project, "config", "core.autocrlf", "false")
        (self.project / "input.txt").write_text("input\n", encoding="utf-8")
        self.git(self.project, "add", "input.txt")
        self.git(self.project, "commit", "-qm", "Initial")

    @staticmethod
    def git(project, *args):
        result = subprocess.run(["git", "-C", str(project), *args], capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def ignored(self, project=None, relative=".awkit/payload"):
        self.assertTrue(local_state._ignored(project or self.project, relative))

    def channel(self, project=None):
        project = project or self.project
        channel = Channel(project / ".awkit/channel.sqlite3", project=project)
        channel.post("main", "reviewer", "notice", "fictional")
        return channel

    def test_direct_channel_repairs_existing_directory_and_preserves_bytes(self):
        exclude = local_state.exclude_file(self.project)
        original = b"# own\xff\r\n*.private"  # CRLF and no final newline
        exclude.write_bytes(original)
        (self.project / ".awkit").mkdir()
        self.channel()
        self.ignored()
        after = exclude.read_bytes()
        self.assertEqual(after, original + b"\r\n/.awkit/\r\n")
        self.channel()
        self.assertEqual(exclude.read_bytes(), after)
        self.assertFalse((self.project / ".gitignore").exists())

    def test_existing_shared_and_global_protection_needs_no_metadata_write(self):
        for shared in (True, False):
            with self.subTest(shared=shared):
                path = self.project / (".gitignore" if shared else "global.ignore")
                path.write_bytes(b"/.awkit/\r\n")
                if not shared:
                    self.git(self.project, "config", "core.excludesFile", str(path))
                before = local_state.exclude_file(self.project).read_bytes()
                with mock.patch.object(local_state, "_locked", side_effect=AssertionError("must not mutate")):
                    self.channel()
                self.assertEqual(local_state.exclude_file(self.project).read_bytes(), before)
                self.assertEqual(path.read_bytes(), b"/.awkit/\r\n")
                path.unlink()

    def test_nested_project_pattern_is_anchored_and_does_not_hide_other_state(self):
        project = self.project / "sub [project]"
        project.mkdir()
        self.channel(project)
        self.ignored(relative="sub [project]/.awkit/channel.sqlite3")
        self.assertFalse(local_state._ignored(self.project, ".awkit/payload"))
        self.assertFalse(local_state._ignored(self.project, "other/.awkit/payload"))

    def test_worktree_and_submodule_use_git_resolved_administration(self):
        worktree = self.base / "worktree"
        self.git(self.project, "worktree", "add", "-qb", "fixture", str(worktree))
        try:
            self.channel(worktree)
            self.ignored(worktree)
            self.assertTrue((worktree / ".git").is_file())
        finally:
            self.git(self.project, "worktree", "remove", "--force", str(worktree))
        source = self.base / "submodule-source"
        self.git(self.base, "clone", "-q", str(self.project), str(source))
        self.git(self.project, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(source), "child")
        child = self.project / "child"
        before = (child / ".git").read_bytes()
        self.channel(child)
        self.ignored(child)
        self.assertEqual((child / ".git").read_bytes(), before)

    def test_outside_git_and_external_outputs_are_not_given_git_metadata(self):
        project = self.base / "plain"
        project.mkdir()
        self.channel(project)
        self.assertFalse((project / ".git").exists())
        self.assertEqual(local_state.prepare(project), "outside-git")
        before = local_state.exclude_file(self.project).read_bytes()
        external = self.base / "arbitrary/.awkit/output.sqlite3"
        Channel(external, project=self.project).post("main", "reviewer", "notice", "external")
        self.assertEqual(local_state.exclude_file(self.project).read_bytes(), before)
        self.assertFalse((self.project / ".awkit").exists())

    def test_tracked_payload_and_index_remain_unchanged(self):
        folder = self.project / ".awkit"
        folder.mkdir()
        tracked = folder / "tracked.txt"
        tracked.write_bytes(b"keep\x00exact")
        self.git(self.project, "add", ".awkit/tracked.txt")
        self.git(self.project, "commit", "-qm", "Tracked fixture")
        index = self.git(self.project, "ls-files", "--stage")
        self.channel()
        self.assertEqual(self.git(self.project, "ls-files", "--stage"), index)
        self.assertEqual(tracked.read_bytes(), b"keep\x00exact")

    def test_tracked_write_target_fails_without_changing_payload_or_index(self):
        channel = self.channel()
        self.git(self.project, "add", "-f", ".awkit/channel.sqlite3")
        before = channel.path.read_bytes()
        index = self.git(self.project, "ls-files", "--stage")
        with self.assertRaisesRegex(local_state.ExclusionError, "already tracked"):
            channel.post("main", "reviewer", "notice", "must not write")
        self.assertEqual(channel.path.read_bytes(), before)
        self.assertEqual(self.git(self.project, "ls-files", "--stage"), index)

    def test_effective_negation_blocks_before_payload_sqlite_or_provider_construction(self):
        (self.project / ".gitignore").write_text("!/.awkit/\n!/.awkit/**\n", encoding="utf-8")
        provider = mock.Mock(side_effect=AssertionError("native construction forbidden"))
        for action in (self.channel,
                       lambda: SessionController(self.project, ["fictional"], provider_factory=provider,
                                                 claude_factory=provider),
                       lambda: SessionStore.create(self.project / ".awkit/sessions/channels", name="fixture",
                                                   project=self.project, responsibility="fictional", generation="fixture",
                                                   permissions={}, provider="claude")):
            with self.subTest(action=action), self.assertRaisesRegex(local_state.ExclusionError, "negation"):
                action()
            self.assertFalse((self.project / ".awkit").exists())
        provider.assert_not_called()

    def test_ignored_probe_and_file_do_not_establish_directory_protection(self):
        (self.project / ".gitignore").write_text("!/.awkit/\n/.awkit/awkit-exclusion-probe\n/.awkit/channel.sqlite3\n", encoding="utf-8")
        with self.assertRaisesRegex(local_state.ExclusionError, "negation"):
            self.channel()
        self.assertFalse((self.project / ".awkit").exists())

    def test_administrative_and_coordination_failures_are_not_outside_git(self):
        original = local_state._git

        def broken(project, *args):
            if args[:2] == ("rev-parse", "--git-path"):
                return subprocess.CompletedProcess([], 128, "", "administration unavailable")
            return original(project, *args)

        with mock.patch.object(local_state, "_git", side_effect=broken):
            with self.assertRaisesRegex(local_state.ExclusionError, "resolve Git info/exclude"):
                self.channel()
        exclude = local_state.exclude_file(self.project)
        lock = exclude.with_name(exclude.name + ".awkit-lock")
        lock.write_bytes(b"other owner")
        with mock.patch.object(local_state, "LOCK_SECONDS", 0.03):
            with self.assertRaisesRegex(local_state.ExclusionError, "busy"):
                self.channel()
        self.assertEqual(lock.read_bytes(), b"other owner")
        self.assertFalse((self.project / ".awkit").exists())
        lock.unlink()
        with mock.patch.object(local_state.os, "open", side_effect=PermissionError("read-only administration")):
            with self.assertRaisesRegex(local_state.ExclusionError, "coordinate"):
                self.channel()
        self.assertFalse((self.project / ".awkit").exists())

    def test_git_inspection_failure_in_known_repository_is_actionable(self):
        with mock.patch.object(local_state, "_git", return_value=subprocess.CompletedProcess([], 128, "", "inspection failed")):
            with self.assertRaisesRegex(local_state.ExclusionError, "resolve Git repository"):
                self.channel()

    def test_concurrent_process_writers_preserve_rules_and_one_managed_addition(self):
        code = ("from awkit.local_state import prepare,add_rule; from pathlib import Path; import sys; "
                "p=Path(sys.argv[1]); prepare(p); add_rule(p,sys.argv[2],directory=True)")
        commands = [[sys.executable, "-c", code, str(self.project), f"private-{index}"] for index in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda argv: subprocess.run(argv, capture_output=True, text=True, env=child_env()), commands))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        data = local_state.exclude_file(self.project).read_bytes()
        self.assertEqual(data.count(b"/.awkit/\n"), 1)
        for index in range(6):
            self.assertIn(f"/private-{index}/\n".encode(), data)
        self.assertFalse(local_state.exclude_file(self.project).with_name("exclude.awkit-lock").exists())

    def test_restore_coordinates_with_add_and_preserves_intervening_external_append(self):
        exclude = local_state.exclude_file(self.project)
        before = exclude.read_bytes()
        entry = kit_hooks.exclude_local(self.project, ".awkit/", Path(".awkit/backup/exclude"))
        with exclude.open("ab") as stream:
            stream.write(b"# external\n/unrelated/\n")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(kit_hooks.restore_exclude, self.project, entry),
                       pool.submit(local_state.add_rule, self.project, "concurrent", directory=True)]
            for future in futures:
                future.result()
        data = exclude.read_bytes()
        self.assertEqual(data, before + b"# external\n/unrelated/\n/concurrent/\n")

    def test_append_does_not_capture_or_lose_a_noncooperating_edit(self):
        exclude = local_state.exclude_file(self.project)
        before = exclude.read_bytes()
        original_open = Path.open

        def intervening(path, mode="r", *args, **kwargs):
            if path == exclude and mode == "ab":
                with original_open(path, "ab") as stream:
                    stream.write(b"# intervening editor\n")
            return original_open(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", intervening):
            entry = kit_hooks.exclude_local(self.project, ".awkit/", Path(".awkit/backup/exclude"))
        self.assertNotEqual(local_state._sha(exclude.read_bytes()), entry["after"])
        kit_hooks.restore_exclude(self.project, entry)
        self.assertEqual(exclude.read_bytes(), before + b"# intervening editor\n")

    def test_other_explicit_writers_fail_before_managed_payload(self):
        pipeline = self.pipeline()
        config = self.project / "checks.toml"
        config.write_text('schema=1\n[[checks]]\nname="fictional"\nargv=["echo","unused"]\n', encoding="utf-8")
        history = self.project / "history.sqlite3"
        Channel(history, project=self.project).post("main", "reviewer", "notice", "fictional")
        (self.project / ".gitignore").write_text("!/.awkit/\n!/.awkit/**\n", encoding="utf-8")
        for action in (lambda: review.check(self.project, "HEAD", config, runs_root=self.project / ".awkit/explicit"),
                       lambda: checks.done(self.project, session="blocked", mark=True),
                       lambda: HistoryViews(self.project, self.project / ".awkit/views").register(history, "M", "R")):
            with self.subTest(action=action), self.assertRaises(local_state.ExclusionError):
                action()
            self.assertFalse((self.project / ".awkit").exists())
        with self.assertRaises(local_state.ExclusionError):
            with pipeline.locked():
                self.fail("must not reach the action")
        self.assertFalse((self.project / ".awkit").exists())

    def test_shared_controller_and_history_registration_are_protected(self):
        controller = SessionController(self.project, ["fictional"])
        controller.close()
        self.ignored()
        # Registering a legacy channel protects its separate selected view directory.
        other = self.project / "views-project"
        other.mkdir()
        channel = Channel(other / "history.sqlite3", project=other)
        channel.post("main", "reviewer", "notice", "retained")
        HistoryViews(other, other / ".awkit/views").register("history.sqlite3", "Main", "Reviewer")
        self.ignored(relative="views-project/.awkit/views/views.json")

    def test_review_explicit_root_accept_and_mark_protect_before_state(self):
        config = self.project / "checks.toml"
        config.write_text('schema=1\n[[checks]]\nname="fixture"\nargv=["' + sys.executable.replace("\\", "/") +
                          '","-c","print(1)"]\n', encoding="utf-8")
        explicit = self.project / ".awkit/explicit"
        result = review.check(self.project, "HEAD", config, runs_root=explicit)
        run = Path(result["run_dir"])
        self.assertEqual(result["status"], "passed")
        self.ignored(relative=".awkit/explicit")
        checks.done(self.project, session="fixture", mark=True)
        self.ignored(relative=".awkit/done")
        # Acceptance must prepare protection before creating its lock or payload.
        retained = self.base / "retained-run"
        shutil.copytree(run, retained)
        run = retained
        shutil.rmtree(self.project / ".awkit")
        exclude = local_state.exclude_file(self.project)
        exclude.write_bytes(exclude.read_bytes().replace(b"/.awkit/\n", b""))
        with mock.patch.object(review, "verify", return_value={"artifacts": True, "verified": True}):
            artifact = Path(run) / "artifacts"
            artifact.mkdir(parents=True, exist_ok=True)
            (artifact / "manifest.json").write_text(json.dumps({"files": []}), encoding="utf-8")
            review.accept(self.project, run)
        self.ignored(relative=".awkit/accepted")

    def test_read_only_paths_leave_a_fresh_project_unchanged(self):
        before = local_state.exclude_file(self.project).read_bytes()
        with self.assertRaises(sqlite3.OperationalError):
            _read_channel(self.project / ".awkit/channel.sqlite3")
        hooks.report(self.project)
        checks.done(self.project)
        HistoryViews(self.project, self.project / ".awkit/views").snapshots()
        pipeline = self.pipeline()
        pipeline.history()
        self.assertFalse((self.project / ".awkit").exists())
        self.assertEqual(local_state.exclude_file(self.project).read_bytes(), before)

    def test_existing_session_status_does_not_repair_exclusion_or_change_channel(self):
        controller = SessionController(self.project, ["fictional"])
        try:
            store = SessionStore.create(controller.directory / "channels", name="fictional", project=self.project,
                                        responsibility="fixture", generation=controller.generation, permissions={})
            controller._stores[store.metadata()["id"]] = store
            exclude = local_state.exclude_file(self.project)
            unprotected = exclude.read_bytes().replace(b"/.awkit/\n", b"")
            exclude.write_bytes(unprotected)
            before = store.path.read_bytes()
            # A new store's Channel has not yet cached its existing schema.
            controller._stores[store.metadata()["id"]] = SessionStore(store.path)
            report = controller.status()
            self.assertEqual(len(report["sessions"]), 1)
            self.assertEqual(store.path.read_bytes(), before)
            self.assertEqual(exclude.read_bytes(), unprotected)
        finally:
            controller.close()

    def pipeline(self):
        for name in ("pipeline.toml", "adapter.py"):
            shutil.copyfile(ROOT / "examples/local-release" / name, self.project / name)
        return Pipeline(self.project / "pipeline.toml")

    def test_pipeline_default_state_prepares_but_external_state_does_not(self):
        pipeline = self.pipeline()
        with pipeline.locked():
            self.ignored(relative=".awkit/releases/lock.sqlite3")
        exclude = local_state.exclude_file(self.project)
        before = exclude.read_bytes()
        pipeline.state = self.base / "external-state"
        with pipeline.locked():
            pass
        self.assertEqual(exclude.read_bytes(), before)

    def test_hook_failure_preserves_block_response_and_skips_all_persistence(self):
        (self.project / ".awkit").mkdir()
        shutil.copyfile(ROOT / "kit/rules.toml", self.project / "rules.toml")
        payload = dict(hook_event_name="PreToolUse", session_id="fixture", cwd=str(self.project),
                       tool_name="Bash", tool_input={"command": "git commit --author='Other <other@example.com>' -m test"})
        error = io.StringIO()
        with mock.patch.dict(os.environ, child_env()), redirect_stderr(error), \
                mock.patch.object(local_state, "prepare", side_effect=local_state.ExclusionError("fictional failure")):
            response = json.loads(hooks.run(json.dumps(payload)))
            hooks._save_state(self.project, "direct", {"logged": []})
            (self.project / "rules.toml").unlink()
            self.assertEqual(hooks.run(json.dumps(payload)), "")
        self.assertEqual(response["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("local state not saved", error.getvalue())
        self.assertEqual(list((self.project / ".awkit").iterdir()), [])

    def test_hook_log_repairs_existing_directory_and_read_only_report_does_not(self):
        (self.project / ".awkit").mkdir()
        before = local_state.exclude_file(self.project).read_bytes()
        hooks.report(self.project)
        self.assertEqual(local_state.exclude_file(self.project).read_bytes(), before)
        hooks.log(self.project, {"decision": "allow", "session": "fictional"})
        self.ignored(relative=".awkit/hooks.ndjson")
        self.assertEqual(json.loads((self.project / ".awkit/hooks.ndjson").read_text())["decision"], "allow")

    def test_default_review_protects_but_external_runs_root_is_unchanged(self):
        config = self.project / "checks.toml"
        config.write_text('schema=1\n[[checks]]\nname="fictional"\nargv=["' +
                          sys.executable.replace("\\", "/") + '","-c","print(1)"]\n', encoding="utf-8")
        before = local_state.exclude_file(self.project).read_bytes()
        external = self.base / "external-runs"
        result = review.check(self.project, "HEAD", config, runs_root=external)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(local_state.exclude_file(self.project).read_bytes(), before)
        result = review.check(self.project, "HEAD", config)
        self.assertEqual(result["status"], "passed")
        self.ignored(relative=".awkit/reviews")

    def test_no_git_install_then_runtime_and_retained_removal_keep_protection(self):
        before = local_state.exclude_file(self.project).read_bytes()
        connect.init(self.project, git=False, hooks=False)
        self.assertEqual(local_state.exclude_file(self.project).read_bytes(), before)
        self.channel()
        connect.remove(self.project, hooks=False, keep_records=True)
        self.ignored()
        self.assertTrue((self.project / ".awkit/channel.sqlite3").exists())

    def test_runtime_first_install_cannot_claim_or_remove_runtime_rule(self):
        self.channel()
        connect.init(self.project, hooks=False)
        record = json.loads((self.project / ".awkit/installed.json").read_text(encoding="utf-8"))
        self.assertNotIn("excluded", record)
        connect.remove(self.project, hooks=False, keep_records=True)
        self.ignored()
