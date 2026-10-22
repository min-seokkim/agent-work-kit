import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from awkit.pipeline import Pipeline, StepError

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "local-release"
A, B, BAD = "a" * 40, "b" * 40, "f" * 40


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project with spaces"
        self.root.mkdir()
        for name in ("pipeline.toml", "adapter.py"):
            shutil.copyfile(EXAMPLE / name, self.root / name)
        self.config = self.root / "pipeline.toml"
        self.pipeline = Pipeline(self.config)

    def fault(self, **kwargs):
        (self.root / "faults.json").write_text(json.dumps(kwargs))

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "awkit", "pipeline", "--config", str(self.config), *args],
            capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )

    def test_one_way_delivery_without_backup_or_rollback(self):
        shutil.copyfile(EXAMPLE / "deliver.toml", self.root / "deliver.toml")
        runner = Pipeline(self.root / "deliver.toml")
        self.assertEqual(runner.run("deploy", A)["status"], "passed")
        # First delivery: no current release to verify, no backup command to run.
        self.assertEqual([e["phase"] for e in runner.last()["events"]], ["preflight", "deploy", "verify"])
        with self.assertRaises(ValueError):
            runner.run("rollback")
        self.fault(fail_after_change=True)
        failed = runner.run("deploy", B, allow_unhealthy_current=True)
        self.assertEqual(failed["status"], "failed-unrecovered")
        self.assertEqual(failed["recovery"], {"skipped": "no-rollback-command"})
        self.fault()
        with self.assertRaises(ValueError):
            runner.run("deploy", A)  # blocked until reconcile
        self.assertEqual(runner.reconcile()["status"], "reconciled")
        text = (self.root / "deliver.toml").read_text(encoding="utf-8") + "\n"
        (self.root / "auto.toml").write_text(text.replace('required_checks = ["service"]',
                                                           'required_checks = ["service"]\nauto_rollback = true'),
                                             encoding="utf-8")
        with self.assertRaises(ValueError):
            Pipeline(self.root / "auto.toml")

    def test_deploy_update_idempotent_and_manual_rollback(self):
        self.assertEqual(self.pipeline.run("deploy", A)["status"], "passed")
        result = self.pipeline.run("deploy", B)
        self.assertEqual((result["status"], result["previous"]), ("passed", A))
        repeat = self.pipeline.run("deploy", B)
        self.assertEqual(repeat["outcome"], "already-current")
        self.assertNotIn("deploy", [event["phase"] for event in repeat["events"]])
        rolled = self.pipeline.run("rollback")
        self.assertEqual((rolled["status"], rolled["release"]), ("passed", A))
        self.assertEqual(self.pipeline.verify()["release"], A)

    def test_failed_health_restores_previous_but_returns_failure(self):
        self.pipeline.run("deploy", A)
        result = self.cli("deploy", BAD, "--json")
        self.assertEqual(result.returncode, 1)
        record = json.loads(result.stdout)
        self.assertEqual(record["status"], "failed-restored")
        self.assertEqual(record["recovery"]["release"], A)
        self.assertEqual(self.pipeline.verify()["release"], A)

    def test_deploy_nonzero_never_uses_old_health_as_success(self):
        self.pipeline.run("deploy", A)
        self.fault(exit_phase="deploy", exit_code=9)
        record = self.pipeline.run("deploy", B)
        self.assertEqual(record["status"], "failed-restored")
        self.assertEqual(record["failure"]["code"], 9)

    def test_zero_exit_but_old_release_is_rejected(self):
        self.pipeline.run("deploy", A)
        self.fault(skip_change=True)
        record = self.pipeline.run("deploy", B)
        self.assertEqual(record["status"], "failed-restored")
        self.assertEqual(record["failure"]["phase"], "verify")

    def test_backup_failure_never_deploys(self):
        self.fault(exit_phase="backup")
        record = self.pipeline.run("deploy", A)
        self.assertEqual(record["status"], "failed")
        self.assertNotIn("deploy", [event["phase"] for event in record["events"]])
        self.assertFalse((self.root / ".demo-target" / "current.json").exists())

    def test_wrong_target_rejected_before_mutation(self):
        self.fault(target="wrong-target")
        record = self.pipeline.run("deploy", A)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(len(record["events"]), 1)

    def test_rollback_failure_blocks_further_mutation(self):
        self.pipeline.run("deploy", A)
        self.fault(exit_phase="rollback")
        self.assertEqual(self.pipeline.run("deploy", BAD)["status"], "rollback-failed")
        with self.assertRaises(ValueError):
            self.pipeline.run("deploy", B)

    def test_first_release_failure_needs_reconciliation(self):
        record = self.pipeline.run("deploy", BAD)
        self.assertEqual(record["status"], "failed-unrecovered")
        with self.assertRaises(ValueError):
            self.pipeline.run("deploy", B)
        # Reconcile records the broken state instead of leaving the target stuck.
        self.assertEqual(self.pipeline.reconcile()["status"], "reconciled-unhealthy")
        self.assertEqual(self.pipeline.history(), [])
        (self.root / ".demo-target" / "current.json").write_text(json.dumps({"release": A}))
        self.assertEqual(self.pipeline.reconcile()["status"], "reconciled")
        self.assertEqual(self.pipeline.run("deploy", B)["status"], "passed")
        self.assertEqual(self.pipeline.history(), [A, B])

    def test_timeout_does_not_launch_automatic_rollback(self):
        self.pipeline.run("deploy", A)
        self.fault(sleep_phase="deploy")
        self.pipeline.timeout = 0.5
        record = self.pipeline.run("deploy", B)
        self.assertEqual(record["status"], "uncertain")
        self.assertNotIn("rollback", [event["phase"] for event in record["events"]])
        with self.assertRaises(ValueError):
            self.pipeline.run("deploy", B)

    def test_second_controller_is_rejected_by_shared_lock(self):
        with self.pipeline.locked():
            result = self.cli("deploy", A)
            self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / ".demo-target").exists())

    def test_status_rejects_malformed_empty_failed_or_duplicate_checks(self):
        self.pipeline.run("deploy", A)
        faults = [
            {"malformed": True}, {"checks": []},
            {"checks": [{"name": "app", "ok": "true"}]},
            {"checks": [{"name": "app", "ok": False}]},
            {"checks": [{"name": "unrelated", "ok": True}]},
            {"checks": [{"name": "app", "ok": True}, {"name": "app", "ok": True}]},
        ]
        for fault in faults:
            self.fault(**fault)
            with self.subTest(fault=fault), self.assertRaises(StepError):
                self.pipeline.verify()

    def test_verifier_exit_code_preserved_for_json_and_human(self):
        self.fault(exit_phase="verify", exit_code=7)
        for flags in ([], ["--json"]):
            result = self.cli("status", *flags)
            self.assertEqual(result.returncode, 7)
            self.assertEqual(result.stdout, "")

    def test_invalid_arguments_do_not_execute_adapters(self):
        for args in [("deploy", "main"), ("deploy",), ("rollback", A), ("status", A)]:
            self.assertEqual(self.cli(*args).returncode, 2)
        self.assertFalse((self.root / ".demo-target").exists())

    def test_plan_is_read_only_and_state_is_project_local(self):
        result = self.cli("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["commands_executed"])
        self.assertFalse(self.pipeline.state.exists())
        self.assertFalse((self.root / ".demo-target").exists())

    def test_two_projects_do_not_share_state(self):
        self.pipeline.run("deploy", A)
        other = self.root.parent / "another-project"
        other.mkdir()
        for name in ("pipeline.toml", "adapter.py"):
            shutil.copyfile(EXAMPLE / name, other / name)
        second = Pipeline(other / "pipeline.toml")
        second.run("deploy", B)
        self.assertEqual(self.pipeline.verify()["release"], A)
        self.assertEqual(second.verify()["release"], B)

    def test_auto_rollback_requires_explicit_opt_in(self):
        self.pipeline.run("deploy", A)
        self.pipeline.auto_rollback = False
        record = self.pipeline.run("deploy", BAD)
        self.assertEqual(record["status"], "failed-unrecovered")
        self.assertNotIn("rollback", [event["phase"] for event in record["events"]])

    def test_commands_are_argument_arrays_and_unknown_placeholders_fail(self):
        original = self.config.read_text(encoding="utf-8")
        for changed in (original.replace('{python}', '{unknown}'),
                        original.replace('required_checks = ["service"]', 'required_checks = []')):
            self.config.write_text(changed, encoding="utf-8")
            with self.assertRaises(ValueError):
                Pipeline(self.config)


class RecoveryTests(unittest.TestCase):
    """Behaviour added in 0.2.0: hotfixes on a broken target, history rollback, process cleanup."""

    setUp = PipelineTests.setUp
    fault = PipelineTests.fault
    cli = PipelineTests.cli

    def test_broken_current_blocks_plain_deploy_but_allows_hotfix(self):
        self.pipeline.run("deploy", A)
        self.fault(unhealthy=[A])
        blocked = self.pipeline.run("deploy", B)
        self.assertEqual((blocked["status"], blocked["failure"]["phase"]), ("failed", "verify-current"))
        self.assertNotIn("deploy", [event["phase"] for event in blocked["events"]])
        result = self.cli("deploy", B, "--allow-unhealthy-current", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual((record["status"], record["outcome"]), ("passed", "deployed"))
        self.assertFalse(record["current_health"]["healthy"])

    def test_failed_hotfix_does_not_roll_back_to_broken_version(self):
        self.pipeline.run("deploy", A)
        self.fault(unhealthy=[A])
        record = self.pipeline.run("deploy", BAD, allow_unhealthy_current=True)
        self.assertEqual(record["status"], "failed-unrecovered")
        self.assertEqual(record["recovery"], {"skipped": "current-unhealthy"})
        self.assertNotIn("rollback", [event["phase"] for event in record["events"]])

    def test_same_release_is_redeployed_when_unhealthy(self):
        self.pipeline.run("deploy", A)
        self.fault(unhealthy=[A])
        record = self.pipeline.run("deploy", A, allow_unhealthy_current=True)
        self.assertEqual(record["outcome"], "redeployed")
        self.assertIn("deploy", [event["phase"] for event in record["events"]])

    def test_rollback_walks_back_through_history(self):
        C = "c" * 40
        for release in (A, B, C):
            self.assertEqual(self.pipeline.run("deploy", release)["status"], "passed")
        self.assertEqual(self.pipeline.run("rollback")["release"], B)
        self.assertEqual(self.pipeline.run("rollback")["release"], A)
        self.assertEqual(self.pipeline.history(), [A])
        last = self.pipeline.run("rollback")
        self.assertEqual((last["status"], last["failure"]["phase"]), ("failed", "preflight"))
        self.assertEqual(self.pipeline.verify()["release"], A)

    def test_rollback_works_when_current_is_broken(self):
        self.pipeline.run("deploy", A)
        self.pipeline.run("deploy", B)
        self.fault(unhealthy=[B])
        record = self.pipeline.run("rollback")
        self.assertEqual((record["status"], record["release"]), ("passed", A))

    def test_history_is_recovered_from_0_1_state(self):
        self.pipeline.run("deploy", A)
        self.pipeline.run("deploy", B)
        (self.pipeline.state / "history.json").unlink()
        self.assertEqual(self.pipeline.history(), [A, B])
        self.assertEqual(self.pipeline.run("rollback")["release"], A)

    def test_timeout_stops_children_started_by_the_adapter(self):
        marker = Path(self.temp.name) / "orphan-alive.txt"
        self.pipeline.run("deploy", A)
        self.fault(orphan_phase="deploy", orphan_marker=str(marker))
        self.pipeline.timeout = 1
        started = time.monotonic()
        record = self.pipeline.run("deploy", B)
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(record["status"], "uncertain")
        time.sleep(4)
        self.assertFalse(marker.exists(), "adapter child survived the timeout")

    def test_command_output_is_kept_with_the_run(self):
        record = self.pipeline.run("deploy", A)
        run_dir = self.pipeline.state / "runs" / record["run_id"]
        verify = [event for event in record["events"] if event["phase"] == "verify"][-1]
        report = json.loads((run_dir / verify["stdout"]).read_text(encoding="utf-8"))
        self.assertEqual(report["release"], A)

    def test_status_and_history_cli(self):
        self.pipeline.run("deploy", A)
        self.pipeline.run("deploy", B)
        history = self.cli("history")
        self.assertEqual(history.returncode, 0, history.stderr)
        self.assertEqual(history.stdout.split()[0], B)
        self.fault(unhealthy=[B])
        status = self.cli("status")
        self.assertEqual(status.returncode, 1)
        self.assertIn("service: failed", status.stdout)
        self.assertEqual(self.cli("rollback", "--allow-unhealthy-current").returncode, 2)


if __name__ == "__main__":
    unittest.main()
