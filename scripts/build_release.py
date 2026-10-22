"""Build the release files: the wheel, the skills ZIP and SHA256SUMS.

The skills ZIP is the kit for a person without Python: the self-contained skills `awkit kit skills` writes,
laid out as they go in the user's home folder (`.claude/skills/awkit-*/SKILL.md` for Claude Code,
`.agents/skills/awkit-*/SKILL.md` for Codex), so unpacking it there is the whole installation.

Usage: python scripts/build_release.py [OUT_DIR]   (default: dist)
Needs setuptools>=77 and wheel in the running Python. No network access is required.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awkit import __version__  # noqa: E402


def build_wheel(out: Path) -> Path:
    from setuptools import build_meta

    with tempfile.TemporaryDirectory() as temporary:
        previous = Path.cwd()
        try:
            import os
            os.chdir(ROOT)
            name = build_meta.build_wheel(temporary)
        finally:
            os.chdir(previous)
        built = Path(temporary) / name
        target = out / name
        shutil.copyfile(built, target)
    for leftover in (ROOT / "build", *ROOT.glob("src/*.egg-info"), *ROOT.glob("*.egg-info")):
        shutil.rmtree(leftover, ignore_errors=True)
    return target


def build_kit_zip(out: Path) -> Path:
    from awkit.kit_install import install_user_skills

    target = out / f"agent-work-kit-skills-{__version__}.zip"
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        install_user_skills(home=home)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(home.rglob("SKILL.md")):
                archive.write(path, path.relative_to(home).as_posix())
    return target


def main(argv):
    out = (Path(argv[1]) if len(argv) > 1 else ROOT / "dist").resolve()
    out.mkdir(parents=True, exist_ok=True)
    files = [build_wheel(out), build_kit_zip(out)]
    sums = "".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n" for f in files)
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8")
    for path in files:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
