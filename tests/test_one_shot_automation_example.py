import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/one-shot-automation"
RUN = load("one_shot_run", EXAMPLE / "run_once.py")
CHECK = load("one_shot_check", EXAMPLE / "check_output.py")


class OneShotExampleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "example"
        shutil.copytree(EXAMPLE, self.root, ignore=shutil.ignore_patterns("output", "__pycache__"))

    def invoke(self, action, case):
        return RUN.main([action, case], root=self.root)

    def job(self, case):
        return self.root / "output" / case

    def finish(self, case):
        self.assertEqual(self.invoke("prepare", case), 0)
        if case in {"fired", "failed"}:
            self.assertEqual(self.invoke("stage-event", case), 0)
        if case != "configured":
            self.assertEqual(self.invoke("observe", case), 1 if case == "failed" else 0)
        if case in {"fired", "failed"}:
            self.assertEqual(self.invoke("observe", case), 0)

    def test_configured_does_not_observe_and_missing_signal_does_not_act(self):
        for case in ("configured", "no-trigger"):
            with self.subTest(case=case):
                self.finish(case)
                self.assertEqual(CHECK.check(self.root, case)["attempts"], 0)
                self.assertFalse((self.job(case) / "delivery/effect.txt").exists())
                self.assertEqual((self.job(case) / "observations.jsonl").exists(), case == "no-trigger")

    def test_one_append_survives_second_observation_with_signal_still_present(self):
        self.assertEqual(self.invoke("prepare", "fired"), 0)
        self.assertEqual(self.invoke("stage-event", "fired"), 0)
        self.assertEqual(self.invoke("observe", "fired"), 0)
        effect = self.job("fired") / "delivery/effect.txt"
        first = effect.read_bytes()
        self.assertEqual(first, b"mock effect DEMO-ONE\n")
        self.assertTrue((self.job("fired") / "signal.json").is_file())
        self.assertEqual(self.invoke("observe", "fired"), 0)
        self.assertEqual(effect.read_bytes(), first)
        self.assertEqual(CHECK.check(self.root, "fired")["attempts"], 1)

    def test_failed_append_records_notification_and_stops_without_retry(self):
        self.assertEqual(self.invoke("prepare", "failed"), 0)
        self.assertEqual(self.invoke("stage-event", "failed"), 0)
        self.assertEqual(self.invoke("observe", "failed"), 1)
        failure = self.job("failed") / "failure.json"
        before = failure.read_bytes()
        self.assertEqual(self.invoke("observe", "failed"), 0)
        self.assertEqual(failure.read_bytes(), before)
        self.assertEqual((self.job("failed") / "delivery").read_bytes(), b"blocked\n")
        self.assertFalse((self.job("failed") / "delivery/effect.txt").is_file())
        self.assertEqual(CHECK.check(self.root, "failed")["status"], "failed")

    def test_prepare_refuses_reuse_without_changing_evidence(self):
        self.finish("fired")
        before = {path.relative_to(self.job("fired")): path.read_bytes()
                  for path in self.job("fired").rglob("*") if path.is_file()}
        self.assertEqual(self.invoke("prepare", "fired"), 2)
        after = {path.relative_to(self.job("fired")): path.read_bytes()
                 for path in self.job("fired").rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_checker_rejects_missing_duplicate_and_contradictory_evidence(self):
        self.finish("fired")
        job = self.job("fired")
        state_path = job / "state.json"
        original = state_path.read_bytes()
        state_path.unlink()
        with self.assertRaises((ValueError, OSError)):
            CHECK.check(self.root, "fired")
        state_path.write_bytes(original)
        effect = job / "delivery/effect.txt"
        effect.write_bytes(effect.read_bytes() * 2)
        with self.assertRaises(ValueError):
            CHECK.check(self.root, "fired")
        effect.write_bytes(b"mock effect DEMO-ONE\n")
        state = json.loads(original)
        state["terminal"] = False
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(ValueError):
            CHECK.check(self.root, "fired")

    def test_uncertain_or_contradictory_state_is_preserved_without_new_effect(self):
        self.finish("fired")
        job = self.job("fired")
        effect = job / "delivery/effect.txt"
        before = effect.read_bytes()
        for state in ({"status": "attempting", "attempts": 1, "terminal": True},
                      {"status": "configured", "attempts": 0, "terminal": False}):
            with self.subTest(state=state):
                state_path = job / "state.json"
                state_path.write_text(json.dumps(state), encoding="utf-8")
                original = state_path.read_bytes()
                self.assertEqual(self.invoke("observe", "fired"), 2)
                self.assertEqual(state_path.read_bytes(), original)
                self.assertEqual(effect.read_bytes(), before)

    def test_escaping_task_path_is_rejected_before_job_creation(self):
        task = self.root / "task.toml"
        original = task.read_text(encoding="utf-8")
        for value in ("../outside.txt", "/outside.txt", "C:/outside.txt", "..\\\\outside.txt"):
            with self.subTest(value=value):
                task.write_text(original.replace('effect = "delivery/effect.txt"', f'effect = "{value}"'),
                                encoding="utf-8")
                self.assertEqual(self.invoke("prepare", "fired"), 2)
                self.assertFalse((self.root / "output").exists())

    def test_symlink_destination_is_rejected_without_writing_target(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        try:
            (self.root / "output").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("directory symlink privilege unavailable")
        self.assertEqual(self.invoke("prepare", "fired"), 2)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
