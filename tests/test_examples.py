import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit.kit_install import EXAMPLES, install_example
from awkit.review import accept, check, compare, git, snapshot, track, verify
from support import child_env


def run(*args, cwd):
    return subprocess.run([sys.executable, "-m", "awkit", *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", env=child_env())


# The edits each example README asks for in prose, keyed by (section number, index of the command
# block they come before). "<new run_dir>" in a block means: snapshot and check again as in step 3.
EDITS = {
    "documents": {(3, 0): ("docs/index.md", "config.md", "setup.md"),
                  (5, 1): ("docs/guide.md", "메모는", "새 메모는")},
    "data": {(3, 0): ("input/orders.csv", "qty", "quantity"),
             (5, 1): ("input/orders.csv", "notebook,3,", "notebook,4,")},
    "analysis": {(3, 0): ("assumptions.toml", "sample_rate_hz = 10 ", "sample_rate_hz = 20 "),
                 (4, 1): ("assumptions.toml", "counts_per_g = 2048", "counts_per_g = 1024")},
}
SECTION = re.compile(r"^## (\d+)\.", re.M)
BLOCK = re.compile(r"^```sh\n(.*?)^```", re.M | re.S)


def readme_blocks(readme):
    """[(section number, block index, [command lines])] for the numbered sections of a README."""
    text = readme.read_text(encoding="utf-8")
    starts = [(int(m.group(1)), m.start()) for m in SECTION.finditer(text)] + [(None, len(text))]
    blocks = []
    for (number, start), (_, end) in zip(starts, starts[1:], strict=False):
        for index, block in enumerate(BLOCK.findall(text[start:end])):
            blocks.append((number, index, [line for line in block.splitlines() if line.strip()]))
    return blocks


class ExampleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def commit_all(self, folder):
        """Track the example the way the CLI does after creating it; return the first commit."""
        record = track(folder, [folder], "Start the example")
        self.assertEqual((record["created"], record["committed"]), (True, True))
        self.assertEqual(git(folder, "config", "core.autocrlf"), "false")
        self.assertEqual(git(folder, "status", "--porcelain"), "")
        return git(folder, "rev-parse", "HEAD")

    def test_examples_are_created_once_with_every_file_and_tracked(self):
        for kind in EXAMPLES:
            with self.subTest(kind=kind):
                target, copied = install_example(kind, self.root / kind)
                self.assertEqual(target, (self.root / kind).absolute())
                self.assertIn("README.md", copied)
                self.assertIn("checks.toml", copied)
                self.assertIn("project.md", copied)
                self.assertTrue(any(name.endswith(".py") for name in copied))
                self.assertFalse((target / ".git").exists())  # copying and tracking are separate steps
                record = track(target, [target], f"Add the {kind} example")
                self.assertEqual((record["created"], record["committed"], record["skipped"]), (True, True, None))
                self.assertEqual(git(target, "log", "--format=%s"), f"Add the {kind} example")
                with self.assertRaises(ValueError):
                    install_example(kind, self.root / kind)
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith(".")], [])
        # Review commands never create a repository or commit; an untracked folder is refused.
        bare, _ = install_example("data", self.root / "untracked")
        for call in (lambda: snapshot(bare, ["input/orders.csv"]),
                     lambda: check(bare, "HEAD", bare / "checks.toml", self.root / "runs"),
                     lambda: compare(bare)):
            with self.assertRaisesRegex(ValueError, "Not a Git repository"):
                call()
        self.assertFalse((bare / ".git").exists())
        git(bare, "init")
        with self.assertRaisesRegex(ValueError, "no commit yet"):
            snapshot(bare, ["input/orders.csv"])

    def test_example_inside_an_existing_repository_is_committed_there(self):
        for with_history in (False, True):
            with self.subTest(with_history=with_history):
                outer = self.root / f"outer-{with_history}"
                outer.mkdir()
                git(outer, "init")
                git(outer, "config", "core.autocrlf", "false")
                (outer / "notes.txt").write_text("mine", encoding="utf-8")
                if with_history:
                    git(outer, "add", "notes.txt")
                    git(outer, "-c", "user.name=f", "-c", "user.email=f@localhost", "commit", "-m", "mine")
                target, _ = install_example("data", outer / "data-example")
                record = track(target, [target], "Add the data example")
                self.assertEqual((record["created"], record["committed"]), (False, True))
                self.assertFalse((target / ".git").exists())
                self.assertIn("data-example/README.md", git(outer, "ls-files"))
                self.assertEqual("notes.txt" in git(outer, "ls-files"), with_history)  # never swept in
                self.assertEqual(git(outer, "status", "--porcelain", "--", "data-example"), "")
                # The README's first command works from inside the example folder.
                failed = check(target, "HEAD", target / "checks.toml", self.root / "runs")
                self.assertEqual((failed["status"], failed["subdir"]), ("failed", "data-example"))
                self.assertIn("missing column", (Path(failed["run_dir"]) / "01.log").read_text(encoding="utf-8"))
                # Paths in the snapshot, the artifacts and the comparison stay relative to the example folder.
                orders = target / "input" / "orders.csv"
                orders.write_text(orders.read_text(encoding="utf-8").replace("qty", "quantity"), encoding="utf-8")
                passed = check(target, snapshot(target, ["input/orders.csv"]), target / "checks.toml", self.root / "runs")
                self.assertEqual(passed["status"], "passed", passed)
                self.assertEqual(sorted(passed["artifacts"]), ["input/orders.csv", "output/summary.csv"])
                accept(target, passed["run_dir"])
                statuses = {f["path"]: f["status"] for f in compare(target)["files"]}
                self.assertEqual(statuses, {"input/orders.csv": "same", "output/summary.csv": "missing"})
                self.assertEqual(git(outer, "status", "--porcelain", "--", "data-example"), "M data-example/input/orders.csv")
        # Staged work of the user's own is never bundled into the kit's commit.
        outer = self.root / "outer-True"
        (outer / "draft.txt").write_text("staged", encoding="utf-8")
        git(outer, "add", "draft.txt")
        target, _ = install_example("documents", outer / "docs-example")
        record = track(target, [target], "Add the documents example")
        self.assertEqual((record["committed"], record["skipped"]), (False, "the index already has staged changes"))
        self.assertNotIn("docs-example", git(outer, "ls-files"))
        self.assertEqual(git(outer, "diff", "--cached", "--name-only"), "draft.txt")
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

    def test_analysis_example_fails_then_passes_and_compares_with_the_accepted_run(self):
        folder, _ = install_example("analysis", self.root / "analysis example")
        head = self.commit_all(folder)
        failed = check(folder, head, folder / "checks.toml", self.root / "runs")
        self.assertEqual(failed["status"], "failed")
        self.assertIn("sample_rate_hz", (Path(failed["run_dir"]) / "01.log").read_text(encoding="utf-8"))
        assumptions = folder / "assumptions.toml"
        assumptions.write_text(assumptions.read_text(encoding="utf-8").replace("sample_rate_hz = 10 ", "sample_rate_hz = 20 "),
                               encoding="utf-8")
        revision = snapshot(folder, ["assumptions.toml"])
        passed = check(folder, revision, folder / "checks.toml", self.root / "runs")
        self.assertEqual(passed["status"], "passed", passed)
        report = json.loads((Path(passed["run_dir"]) / "artifacts/output/report.json").read_text(encoding="utf-8"))
        self.assertEqual(set(report), {"observed", "assumptions", "computed", "interpretation", "interpretation_status"})
        self.assertEqual(report["computed"]["peak_g"], 0.75)
        self.assertIsNone(report["interpretation"])
        accept(folder, passed["run_dir"])
        self.assertTrue(compare(folder, run_dir=passed["run_dir"])["unchanged"])
        assumptions.write_text(assumptions.read_text(encoding="utf-8").replace("counts_per_g = 2048", "counts_per_g = 1024"),
                               encoding="utf-8")
        again = check(folder, snapshot(folder, ["assumptions.toml"]), folder / "checks.toml", self.root / "runs")
        self.assertEqual(again["status"], "passed", again)
        diffed = compare(folder, run_dir=again["run_dir"], diff=True)
        statuses = {f["path"]: f["status"] for f in diffed["files"]}
        self.assertEqual(statuses, {"assumptions.toml": "changed", "input/readings.csv": "same",
                                    "output/report.json": "changed"})
        self.assertIn('"peak_g": 1.5', next(f["diff"] for f in diffed["files"] if f["path"] == "output/report.json"))

    def test_readme_commands_work_as_written(self):
        # F4, F5: an example created inside a repository with history was not committed, so the
        # README's first command failed. Every command in the READMEs runs here as written.
        for kind in EDITS:
            with self.subTest(kind=kind):
                outer = self.root / f"project-{kind}"
                outer.mkdir()
                git(outer, "init", "-q")
                (outer / "notes.txt").write_text("mine", encoding="utf-8")
                git(outer, "add", "notes.txt")
                git(outer, "-c", "user.name=f", "-c", "user.email=f@localhost", "commit", "-q", "-m", "mine")
                created = run("kit", "example", kind, str(outer / "example"), cwd=outer)
                self.assertEqual(created.returncode, 0, created.stderr)
                folder = outer / "example"
                variables, checks, rerun = {}, [], None
                for number, index, lines in readme_blocks(folder / "README.md"):
                    if (number, index) in EDITS[kind]:
                        name, old, new = EDITS[kind][(number, index)]
                        path = folder / name
                        text = path.read_text(encoding="utf-8")
                        self.assertIn(old, text)
                        path.write_text(text.replace(old, new, 1), encoding="utf-8")
                    if number == 3:
                        rerun = lines
                    for line in (rerun if any("<new run_dir>" in line for line in lines) else []) + lines:
                        line = line.replace("<new run_dir>", checks[-1]["run_dir"] if checks else "")
                        line = line.replace("<run_dir>", checks[-1]["run_dir"] if checks else "")
                        target, _, command = line.rpartition("=$(") if "=$(" in line else ("", "", line)
                        command = command.removesuffix(")") if target else command
                        argv = shlex.split(command)
                        argv = [variables.get(arg.lstrip("$"), arg) if arg.startswith("$") else arg for arg in argv]
                        self.assertEqual(argv[0], "awkit", line)
                        result = run(*argv[1:], cwd=folder)
                        self.assertIn(result.returncode, (0, 1), f"{kind}: {line}\n{result.stderr}")
                        if target:
                            variables[target] = result.stdout.strip()
                        if argv[1:3] == ["review", "check"]:
                            checks.append(json.loads(result.stdout))
                statuses = [record["status"] for record in checks]
                self.assertEqual(statuses[:2], ["failed", "passed"], kind)
                self.assertTrue(all(status == "passed" for status in statuses[1:]), kind)
                self.assertEqual(git(outer, "ls-files", "--", "notes.txt"), "notes.txt")

    def test_cli_example(self):
        created = run("kit", "example", "documents", str(self.root / "d"), cwd=self.root)
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertIn("README.md", created.stdout)
        self.assertIn("initialized a Git repository", created.stdout)
        self.assertEqual(git(self.root / "d", "log", "--format=%s"), "Add the documents example")
        plain = run("kit", "example", "data", str(self.root / "p"), "--no-git", cwd=self.root)
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertFalse((self.root / "p" / ".git").exists())
        again = run("kit", "example", "documents", str(self.root / "d"), cwd=self.root)
        self.assertEqual(again.returncode, 2)
        self.assertIn("already exists", again.stderr)


if __name__ == "__main__":
    unittest.main()
