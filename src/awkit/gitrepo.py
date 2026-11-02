"""Git primitives the review, check and connect commands share: running git, finding the repository top,
nested repositories and the folder a command runs in."""

import subprocess
from pathlib import Path


def git(repo, *args, env=None):
    result = subprocess.run(["git", "-C", str(repo), *args], env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git command failed.")
    return result.stdout.strip()


IDENTITY = ("-c", "user.name=Agent Work Kit", "-c", "user.email=awkit@localhost")


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
