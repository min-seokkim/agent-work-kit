import json
import ntpath
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from awkit.kit_install import install
from awkit.review import track
from awkit.scan import scan
from support import child_env


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
        (workflows / "ci.yml").write_text(
            "jobs:\n  t:\n    steps:\n      - run: npm ci\n      - run: npm test\n"
            "      - run: python -m unittest discover -s tests -v\n      - run: ruff check .\n"
            "      - run: echo done && make lint\n      - name: x\n        run: |\n          make lint\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "a.md").write_text("# a", encoding="utf-8")
        (self.root / "README.md").write_text("# r", encoding="utf-8")
        report = scan(self.root)
        self.assertEqual(report["manifests"], ["Makefile", "package.json", "pyproject.toml"])
        self.assertEqual(report["languages"], ["javascript", "make", "python"])
        names = {c["name"]: c for c in report["commands"]}
        # What CI runs comes first; install steps and shell lines are not offered as checks.
        self.assertEqual([(c["name"], c["source"]) for c in report["commands"][:3]],
                         [("npm-test", ".github/workflows/ci.yml"), ("unittest-discover", ".github/workflows/ci.yml"),
                          ("ruff-check", ".github/workflows/ci.yml")])
        self.assertEqual(names["unittest-discover"]["argv"], ["{python}", "-m", "unittest", "discover", "-s", "tests", "-v"])
        # The same check from a manifest is not repeated: npm run test and python -m ruff check . are dropped.
        self.assertNotIn("test", names)
        self.assertNotIn("lint", names)
        self.assertEqual(names["build"]["argv"], ["npm", "run", "build"])
        self.assertIn("make-lint", names)
        self.assertNotIn("make-deploy", names)
        # A tests folder without pytest configuration does not make pytest a suggestion.
        self.assertFalse(any("pytest" in c["argv"] for c in report["commands"]))
        self.assertEqual(report["ci"][0]["run"][:2], ["npm ci", "npm test"])
        self.assertEqual((report["docs_folders"], report["markdown_files"]), (["docs"], 2))
        self.assertIsNone(report["git"]["repository"])
        self.assertFalse(report["kit"]["present"])
        suggested = tomllib.loads(report["suggested_checks_toml"])
        self.assertEqual(suggested["schema"], 1)
        self.assertEqual([c["name"] for c in suggested["checks"]], list(names))
        (self.root / "conftest.py").write_text("", encoding="utf-8")
        self.assertIn(["{python}", "-m", "pytest", "-q"], [c["argv"] for c in scan(self.root)["commands"]])

    def test_reports_the_kit_and_repository_once_installed(self):
        target, _ = install(self.root)
        track(self.root, [target], "Add agent-work-kit")
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
        env = child_env()
        full = subprocess.run([sys.executable, "-m", "awkit", "kit", "scan", str(self.root)], capture_output=True,
                              text=True, encoding="utf-8", env=env)
        self.assertEqual(full.returncode, 0, full.stderr)
        self.assertEqual(json.loads(full.stdout)["languages"], ["go"])
        only = subprocess.run([sys.executable, "-m", "awkit", "kit", "scan", str(self.root), "--checks"],
                              capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(tomllib.loads(only.stdout)["checks"][0]["argv"], ["go", "test", "./..."])
        with self.assertRaises(ValueError):
            scan(self.root / "missing")

    def test_cli_default_dot_and_absolute_select_same_project(self):
        project = self.root / "project with spaces \ud55c\uae00"
        project.mkdir()
        (project / "go.mod").write_text("module x\n", encoding="utf-8")
        reports = []
        for arguments in ([], ["."], [str(project)]):
            result = subprocess.run([sys.executable, "-m", "awkit", "kit", "scan", *arguments],
                                    cwd=project, env=child_env(), capture_output=True,
                                    text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            reports.append(json.loads(result.stdout))
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(reports[0], reports[2])
        self.assertEqual(reports[0]["languages"], ["go"])

    @unittest.skipUnless(os.name == "nt", "Windows realpath fallback")
    def test_scan_when_windows_denies_trailing_dot(self):
        original = ntpath._getfinalpathname

        def denied_dot(path):
            if path.endswith("\\."):
                error = PermissionError(13, "Simulated trailing-dot access denial")
                error.winerror = 5
                raise error
            return original(path)

        (self.root / "go.mod").write_text("module x\n", encoding="utf-8")
        with chdir(self.root), patch.object(ntpath, "_getfinalpathname", denied_dot):
            # Exercise Python's real fallback; only the denied OS call is mocked.
            self.assertEqual(scan("."), scan(self.root))

    def test_relative_scan_still_follows_directory_links(self):
        target = self.root / "target"
        target.mkdir()
        (target / "go.mod").write_text("module x\n", encoding="utf-8")
        link = self.root / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Directory links unavailable: {exc}")
        with chdir(self.root):
            self.assertEqual(scan("link"), scan(target))


if __name__ == "__main__":
    unittest.main()
