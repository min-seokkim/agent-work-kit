"""The user layer: the kit's guides as skills in the user's skill folders, which Claude Code and Codex read
in every project, and `kit guide`, which prints a guide for agents without skills and for people."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from awkit import __version__, environment
from awkit.kit_install import SITUATIONS, WORKFLOW, guide, guide_files, install_user_skills
from awkit.review import git
from support import child_env
from test_kit import skill_front_matter

NAMES = [name for name, *_ in (WORKFLOW, *SITUATIONS)]
# What the skills in the user folder add to every session: one line per skill.
SESSION_WORD_LIMIT = 150


class Isolated(unittest.TestCase):
    """A temporary home folder, so the user's real skill folders are never read or written."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        patch = mock.patch.dict(os.environ, {**child_env(), "HOME": str(self.home), "USERPROFILE": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)

    def repository(self, name, files):
        root = self.base / name
        root.mkdir()
        git(root, "init", "-q")
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        return root

    def awkit(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-m", "awkit", *args], capture_output=True, text=True,
                              encoding="utf-8", env=os.environ.copy(), cwd=cwd, stdin=subprocess.DEVNULL)


class UserLayer(Isolated):
    def test_skills_go_to_the_user_folders_and_parse_for_both_agents(self):
        result = self.awkit("kit", "skills")
        self.assertEqual(result.returncode, 0, result.stderr)
        folders = {"claude": self.home / ".claude" / "skills", "codex": self.home / ".agents" / "skills"}
        for folder in folders.values():
            self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted(NAMES))
            for name in NAMES:
                text = (folder / name / "SKILL.md").read_text(encoding="utf-8")
                meta = skill_front_matter(text)
                # Both agents read name and description: the name matches the folder, lowercase letters,
                # digits and hyphens up to 64 characters; the description is one line within 1024.
                self.assertEqual(set(meta), {"name", "description"})
                self.assertEqual(meta["name"], name)
                self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
                self.assertNotIn("\n", meta["description"])
                self.assertLessEqual(len(meta["description"]), 1024)
                # One line says which awkit made the file and how to update it.
                header = [line for line in text.splitlines() if line.startswith(environment.GENERATED)]
                self.assertEqual(len(header), 1)
                self.assertIn(f"by awkit {__version__}", header[0])
                self.assertIn("Update with `awkit kit skills`", header[0])
        record = json.loads((self.home / ".awkit" / "installed.json").read_text(encoding="utf-8"))
        self.assertEqual(len(record["files"]), 2 * len(NAMES))
        self.assertLessEqual(max(environment.session_words(self.base).values()), SESSION_WORD_LIMIT)

    def test_without_leaves_skills_out_and_removes_earlier_ones(self):
        install_user_skills()
        results, _ = install_user_skills(without=["delegation,review-session"])
        names = sorted(p.name for p in (self.home / ".claude" / "skills").iterdir())
        self.assertEqual(names, sorted(set(NAMES) - {"awkit-delegation", "awkit-review-session"}))
        self.assertEqual(len(results["codex"]["removed"]), 2)
        with self.assertRaises(ValueError):
            install_user_skills(without=["nothing-like-this"])

    def test_project_skills_only_with_project(self):
        root = self.repository("project", {"README.md": "# P\n"})
        result = self.awkit("kit", "skills", "--project", "--provider", "claude", str(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list((root / ".claude" / "skills").glob("awkit-*/SKILL.md"))), len(NAMES))
        self.assertFalse((self.home / ".claude").exists())

    def test_guides_print_with_links_turned_into_guide_names(self):
        for name in guide_files():
            text = guide(name)
            self.assertTrue(text.strip(), name)
            # A printed guide has no folder around it: links to kit files become guide names.
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                self.assertRegex(target, r"^(https?:|#)", f"{name}: {target}")
        self.assertIn("`awkit kit guide connect`", guide("workflow"))
        self.assertTrue(guide("profile").startswith("# "))
        result = self.awkit("kit", "guide", "no-such-guide")
        self.assertEqual(result.returncode, 2)
        self.assertIn("connect", result.stderr)
        listed = self.awkit("kit", "guide")
        self.assertIn("profile", listed.stdout.split())


if __name__ == "__main__":
    unittest.main()
