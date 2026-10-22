import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from awkit.kit_install import install
from awkit.scan import scan


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()

    def test_reports_manifests_commands_ci_and_git_state(self):
        (self.root / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run", "build": "vite build"}}))
        (self.root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "Makefile").write_text("lint:\n\truff check .\ndeploy:\n\t./deploy.sh\n", encoding="utf-8")
        workflows = self.root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("jobs:\n  t:\n    steps:\n      - run: npm test\n      - name: x\n        run: |\n          make lint\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "a.md").write_text("# a", encoding="utf-8")
        (self.root / "README.md").write_text("# r", encoding="utf-8")
        report = scan(self.root)
        self.assertEqual(report["manifests"], ["Makefile", "package.json", "pyproject.toml"])
        self.assertEqual(report["languages"], ["javascript", "make", "python"])
        names = {c["name"]: c for c in report["commands"]}
        self.assertEqual(names["test"]["argv"], ["npm", "run", "test"])
        self.assertEqual(names["tests"]["argv"], ["{python}", "-m", "pytest", "-q"])
        self.assertEqual(names["lint"]["source"], "pyproject.toml [tool.ruff]")
        self.assertIn("make-lint", names)
        self.assertNotIn("make-deploy", names)
        self.assertEqual(report["ci"], [{"file": ".github/workflows/ci.yml", "run": ["npm test"]}])
        self.assertEqual((report["docs_folders"], report["markdown_files"]), (["docs"], 2))
        self.assertIsNone(report["git"]["repository"])
        self.assertFalse(report["kit"]["present"])
        suggested = tomllib.loads(report["suggested_checks_toml"])
        self.assertEqual(suggested["schema"], 1)
        self.assertEqual([c["name"] for c in suggested["checks"]], list(names))

    def test_reports_the_kit_and_repository_once_installed(self):
        install(self.root)
        report = scan(self.root)
        self.assertEqual(report["git"]["uncommitted_files"], 0)
        self.assertEqual(len(report["git"]["head"]), 40)
        self.assertTrue(report["kit"]["present"])
        self.assertEqual((report["kit"]["start_here_fields"], report["kit"]["start_here_filled"]), (5, 0))
        profile = self.root / "agent-work-kit" / "templates" / "project.md"
        profile.write_text(profile.read_text(encoding="utf-8").replace("- Desired result:", "- Desired result: a wheel"),
                           encoding="utf-8")
        self.assertEqual(scan(self.root)["kit"]["start_here_filled"], 1)
        self.assertEqual(scan(self.root)["git"]["uncommitted_files"], 1)

    def test_cli_scan(self):
        (self.root / "go.mod").write_text("module x\n", encoding="utf-8")
        env = {**os.environ, "PYTHONUTF8": "1"}
        full = subprocess.run([sys.executable, "-m", "awkit", "kit", "scan", str(self.root)], capture_output=True,
                              text=True, encoding="utf-8", env=env)
        self.assertEqual(full.returncode, 0, full.stderr)
        self.assertEqual(json.loads(full.stdout)["languages"], ["go"])
        only = subprocess.run([sys.executable, "-m", "awkit", "kit", "scan", str(self.root), "--checks"],
                              capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(tomllib.loads(only.stdout)["checks"][0]["argv"], ["go", "test", "./..."])
        with self.assertRaises(ValueError):
            scan(self.root / "missing")


if __name__ == "__main__":
    unittest.main()
