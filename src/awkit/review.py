"""Freeze explicitly selected changes and check a fixed Git object in isolation."""

import difflib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from .process import run_to_files
from .records import LABEL, atomic_json, stamp


def git(repo, *args, env=None):
    result = subprocess.run(["git", "-C", str(repo), *args], env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git command failed.")
    return result.stdout.strip()


IDENTITY = ("-c", "user.name=Agent Work Kit", "-c", "user.email=awkit@localhost")

# The failure catalogue entries (kit/failures.md) each command guards against.
PREVENTS = {"awkit review snapshot": ("F17",), "awkit review check": ("F2", "F17"),
            "awkit review accept": ("F16",), "awkit review compare": ("F16",),
            "awkit kit init and kit example (commit only the new folder)": ("F8", "F9")}


def _probe(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def toplevel(folder):
    """The Git top level that contains `folder`, which must already have a commit.

    The review commands only read and check files that Git tracks; they never create a
    repository or commit on their own.
    """
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError(f"The folder does not exist: {folder}")
    probe = _probe(folder, "rev-parse", "--show-toplevel")
    if probe.returncode:
        raise ValueError(f"Not a Git repository: {folder}. awkit checks files that Git tracks: run `git init` "
                         "and commit them, or start from `awkit kit init` or `awkit kit example`.")
    top = Path(probe.stdout.strip())
    if _probe(top, "rev-parse", "--verify", "-q", "HEAD^{commit}").returncode:
        raise ValueError(f"The repository has no commit yet: {top}. Commit the files before checking them.")
    return top


def nested_repositories(top):
    """Untracked folders in the repository that are Git repositories of their own, such as a clone of
    awkit placed inside the project. awkit does not support them: a snapshot cannot hold a folder, so
    changes there can never be checked. Ignored folders and submodules are not listed."""
    top = Path(top)
    probe = _probe(top, "ls-files", "--others", "--exclude-standard", "-z")
    found = []
    for entry in probe.stdout.split("\0"):
        # Git does not descend into another repository; it lists it as one "path/" entry.
        if entry.endswith("/") and (top / entry / ".git").exists():
            path = entry.rstrip("/")
            found.append({"path": path, "awkit": (top / path / "src" / "awkit" / "__init__.py").is_file()})
    return found


def nested_warning(entry):
    what = "a clone of awkit" if entry["awkit"] else "a separate Git repository"
    return (f"{entry['path']} is {what} inside this project. awkit does not support that: changes in it can "
            "never be checked, and `git add -A` would add it as an embedded repository. Move it outside the "
            "project, or add it to .gitignore.")


def located(folder):
    """The repository top level and the folder's path inside it, "" at the root.

    Review commands take paths, step working directories and artifact patterns relative to the
    folder they are run in, and resolve them inside the same subfolder of the checked worktree.
    """
    top = toplevel(folder)
    inside = Path(folder).resolve().relative_to(top.resolve())
    return top, inside.as_posix() if inside.parts else ""


def track(folder, paths, message):
    """Commit `paths` under `folder` with Git, creating the repository when `folder` is not in one.

    Only the named paths are added. In a repository with no commits by anyone but awkit, the commit is made
    under awkit's own identity; in one with history, under the configured identity when it fits the history (see
    `identity.author_problem`), and otherwise not at all. A repository that awkit creates gets `core.autocrlf=false`
    so the bytes it checks out are the bytes that were committed. Nothing is committed when the
    index already holds staged changes, so a kit commit never bundles the user's own work.
    Returns a record with the repository, whether it was created, whether a commit was made and,
    if not, why.
    """
    folder = Path(folder).resolve()
    probe = _probe(folder, "rev-parse", "--show-toplevel")
    created = bool(probe.returncode)
    if created:
        git(folder, "init", "-q")
        git(folder, "config", "core.autocrlf", "false")
        top = folder
    else:
        top = Path(probe.stdout.strip())
    record = {"repository": str(top), "created": created, "committed": False, "skipped": None}
    if _probe(top, "diff", "--cached", "--quiet").returncode:
        record["skipped"] = "the index already has staged changes"
        return record
    from .identity import author_problem, configured, history_authors
    has_commit = not _probe(top, "rev-parse", "--verify", "-q", "HEAD^{commit}").returncode
    identity = IDENTITY
    # Commits only awkit has made are not anyone's history; awkit keeps committing under its own name.
    if has_commit and history_authors(top)[0]:
        # In a repository with history the kit is committed as the person it belongs to, never as an
        # agent and never under awkit's own name; when that is not possible the user commits it.
        author = configured(top)
        problem = author_problem(top, *author) if author else "no Git identity is configured"
        if problem:
            record["skipped"] = problem
            return record
        identity = ()
    relative = [Path(p).resolve().relative_to(top).as_posix() for p in paths]
    git(top, "-c", "core.autocrlf=false", "add", "-A", "--", *relative)
    if not _probe(top, "diff", "--cached", "--quiet").returncode:
        record["skipped"] = "nothing to commit"
        return record
    git(top, *identity, "commit", "-q", "-m", message)
    record["committed"] = True
    return record


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
    repo, subdir = located(repo)
    base = repo / subdir
    parent = git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    if not paths:
        raise ValueError("Name the changed files to include.")
    specs = []
    for name in paths:
        rel = relative_file(name)
        target = base / rel
        if target.is_dir() or any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
                                  for p in [target, *target.parents] if p != repo.parent):
            raise ValueError(f"Directories and links cannot be included: {name}")
        if not target.resolve().is_relative_to(repo.resolve()):
            raise ValueError("The file is outside the repository.")
        spec = (PurePosixPath(subdir) / rel).as_posix()
        # A deleted file counts when HEAD or the index has it; `git rm` and `git mv` remove it from both
        # the working tree and the index, so HEAD is the one that still knows it.
        if (not target.exists() and _probe(repo, "ls-files", "--error-unmatch", "--", spec).returncode
                and not git(repo, "ls-tree", "--name-only", parent, "--", spec)):
            raise ValueError(f"File not found: {name}")
        specs.append(spec)
    with tempfile.TemporaryDirectory(prefix="awkit-index-") as temporary:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        env["GIT_LITERAL_PATHSPECS"] = "1"
        env.update(GIT_AUTHOR_NAME="Agent Work Kit", GIT_AUTHOR_EMAIL="snapshot@localhost",
                   GIT_COMMITTER_NAME="Agent Work Kit", GIT_COMMITTER_EMAIL="snapshot@localhost")
        git(repo, "read-tree", parent, env=env)
        git(repo, "add", "-A", "--", *specs, env=env)
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


def exclude_locally(top, pattern):
    """Keep `pattern` out of Git through .git/info/exclude unless something ignores it already.

    The exclude file stays on this machine, so the user's .gitignore and history are untouched. A
    pattern ending in "/" is a folder."""
    probe = pattern + "x" if pattern.endswith("/") else pattern
    if not _probe(top, "check-ignore", "-q", "--no-index", probe).returncode:
        return
    exclude = Path(git(top, "rev-parse", "--git-path", "info/exclude"))
    exclude = exclude if exclude.is_absolute() else Path(top) / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    # Bytes, so the file keeps its own line endings: text mode would rewrite every line with CRLF on Windows.
    data = exclude.read_bytes() if exclude.is_file() else b""
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    exclude.write_bytes(data + (b"" if not data or data.endswith(b"\n") else newline) + pattern.encode("utf-8") + newline)


def accepted_root(repo):
    return toplevel(repo) / ".awkit" / "accepted"


@contextmanager
def _accept_lock(root):
    """One accept at a time per repository, like the release runner's state lock.

    The lock file sits next to the accepted folder so that folder holds only labels."""
    conn = sqlite3.connect(root.parent / "accept.lock.sqlite3", timeout=0)
    try:
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise ValueError("Another accept is running in this repository. Try again when it finishes.") from exc
        yield
    finally:
        conn.rollback()
        conn.close()


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
    record = {"schema": 1, "label": label, "accepted_at": stamp(), "run_dir": str(run),
              "snapshot": manifest.get("snapshot"), "config_sha256": manifest.get("config_sha256"),
              "subdir": manifest.get("subdir", ""), "files": manifest["files"]}
    with _accept_lock(root):
        staging = root / f".{label}.{os.getpid()}.tmp"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(run / "artifacts", staging)
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
        source = toplevel(repo) / record.get("subdir", "")
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
    if run_dir is None and any(item["status"] == "missing" for item in report["files"]):
        report["note"] = ("A file the check produced exists only in the worktree it ran in, not in the working "
                          "tree. To compare the outputs of a later run, pass its run folder with --run.")
    return report


def check(repo, revision, config, runs_root=None, keep=False):
    if revision != "HEAD" and not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", revision):
        raise ValueError("Give the full ID of the Git commit to check, or HEAD.")
    repo, subdir = located(repo)
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
    if runs_root is None:
        # Run records belong to the project they checked; .awkit is excluded from Git locally.
        exclude_locally(repo, ".awkit/")
        runs_root = repo / ".awkit" / "reviews"
    root = Path(runs_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="review-", dir=root))
    worktree = run / "worktree"
    base = worktree / subdir
    result = {"snapshot": commit, "config_sha256": hashlib.sha256(raw).hexdigest(), "subdir": subdir,
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
            step_dir = base / relative_directory(step.get("cwd", "."))
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
            files, missing, skipped = collect_artifacts(base, run, patterns, required)
            result["artifacts"] = files
            result["missing_artifacts"] = missing
            if skipped:
                result["skipped_artifacts"] = skipped
            manifest = {"schema": 1, "snapshot": commit, "config_sha256": result["config_sha256"],
                        "subdir": subdir, "run_id": run.name, "files": files}
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
