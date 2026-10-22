"""Freeze explicitly selected changes and check a fixed Git object in isolation."""

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath

from .pipeline import LABEL, atomic_json, stamp
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


def artifact_patterns(settings):
    """Validate `artifacts` and `required_artifacts`: glob patterns relative to the worktree."""
    patterns = {}
    for key in ("artifacts", "required_artifacts"):
        values = settings.get(key, [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError(f"{key} must be an array of relative glob patterns.")
        for value in values:
            relative_file(value.replace("*", "x").replace("?", "x").replace("[", "x").replace("]", "x"))
        patterns[key] = values
    return patterns["artifacts"], patterns["required_artifacts"]


def collect_artifacts(worktree, run, patterns, required):
    """Copy the files matching `patterns` from the worktree into run/artifacts and hash them.

    Returns (files, missing): files maps each retained relative path to its size and SHA-256;
    missing lists the required patterns that matched nothing. Links and anything resolving
    outside the worktree are skipped and reported under `skipped`.
    """
    worktree = worktree.resolve()
    destination = run / "artifacts"
    files, missing, skipped = {}, [], []
    for pattern in dict.fromkeys(patterns + required):
        matched = False
        for path in sorted(worktree.glob(pattern)):
            relative = path.relative_to(worktree).as_posix()
            if ".git" in path.relative_to(worktree).parts:
                continue
            if any(p.is_symlink() for p in [path, *path.parents] if p != worktree.parent) \
                    or not path.resolve().is_relative_to(worktree) or not path.is_file():
                if path.is_file() or path.is_symlink():
                    skipped.append(relative)
                continue
            matched = True
            if relative in files:
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes()
            target.write_bytes(data)
            files[relative] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if not matched and pattern in required:
            missing.append(pattern)
    return files, missing, skipped


def verify(run_dir):
    """Compare the artifacts retained by `check` with the manifest written at that time."""
    run = Path(run_dir).resolve()
    record_path = run / "result.json"
    if not record_path.is_file():
        raise ValueError(f"No result.json in the run folder: {run}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    report = {"run_dir": str(run), "snapshot": record.get("snapshot"),
              "config_sha256": record.get("config_sha256"), "check_status": record.get("status"),
              "interrupted": record.get("status") == "running", "artifacts": [], "unexpected": []}
    manifest_path = run / "artifacts" / "manifest.json"
    expected = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != 1 or not isinstance(manifest.get("files"), dict):
            raise ValueError("The artifact manifest is not in a known format.")
        if manifest.get("snapshot") != record.get("snapshot"):
            raise ValueError("The artifact manifest belongs to a different snapshot than result.json.")
        expected = manifest["files"]
    for relative, entry in sorted(expected.items()):
        path = run / "artifacts" / PurePosixPath(relative)
        item = {"path": relative, "status": "ok"}
        if path.is_symlink() or not path.is_file():
            item["status"] = "missing"
        else:
            data = path.read_bytes()
            if len(data) != entry.get("size") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                item["status"] = "changed"
        report["artifacts"].append(item)
    folder = run / "artifacts"
    if folder.is_dir():
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(folder).as_posix()
            if path.is_file() and relative != "manifest.json" and relative not in expected:
                report["unexpected"].append(relative)
    report["verified"] = (not report["interrupted"] and not report["unexpected"]
                          and all(item["status"] == "ok" for item in report["artifacts"]))
    return report


def accepted_root(repo):
    return Path(git(repo, "rev-parse", "--show-toplevel")) / ".awkit" / "accepted"


def accept(repo, run_dir, label="accepted"):
    """Keep a verified run's retained artifacts under .awkit/accepted/<label> for later comparison."""
    if not isinstance(label, str) or not LABEL.fullmatch(label):
        raise ValueError("A label uses letters, digits, dots, underscores and hyphens, up to 80 characters.")
    report = verify(run_dir)
    if not report["artifacts"]:
        raise ValueError("The run retained no artifacts; list them under `artifacts` in the check configuration.")
    if not report["verified"]:
        raise ValueError("The run's retained artifacts no longer match its manifest, so they cannot be accepted.")
    run = Path(run_dir).resolve()
    manifest = json.loads((run / "artifacts" / "manifest.json").read_text(encoding="utf-8"))
    root = accepted_root(repo)
    root.mkdir(parents=True, exist_ok=True)
    target = root / label
    staging = root / f".{label}.{os.getpid()}.tmp"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(run / "artifacts", staging)
    record = {"schema": 1, "label": label, "accepted_at": stamp(), "run_dir": str(run),
              "snapshot": manifest.get("snapshot"), "config_sha256": manifest.get("config_sha256"),
              "files": manifest["files"]}
    atomic_json(staging / "accepted.json", record)
    previous = root / f".{label}.previous"
    if previous.exists():
        shutil.rmtree(previous)
    if target.exists():
        target.rename(previous)
    staging.rename(target)
    if previous.exists():
        shutil.rmtree(previous)
    record["folder"] = str(target)
    return record


def _text_diff(before, after, relative):
    try:
        old_lines = before.decode("utf-8").splitlines(keepends=True)
        new_lines = after.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return None
    lines = list(difflib.unified_diff(old_lines, new_lines, f"accepted/{relative}", f"current/{relative}"))
    if len(lines) > 400:
        lines = lines[:400] + ["... (diff truncated)\n"]
    return "".join(lines)


def compare(repo, label="accepted", run_dir=None, diff=False):
    """Compare the working tree (or a run's retained artifacts) with the accepted version."""
    folder = accepted_root(repo) / label
    record_path = folder / "accepted.json"
    if not record_path.is_file():
        raise ValueError(f"No accepted version named {label!r}. Run `awkit review accept` first.")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if run_dir is not None:
        source = Path(run_dir).resolve() / "artifacts"
        if not source.is_dir():
            raise ValueError(f"The run folder has no retained artifacts: {run_dir}")
        origin = str(Path(run_dir).resolve())
    else:
        source = Path(git(repo, "rev-parse", "--show-toplevel"))
        origin = "working-tree"
    report = {"label": label, "accepted_at": record.get("accepted_at"), "accepted_snapshot": record.get("snapshot"),
              "compared": origin, "files": []}
    for relative, entry in sorted(record["files"].items()):
        rel = PurePosixPath(relative)
        accepted_file = folder / rel
        current = source / rel
        item = {"path": relative, "status": "same"}
        if current.is_symlink() or not current.is_file():
            item["status"] = "missing"
        else:
            data = current.read_bytes()
            if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                item["status"] = "changed"
                if diff and accepted_file.is_file():
                    item["diff"] = _text_diff(accepted_file.read_bytes(), data, relative)
        report["files"].append(item)
    report["unchanged"] = all(item["status"] == "same" for item in report["files"])
    return report


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
    patterns, required = artifact_patterns(settings)
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
    (run / "config.toml").write_bytes(raw)
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
        if patterns or required:
            files, missing, skipped = collect_artifacts(worktree, run, patterns, required)
            result["artifacts"] = files
            result["missing_artifacts"] = missing
            if skipped:
                result["skipped_artifacts"] = skipped
            manifest = {"schema": 1, "snapshot": commit, "config_sha256": result["config_sha256"],
                        "run_id": run.name, "files": files}
            atomic_json(run / "artifacts" / "manifest.json", manifest)
            if missing and result["status"] == "passed":
                result["status"] = "failed"
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
