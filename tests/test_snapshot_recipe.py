"""The bash snapshot recipe in reference.md, run as written on a repository with awkward file names."""

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit.review import git
from support import child_env

ROOT = Path(__file__).resolve().parents[1]


def bash_recipe():
    text = (ROOT / "kit" / "reference.md").read_text(encoding="utf-8")
    section = text.split("### snapshot", 1)[1].split("### check", 1)[0]
    return re.search(r"In bash[^\n]*\n\n```sh\n(.*?)```", section, re.S).group(1)


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "the recipe is for bash on POSIX")
class BashSnapshotRecipe(unittest.TestCase):
    def test_changed_added_and_spaced_or_non_ascii_files_are_snapshotted(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, tools = Path(temp) / "repo", Path(temp) / "bin"
            repo.mkdir()
            tools.mkdir()
            shim = tools / "awkit"
            shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m awkit "$@"\n', encoding="utf-8")
            shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "owner")
            git(repo, "config", "user.email", "owner@example.com")
            (repo / "kept.md").write_text("first\n", encoding="utf-8")
            git(repo, "add", "kept.md")
            git(repo, "commit", "-q", "-m", "First")
            env = child_env(PATH=f"{tools}{os.pathsep}{os.environ['PATH']}")
            empty = subprocess.run(["bash", "-c", bash_recipe()], cwd=repo, env=env, capture_output=True, text=True)
            self.assertEqual(empty.stdout.strip(), "")
            (repo / "kept.md").write_text("changed\n", encoding="utf-8")
            (repo / "with space.md").write_text("added\n", encoding="utf-8")
            (repo / "한글 이름.md").write_text("추가\n", encoding="utf-8")
            result = subprocess.run(["bash", "-c", bash_recipe()], cwd=repo, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            commit = result.stdout.strip()
            self.assertRegex(commit, r"^[0-9a-f]{40}$")
            files = git(repo, "ls-tree", "-r", "-z", "--name-only", commit).split("\0")
            self.assertEqual(sorted(f for f in files if f), sorted(["kept.md", "with space.md", "한글 이름.md"]))
            self.assertEqual(git(repo, "show", f"{commit}:kept.md"), "changed")
            self.assertEqual(git(repo, "status", "--porcelain").count("??"), 2)  # worktree and index untouched


if __name__ == "__main__":
    unittest.main()
