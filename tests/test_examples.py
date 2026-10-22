import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit.kit_install import EXAMPLES, install_example
from awkit.review import check, git, snapshot, verify


def run(*args, cwd):
    return subprocess.run([sys.executable, "-m", "awkit", *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})


class ExampleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def commit_all(self, folder):
        git(folder, "init")
        git(folder, "config", "user.name", "Fixture")
        git(folder, "config", "user.email", "fixture@localhost")
        git(folder, "config", "core.autocrlf", "false")
        git(folder, "add", "-A")
        git(folder, "commit", "-m", "Start")
        return git(folder, "rev-parse", "HEAD")

    def test_examples_are_created_once_with_every_file(self):
        for kind in EXAMPLES:
            with self.subTest(kind=kind):
                target, copied = install_example(kind, self.root / kind)
                self.assertEqual(target, (self.root / kind).absolute())
                self.assertIn("README.md", copied)
                self.assertIn("checks.toml", copied)
                self.assertIn("project.md", copied)
                self.assertTrue(any(name.endswith(".py") for name in copied))
                with self.assertRaises(ValueError):
                    install_example(kind, self.root / kind)
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith(".")], [])
        with self.assertRaises(ValueError):
            install_example("video", self.root / "x")
        with self.assertRaises(ValueError):
            install_example("data", self.root / "missing-parent" / "x")

    def test_documents_example_fails_then_passes_after_the_fix(self):
        folder, _ = install_example("documents", self.root / "docs example")
        head = self.commit_all(folder)
        failed = check(folder, head, folder / "checks.toml", self.root / "runs")
        self.assertEqual(failed["status"], "failed")
        log = (Path(failed["run_dir"]) / "01.log").read_text(encoding="utf-8")
        self.assertIn("config.md", log)
        self.assertIn("docs/index.md", failed["artifacts"])  # the checked documents are kept even on failure
        index = folder / "docs" / "index.md"
        index.write_text(index.read_text(encoding="utf-8").replace("config.md", "setup.md"), encoding="utf-8")
        revision = snapshot(folder, ["docs/index.md"])
        passed = check(folder, revision, folder / "checks.toml", self.root / "runs")
        self.assertEqual(passed["status"], "passed", passed)
        self.assertEqual(set(passed["artifacts"]), {"docs/index.md", "docs/guide.md", "docs/setup.md"})
        self.assertTrue(verify(passed["run_dir"])["verified"])
        self.assertEqual(git(folder, "rev-parse", "HEAD"), head)  # the snapshot left the branch alone

    def test_data_example_fails_then_passes_after_the_fix(self):
        folder, _ = install_example("data", self.root / "data example")
        head = self.commit_all(folder)
        failed = check(folder, head, folder / "checks.toml", self.root / "runs")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual([step["name"] for step in failed["steps"]], ["process"])
        self.assertEqual(failed["missing_artifacts"], ["output/summary.csv"])
        self.assertIn("quantity", (Path(failed["run_dir"]) / "01.log").read_text(encoding="utf-8"))
        orders = folder / "input" / "orders.csv"
        orders.write_text(orders.read_text(encoding="utf-8").replace("qty", "quantity", 1), encoding="utf-8")
        revision = snapshot(folder, ["input/orders.csv"])
        passed = check(folder, revision, folder / "checks.toml", self.root / "runs")
        self.assertEqual(passed["status"], "passed", passed)
        summary = (Path(passed["run_dir"]) / "artifacts" / "output" / "summary.csv").read_text(encoding="utf-8")
        self.assertIn("notebook,6,15000", summary)
        self.assertFalse((folder / "output").exists())  # produced in the worktree, not the working folder

    def test_cli_example(self):
        created = run("kit", "example", "documents", str(self.root / "d"), cwd=self.root)
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertIn("README.md", created.stdout)
        again = run("kit", "example", "documents", str(self.root / "d"), cwd=self.root)
        self.assertEqual(again.returncode, 2)
        self.assertIn("already exists", again.stderr)


if __name__ == "__main__":
    unittest.main()
