"""Build the release files: the wheel, the agent-work-kit ZIP and SHA256SUMS.

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
    target = out / f"agent-work-kit-{__version__}.zip"
    kit = ROOT / "kit"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(kit.rglob("*.md")):
            archive.write(path, Path("agent-work-kit") / path.relative_to(kit))
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
