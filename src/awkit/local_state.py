"""Protect project-managed state through verified, clone-local Git exclusions."""

import hashlib
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

# Local state must not enter a published source submission.
PREVENTS = {"awkit managed project state": ("F7", "F24")}
LOCK_SECONDS = 5


class ExclusionError(ValueError):
    """A managed writer cannot establish effective local exclusion."""


def _git(folder, *args):
    try:
        return subprocess.run(["git", "-C", str(folder), *args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", env={**os.environ, "LC_ALL": "C"})
    except OSError as exc:
        raise ExclusionError(f"Cannot inspect Git exclusion for {folder}: {exc}") from exc


def repository(project):
    project = Path(project).resolve()
    existing = project
    while not existing.exists():
        existing = existing.parent
    known = (bool(os.environ.get("GIT_DIR")) or
             any((parent / ".git").exists() or (parent / ".git").is_symlink()
                 for parent in (existing, *existing.parents)))
    try:
        result = _git(existing, "rev-parse", "--show-toplevel")
    except ExclusionError as exc:
        if not known and isinstance(exc.__cause__, FileNotFoundError):
            return None
        raise
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    if not known and "not a git repository" in result.stderr.lower():
        return None
    raise ExclusionError(f"Cannot resolve Git repository for {project}: {result.stderr.strip()}")


def exclude_file(top):
    result = _git(top, "rev-parse", "--git-path", "info/exclude")
    if result.returncode or not result.stdout.strip():
        raise ExclusionError(f"Cannot resolve Git info/exclude for {top}: {result.stderr.strip()}")
    path = Path(result.stdout.strip())
    return (path if path.is_absolute() else Path(top) / path).resolve()


def _ignored(top, target):
    result = _git(top, "check-ignore", "-q", "--no-index", "--", target)
    if result.returncode not in (0, 1):
        raise ExclusionError(f"Cannot verify Git exclusion for {target}: {result.stderr.strip()}")
    return result.returncode == 0


@contextmanager
def _locked(exclude):
    """Coordinate awkit append and restore; never steal a possibly live lock."""
    lock = exclude.with_name(exclude.name + ".awkit-lock")
    deadline = time.monotonic() + LOCK_SECONDS
    try:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise ExclusionError(f"Git exclusion is busy: {lock}. Retry after the owning writer finishes.") from None
                time.sleep(0.025)
    except OSError as exc:
        raise ExclusionError(f"Cannot coordinate Git exclusion at {exclude}: {exc}") from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def _sha(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def _pattern(relative, directory):
    if "\n" in relative or "\r" in relative:
        raise ExclusionError("Cannot represent this managed directory in a single Git exclusion rule.")
    escaped = "".join("\\" + char if char in "\\*?[!#" else char for char in relative)
    return "/" + escaped + ("/" if directory else "")


def _backup(top, requested, data):
    """Reserve a fresh original copy without overwriting an unrecorded backup."""
    path = requested
    try:
        requested.relative_to(top)
        git_root = repository(top)
        if git_root is not None:
            _untracked(git_root, requested.relative_to(git_root).as_posix())
        requested.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=requested.name + "-", dir=requested.parent)
        path = Path(name)
        with os.fdopen(fd, "wb") as stream:
            if git_root is not None:
                _untracked(git_root, path.relative_to(git_root).as_posix())
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ExclusionError(f"Cannot save fresh backup {path}: {exc}") from exc
    return path


def add_rule(top, relative, *, directory=False, backup=None, project=None):
    """Append without replacing existing bytes; optionally return an installer receipt."""
    top = Path(top).resolve()
    target = relative.rstrip("/") + ("/awkit-exclusion-probe" if directory else "")
    def protected():
        return _ignored(top, target) and (not directory or _ignored(top, relative.rstrip("/") + "/"))
    if protected():
        return None
    exclude = exclude_file(top)
    try:
        with _locked(exclude):
            if protected():
                return None
            before = exclude.read_bytes() if exclude.is_file() else None
            data = before or b""
            newline = b"\r\n" if b"\r\n" in data else b"\n"
            pattern = _pattern(relative.rstrip("/"), directory)
            line = pattern.encode("utf-8") + newline
            addition = (b"" if not data or data.endswith(b"\n") else newline) + line
            entry = {"pattern": pattern, "before": _sha(before), "after": _sha(data + addition), "line": line.hex()}
            if backup is not None and before is not None:
                base = Path(project) if project is not None else top
                requested = base / backup
                # Reserve a new file, including when an earlier unrecorded backup exists.
                # Save it before touching exclude; a failed reservation/write leaves exclude exact.
                try:
                    path = _backup(top, requested, before)
                except ExclusionError as exc:
                    raise ExclusionError(f"Git exclusion was not changed: {exc}") from exc
                entry["backup"] = path.relative_to(base).as_posix()
            with exclude.open("ab") as stream:
                stream.write(addition)
                stream.flush()
                os.fsync(stream.fileno())
            if not protected():
                # Undo a failed addition only when the captured bytes are still exact.
                # A non-cooperating editor's intervening content must survive.
                if exclude.read_bytes() == data + addition:
                    if before is None:
                        exclude.unlink()
                    else:
                        exclude.write_bytes(before)
                raise ExclusionError(f"Git does not ignore {target}; check higher-priority .gitignore negations. "
                                     "Managed state was not written.")
            return entry
    except OSError as exc:
        raise ExclusionError(f"Cannot protect managed state using {exclude}: {exc}") from exc


def _untracked(top, selected_relative, recursive=False):
    tracked = _git(top, "ls-files", "-z", "--", selected_relative)
    if tracked.returncode:
        raise ExclusionError(f"Cannot inspect tracked managed output {selected_relative}: {tracked.stderr.strip()}")
    if any(name and (recursive or os.path.normcase(name) == os.path.normcase(selected_relative))
           for name in tracked.stdout.split("\0")):
        raise ExclusionError(f"Managed output is already tracked by Git: {selected_relative}. "
                             "Its contents and index were not changed; select an untracked output or resolve tracking explicitly.")


def validate_output(project, output):
    """Check a setup-owned destination before adding its receipted exclusion."""
    top = repository(project)
    if top is not None:
        _untracked(top, Path(output).resolve().relative_to(top).as_posix())


def prepare(project, output=None, *, bypass=False, recursive=False):
    """Return protected/outside-git/bypassed/unmanaged before a selected managed write."""
    if bypass:
        return "bypassed"
    project = Path(project).resolve()
    managed = project / ".awkit"
    lexical = managed if output is None else Path(os.path.abspath(output))
    if lexical.is_relative_to(managed) and managed.resolve() != managed:
        raise ExclusionError(f"Managed state directory is redirected: {managed}. Select a project-local directory.")
    selected = managed if output is None else Path(output).resolve()
    if not selected.is_relative_to(managed):
        return "unmanaged"
    top = repository(project)
    if top is None:
        return "outside-git"
    selected_relative = selected.relative_to(top).as_posix()
    _untracked(top, selected_relative, recursive)
    relative = managed.relative_to(top).as_posix()
    add_rule(top, relative, directory=True)
    target = selected_relative
    if not _ignored(top, target + ("/" if selected == managed else "")):
        raise ExclusionError(f"Git does not ignore {target}; check .gitignore negations before writing managed state.")
    return "protected"


def restore(top, entry):
    """Undo only a recorded addition, coordinating with other awkit writers."""
    top = Path(top)
    exclude = exclude_file(top)
    with _locked(exclude):
        if not exclude.is_file():
            return
        backup = top / entry["backup"] if entry.get("backup") else None
        original = backup.read_bytes() if backup and backup.is_file() else None
        current = exclude.read_bytes()
        if _sha(current) == entry.get("after") and _sha(original) == entry.get("before"):
            if original is None:
                exclude.unlink()
            else:
                exclude.write_bytes(original)
            return
        lines = current.splitlines(keepends=True)
        pattern = entry.get("pattern", ".awkit/").encode("utf-8")
        own = bytes.fromhex(entry["line"]) if entry.get("line") else None
        matches = [i for i, line in enumerate(lines) if line == own or (own is None and line.strip() == pattern)]
        if len(matches) == 1:
            del lines[matches[0]]
            exclude.write_bytes(b"".join(lines))
