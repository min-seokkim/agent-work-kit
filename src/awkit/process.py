"""Run project commands so that a timeout stops everything they started."""

from __future__ import annotations

import os
import signal
import subprocess


def spawn_options():
    # Put the command in its own process group so the whole tree can be stopped together.
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def kill_tree(process):
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass


def run_to_files(args, *, cwd, stdout, stderr, timeout, env=None):
    """Run args with output going to open file objects; raise TimeoutExpired after killing the tree."""
    process = subprocess.Popen(args, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                               stdin=subprocess.DEVNULL, shell=False, **spawn_options())
    try:
        return process.wait(timeout=timeout)
    except BaseException:
        kill_tree(process)
        raise
