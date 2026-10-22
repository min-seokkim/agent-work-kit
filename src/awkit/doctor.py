"""Check that this machine and project can run awkit, and say how to fix what is missing."""

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .identity import author_problem, configured
from .kit_install import SITUATIONS, SKILL_FOLDERS, read_version
from .review import nested_repositories

MIN_PYTHON = (3, 11)
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
                "awkit kit init creates one; the review commands need committed files")
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
                        "it was copied by an awkit before 0.3.0; compare it with awkit kit init --name agent-work-kit-new")
                elif recorded != __version__:
                    add("kit folder", "warning", f"{kit} was copied by awkit {recorded}; awkit {__version__} is installed",
                        "install the new kit beside it with awkit kit init --name agent-work-kit-new and compare")
                else:
                    add("kit folder", "ok", f"{kit} (awkit {recorded})")
                for provider, path in SKILL_FOLDERS.items():
                    present = sum((top / path / name / "SKILL.md").is_file() for name, *_ in SITUATIONS)
                    if present:
                        add(f"{provider} skills", "ok", f"{present} of {len(SITUATIONS)} in {top / path}")
            elif kit.exists():
                add("kit folder", "warning", f"{kit} has no workflow.md; it may be an older kit",
                    "install the new version beside it with awkit kit init --name agent-work-kit-new")
    return findings


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
