"""Helpers shared by the tests."""

import os
from pathlib import Path

import awkit

SRC = Path(__file__).resolve().parents[1] / "src"

# An installed copy of awkit (a cloud session installs one) must not stand in for the code under test.
if Path(awkit.__file__).resolve().parent != SRC / "awkit":
    raise ImportError(f"The tests imported awkit from {awkit.__file__}, not from {SRC}. "
                      "Run them with PYTHONPATH=src so they test this source tree.")


# No background `git gc --auto` or maintenance from the test repositories: a detached gc started by a test's
# commit kept writing .git/objects/pack after the test returned, and removing the temporary folder failed with
# "Directory not empty" on Linux CI (test_connect, runs on 26e2d34 and c08418b). Command-scope configuration
# reaches every git the tests start, including those started by awkit, and leaves user configuration alone.
_count = int(os.environ.get("GIT_CONFIG_COUNT", "0") or 0)
for _key, _value in (("gc.auto", "0"), ("maintenance.auto", "false")):
    os.environ[f"GIT_CONFIG_KEY_{_count}"], os.environ[f"GIT_CONFIG_VALUE_{_count}"] = _key, _value
    _count += 1
os.environ["GIT_CONFIG_COUNT"] = str(_count)


def child_env(**extra):
    """Environment for a `python -m awkit` child process.

    The child often runs in a temporary folder, so a relative PYTHONPATH such as `src` would not
    resolve there; put the absolute source folder first.
    """
    path = os.pathsep.join(p for p in (str(SRC), os.environ.get("PYTHONPATH", "")) if p)
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": path, **extra}


# How long a test waits for a background thread or child process to reach a condition. Waits return as soon as
# the condition holds, so the budget only matters on a slow runner: Windows CI took 4.7 s from send to turn
# start in one run, which failed a 5 s wait (run 41392966470). Admission alone has a 30 s RPC budget.
WAIT_SECONDS = 35
