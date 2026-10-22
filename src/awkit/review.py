"""Freeze explicitly selected changes and check a fixed Git object in isolation."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import tomllib

from .pipeline import atomic_json
from .process import run_to_files


def git(repo, *args, env=None):
    result = subprocess.run(["git", "-C", str(repo), *args], env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git command failed.")
    return result.stdout.strip()


def relative_file(value):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or any(p.lower() in ("", ".", "..", ".git") for p in value.split("/"))
            or "\\" in value or ":" in value or "\x00" in value):
        raise ValueError(f"Use a relative path inside the project: {value}")
    return path


def relative_directory(value):
    if not isinstance(value, str):
        raise ValueError("cwd must be a string path relative to the worktree.")
    return PurePosixPath(".") if value == "." else relative_file(value)


def snapshot(repo, paths):
    repo = Path(git(repo, "rev-parse", "--show-toplevel"))
    parent = git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    if not paths:
        raise ValueError("Name the changed files to include.")
    for name in paths:
        rel = relative_file(name)
        target = repo / rel
        if target.is_dir() or any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
                                  for p in [target, *target.parents] if p != repo.parent):
            raise ValueError(f"Directories and links cannot be included: {name}")
        if not target.resolve().is_relative_to(repo.resolve()):
            raise ValueError("The file is outside the repository.")
        if not target.exists() and not git(repo, "ls-files", "--error-unmatch", "--", name):
            raise ValueError(f"File not found: {name}")
    with tempfile.TemporaryDirectory(prefix="awkit-index-") as temporary:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        env["GIT_LITERAL_PATHSPECS"] = "1"
        env.update(GIT_AUTHOR_NAME="Agent Work Kit", GIT_AUTHOR_EMAIL="snapshot@localhost",
                   GIT_COMMITTER_NAME="Agent Work Kit", GIT_COMMITTER_EMAIL="snapshot@localhost")
        git(repo, "read-tree", parent, env=env)
        git(repo, "add", "-A", "--", *paths, env=env)
        tree = git(repo, "write-tree", env=env)
        return git(repo, "commit-tree", tree, "-p", parent, "-m", "Review snapshot", env=env)


def check(repo, revision, config, runs_root=None, keep=False):
    if not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", revision):
        raise ValueError("Give the full ID of the Git commit to check.")
    repo = Path(git(repo, "rev-parse", "--show-toplevel"))
    commit = git(repo, "rev-parse", "--verify", revision + "^{commit}")
    raw = Path(config).read_bytes()
    settings = tomllib.loads(raw.decode("utf-8"))
    if type(settings.get("schema")) is not int or settings["schema"] != 1:
        raise ValueError("The check configuration needs schema = 1.")
    timeout = settings.get("timeout_seconds", 300)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 86400:
        raise ValueError("timeout_seconds must be above 0 and at most 86400.")
    checks, setup = settings.get("checks"), settings.get("setup", [])
    if not isinstance(checks, list) or not checks or not isinstance(setup, list):
        raise ValueError("checks must list at least one command.")
    names = set()
    for step in setup + checks:
        if not isinstance(step, dict):
            raise ValueError("Each step must be a table.")
        name, argv = step.get("name"), step.get("argv")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("Each step needs a distinct name.")
        names.add(name)
        if not isinstance(argv, list) or not argv or any(not isinstance(s, str) for s in argv):
            raise ValueError("argv must be a non-empty array of strings.")
        relative_directory(step.get("cwd", "."))
    custom_env = settings.get("env", {})
    if not isinstance(custom_env, dict) or any(not isinstance(v, str) for v in custom_env.values()):
        raise ValueError("env values must be strings.")
    root = Path(runs_root or Path(tempfile.gettempdir()) / "agent-work-kit-reviews").resolve()
    root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="review-", dir=root))
    worktree = run / "worktree"
    result = {"snapshot": commit, "config_sha256": hashlib.sha256(raw).hexdigest(),
              "run_dir": str(run), "worktree": str(worktree), "status": "running", "steps": []}
    def save():
        atomic_json(run / "result.json", result)
    values = {"{worktree}": str(worktree), "{run_dir}": str(run), "{run_id}": run.name,
              "{python}": sys.executable}
    def expand(value):
        for key, replacement in values.items():
            value = value.replace(key, replacement)
        return value
    env = os.environ.copy()
    env.update({key: expand(value) for key, value in custom_env.items()})
    env.update(AWKIT_WORKTREE=str(worktree), AWKIT_RUN_DIR=str(run), AWKIT_RUN_ID=run.name)
    added = False
    preserve = keep
    save()
    try:
        git(repo, "worktree", "add", "--detach", str(worktree), commit)
        added = True
        for index, step in enumerate(setup + checks):
            step_dir = worktree / relative_directory(step.get("cwd", "."))
            entry = {"name": step["name"], "cwd": str(step_dir), "phase": "setup" if index < len(setup) else "check",
                     "log": f"{index + 1:02d}.log", "argv": [expand(s) for s in step["argv"]]}
            result["steps"].append(entry)
            with (run / entry["log"]).open("wb") as log:
                try:
                    # Resolve after preceding setup steps, which may create this directory.
                    resolved_dir = step_dir.resolve()
                    if not resolved_dir.is_relative_to(worktree.resolve()):
                        raise ValueError("cwd resolves outside the worktree.")
                    if not resolved_dir.is_dir():
                        raise ValueError("cwd directory does not exist: " + str(step_dir))
                    entry["cwd"] = str(resolved_dir)
                    returncode = run_to_files(entry["argv"], cwd=resolved_dir, env=env,
                                              stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                    entry.update(exit_code=returncode,
                                 status="passed" if returncode == 0 else "failed")
                except subprocess.TimeoutExpired:
                    entry["status"] = "timeout"
                    preserve = True
                except (OSError, ValueError) as exc:
                    entry.update(status="failed", error=str(exc))
            save()
            if entry["status"] == "timeout" or (index < len(setup) and entry["status"] != "passed"):
                break
        result["status"] = "passed" if (len(result["steps"]) == len(setup + checks)
            and all(s["status"] == "passed" for s in result["steps"])) else "failed"
        if any(s["status"] == "timeout" for s in result["steps"]):
            result["status"] = "uncertain"
    except BaseException:
        preserve = True
        result["status"] = "uncertain"
        raise
    finally:
        if added and not preserve:
            try:
                git(repo, "worktree", "remove", "--force", str(worktree))
            except ValueError as exc:
                result.update(status="cleanup-failed", cleanup_error=str(exc))
        result["worktree_retained"] = worktree.exists()
        save()
    return result
