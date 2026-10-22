"""The release's skills ZIP: unpacked in a home folder, it is the kit for a person without Python."""

import importlib.util
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from awkit import __version__
from awkit.connect import user_skills
from awkit.kit_install import SITUATIONS, WORKFLOW
from test_kit import skill_front_matter

ROOT = Path(__file__).resolve().parents[1]
NAMES = sorted(name for name, *_ in (WORKFLOW, *SITUATIONS))


def build_release():
    spec = importlib.util.spec_from_file_location("build_release", ROOT / "scripts" / "build_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillsZip(unittest.TestCase):
    def test_unpacked_in_a_home_folder_it_is_the_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            out, home = Path(temporary) / "dist", Path(temporary) / "home"
            out.mkdir()
            home.mkdir()
            target = build_release().build_kit_zip(out)
            self.assertEqual(target.name, f"agent-work-kit-skills-{__version__}.zip")
            with zipfile.ZipFile(target) as archive:
                names = archive.namelist()
                # Only skill files, at the paths Claude Code and Codex read in the user folder.
                self.assertEqual(sorted(names), sorted(f"{folder}/{name}/SKILL.md" for folder in
                                                       (".claude/skills", ".agents/skills") for name in NAMES))
                for name in names:
                    meta = skill_front_matter(archive.read(name).decode("utf-8"))
                    self.assertEqual(meta["name"], Path(name).parent.name)
                archive.extractall(home)
            with mock.patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
                found = user_skills()
            self.assertEqual({p: sorted(n for n, _ in s) for p, s in found.items()}, {"claude": NAMES, "codex": NAMES})
            self.assertEqual({v for s in found.values() for _, v in s}, {__version__})


if __name__ == "__main__":
    unittest.main()
