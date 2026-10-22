"""Helpers shared by the tests."""

import os
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def child_env(**extra):
    """Environment for a `python -m awkit` child process.

    The child often runs in a temporary folder, so a relative PYTHONPATH such as `src` would not
    resolve there; put the absolute source folder first.
    """
    path = os.pathsep.join(p for p in (str(SRC), os.environ.get("PYTHONPATH", "")) if p)
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": path, **extra}
