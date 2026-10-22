"""Check that this machine and project can run awkit, and say how to fix what is missing."""

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .identity import author_problem, configured
from .kit_install import SKILL_FOLDERS, read_version
from .review import nested_repositories

MIN_PYTHON = (3, 11)

# The failure catalogue entries (kit/failures.md) this command guards against: an agent's commit
# identity, a kit or skills made by another awkit version (F25), and guides or hooks that a session never
# loads, so the way of working does not reach it (F29).
PREVENTS = {"awkit doctor": ("F9", "F25", "F29")}
MIN_GIT = (2, 25)


def _git(folder, *args):
    try:
        result = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8",
                                errors="replace")
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else ""


def _install_hint(tool):
    system = platform.system()
    if tool == "git":
        return {"Windows": "winget install --id Git.Git -e, then open a new terminal",
                "Darwin": "brew install git, or xcode-select --install"}.get(
            system, "install git with the package manager, for example sudo apt install git")
    return {"Windows": "winget install --id Python.Python.3.12 -e, then open a new terminal",
            "Darwin": "brew install python@3.12"}.get(
        system, "install Python 3.11 or later with the package manager, for example sudo apt install python3")


def diagnose(folder="."):
    """A list of findings: {item, status ("ok", "missing", "warning"), detail, fix}."""
    folder = Path(folder).resolve()
    findings = []

    def add(item, status, detail, fix=""):
        findings.append({"item": item, "status": status, "detail": detail, "fix": fix})

    version = sys.version_info[:3]
    add("python", "ok" if version >= MIN_PYTHON else "missing", ".".join(map(str, version)) + f" at {sys.executable}",
        "" if version >= MIN_PYTHON else _install_hint("python"))

    if shutil.which("git") is None:
        add("git", "missing", "git was not found on PATH", _install_hint("git"))
    else:
        text = _git(folder if folder.is_dir() else None, "--version") or ""
        match = re.search(r"(\d+)\.(\d+)", text)
        found = tuple(int(part) for part in match.groups()) if match else (0, 0)
        add("git", "ok" if found >= MIN_GIT else "missing", text or "git --version failed",
            "" if found >= MIN_GIT else "update Git: " + _install_hint("git"))
        where = folder if folder.is_dir() else None
        for key, example in (("user.name", '"Your Name"'), ("user.email", "you@example.com")):
            value = _git(where, "config", "--get", key)
            add(f"git {key}", "ok" if value else "missing", value or "not set",
                "" if value else f"git config --global {key} {example}  (commits fail without it)")

    if shutil.which("awkit") is None:
        add("awkit on PATH", "warning", "the awkit command was not found on PATH",
            "run pipx ensurepath and open a new terminal")
    else:
        add("awkit on PATH", "ok", shutil.which("awkit"))

    if folder.is_dir() and shutil.which("git") is not None:
        top = _git(folder, "rev-parse", "--show-toplevel")
        if not top:
            add("project repository", "warning", f"{folder} is not in a Git repository",
                "run git init and commit the files; the review commands need committed files")
        else:
            top = Path(top)
            has_commit = bool(_git(top, "rev-parse", "--verify", "-q", "HEAD"))
            add("project repository", "ok" if has_commit else "warning", str(top),
                "" if has_commit else "commit the files before awkit review check")
            author = configured(top)
            problem = author_problem(top, *author, "HEAD" if has_commit else None) if author else None
            if problem:
                add("commit identity", "warning", problem.split(". Commit as")[0],
                    "git config user.name and user.email as the person the repository belongs to")
            for entry in nested_repositories(top):
                what = "a clone of awkit" if entry["awkit"] else "a separate Git repository"
                add("nested repository", "warning", f"{entry['path']} is {what}; awkit cannot check changes in it",
                    f"move {entry['path']} outside the project, or add {entry['path']}/ to .gitignore")
            kit = folder / "agent-work-kit"
            if (kit / "workflow.md").is_file():
                recorded = read_version(kit).get("awkit")
                if recorded is None:
                    add("kit folder", "warning", f"{kit} records no version",
                        "it was copied by an awkit before 0.3.0; compare it with awkit kit init --copy --name agent-work-kit-new")
                elif recorded != __version__:
                    add("kit folder", "warning", f"{kit} was copied by awkit {recorded}; awkit {__version__} is installed",
                        "install the new kit beside it with awkit kit init --copy --name agent-work-kit-new and compare")
                else:
                    add("kit folder", "ok", f"{kit} (awkit {recorded})")
                _skills(top, add)
            elif kit.exists():
                add("kit folder", "warning", f"{kit} has no workflow.md; it may be an older kit",
                    "install the new version beside it with awkit kit init --copy --name agent-work-kit-new")
            else:
                _skills(top, add)
            _layers(top, add)
    return findings


def _layers(top, add):
    """The three layers: the skills in the user folder and the awkit that made them, the hooks a project with
    checks.toml needs, the version in its [kit] table, and a kit folder copied before the guides moved to the
    user folder."""
    from .connect import CHECKS, kit_table, user_skills
    from .environment import hooks, skills
    from .kit_install import user_skill_folders
    folders, mine, project = user_skill_folders(), user_skills(), skills(top)
    for provider, found in mine.items():
        older = sorted({version or "an unknown version" for _, version in found if version != __version__})
        if older:
            add(f"{provider} user skills", "warning", f"{len(found)} awkit skills in {folders[provider]}, made by awkit "
                + ", ".join(older), "awkit kit skills  (regenerates them for the installed awkit)")
        elif found:
            add(f"{provider} user skills", "ok", f"{len(found)} awkit skills in {folders[provider]}")
        elif not any(s["awkit"] for s in project[provider]):
            add(f"{provider} user skills", "warning", f"no awkit skills in {folders[provider]}, so sessions never "
                "load the guides", "awkit kit skills")
    table = kit_table(top / CHECKS)
    if table is None:
        pass
    elif "version" in table and table["version"] != __version__:
        add("kit version", "warning", f"[kit] in {CHECKS} says awkit {table['version']}; awkit {__version__} is installed",
            f'set version = "{__version__}" in [kit] once the project works with it, or install awkit {table["version"]}')
    elif "version" in table:
        add("kit version", "ok", f"[kit] in {CHECKS} matches awkit {__version__}")
    if table is not None:
        found = hooks(top)
        commands = [c for provider in ("claude", "codex") for entry in found[provider]
                    for cs in entry["events"].values() for c in cs]
        if not any(c.strip().startswith("awkit") for c in commands):
            add("hooks", "warning", f"{CHECKS} is here but no Claude Code or Codex hook runs awkit, so its checks run "
                "only when the agent chooses to", "awkit kit hooks --git --claude --codex  (or awkit kit init)")
    copied = top / "agent-work-kit"
    if (copied / "workflow.md").is_file():
        where = "the skills in your user folder hold the guides now" if any(mine.values()) else \
            "awkit kit skills puts the guides in your user folder"
        add("copied kit folder", "warning", f"{copied} is a copy of the guides an earlier awkit made; {where}",
            "move any profile or task records you wrote there into the project's own records, then delete the folder")


def _skills(top, add):
    from .environment import skills
    for provider, found in skills(top).items():
        mine = [s["name"] for s in found if s["awkit"]]
        if mine:
            add(f"{provider} skills", "ok", f"{len(mine)} awkit skills in {top / SKILL_FOLDERS[provider]}")


def render(findings):
    width = max(len(f["item"]) for f in findings)
    lines = []
    for finding in findings:
        line = f"{finding['status']:<8} {finding['item']:<{width}}  {finding['detail']}"
        if finding["fix"]:
            line += f"\n{'':<8} {'':<{width}}  fix: {finding['fix']}"
        lines.append(line)
    missing = sum(f["status"] == "missing" for f in findings)
    lines.append("ready" if not missing else f"{missing} required item(s) missing")
    return "\n".join(lines)
