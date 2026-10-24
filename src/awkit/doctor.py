"""Check that this machine and project can run awkit, and say how to fix what is missing."""

import json
import platform
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from importlib import metadata
from pathlib import Path

from . import __version__
from .identity import author_problem, configured
from .kit_install import SKILL_FOLDERS, read_version
from .review import nested_repositories, validate_settings

MIN_PYTHON = (3, 11)

# The failure catalogue entries (kit/failures.md) this command guards against: an agent's commit
# identity, readiness inferred without usable checks (F11), a kit or skills made by another awkit version
# (F25), and guides or hooks that a session never loads, including consumed stale project kit paths (F29).
PREVENTS = {"awkit doctor": ("F9", "F11", "F25", "F29")}
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


def runtime_origin():
    """Identify the loaded code, without attributing another installation's metadata to it."""
    module = Path(__file__).resolve()
    checkout = module.parents[2]
    if module == checkout / "src" / "awkit" / "doctor.py" and (checkout / "pyproject.toml").is_file():
        top = _git(checkout, "rev-parse", "--show-toplevel")
        if top and Path(top).resolve() == checkout:
            revision = _git(checkout, "rev-parse", "--verify", "HEAD")
            if revision:
                try:
                    status = subprocess.run(["git", "status", "--porcelain", "--", "src/awkit", "kit", "pyproject.toml"],
                                            cwd=checkout, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    state = "unknown" if status.returncode else "modified" if status.stdout else "clean"
                except OSError:
                    state = "unknown"
                return f"checkout HEAD {revision}; source and kit worktree {state}"
        return "source checkout; commit unavailable"
    try:
        dist = metadata.distribution("agent-work-kit")
        if Path(dist.locate_file("awkit/doctor.py")).resolve() != module:
            return "installation commit unavailable; distribution metadata belongs to other code"
        raw = dist.read_text("direct_url.json")
        if not raw:
            return "installation commit unavailable; no direct URL metadata"
        origin = json.loads(raw)
        vcs = origin.get("vcs_info", {}) if isinstance(origin, dict) else {}
        revision = vcs.get("commit_id") if isinstance(vcs, dict) else None
        if isinstance(revision, str) and re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", revision):
            return f"installation commit {revision} (metadata; installed files not compared)"
        return "installation commit unavailable; metadata records no full commit ID"
    except (metadata.PackageNotFoundError, OSError, ValueError, TypeError):
        return "installation commit unavailable; metadata missing or unreadable"


def _checks(top, add):
    path = top / "checks.toml"
    if not path.exists():
        return
    try:
        settings = tomllib.loads(path.read_text(encoding="utf-8"))
        validate_settings(settings)
    except (OSError, ValueError) as exc:
        add("project checks", "warning", f"{path}: {exc}",
            "configure at least one real project check in checks.toml, then run awkit review check HEAD --config checks.toml")
    else:
        add("project checks", "ok", f"{len(settings['checks'])} configured check(s); configuration valid, execution unverified")


def _rules(top, add):
    """Validate project rules without evaluation; inspect only a kit directory the rules can consume."""
    from .hooks import CAN_BLOCK, _rules_from_data

    path = top / "rules.toml"
    repair = "correct the reported rules.toml error while preserving custom rules and comments, then rerun awkit doctor"

    def warning(stage, detail):
        add("project rules", "warning", f"{path}: {stage}: {detail}; kit directory unverified", repair)

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except UnicodeDecodeError as exc:
        warning("decode error", str(exc))
        return
    except OSError as exc:
        warning("read error", str(exc))
        return
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        warning("TOML error", str(exc))
        return
    try:
        rules, problems = _rules_from_data(data, path)
    except ValueError as exc:
        warning("schema error" if data.get("schema") != 1 else "configuration error", str(exc))
        return
    if problems:
        warning("rule validation error", "; ".join(problems))
        return
    add("project rules", "ok", f"{len(rules)} valid rule(s); execution unverified")
    consumed = False
    for raw, rule in zip(data.get("rules", []), rules, strict=True):
        command = raw.get("command", [])
        strings = [raw.get("message", ""), *([command] if isinstance(command, str) else command)]
        explicit = any("{kit}" in value for value in strings)
        citation = rule.kind != "inject" and rule.prevents and any(event in CAN_BLOCK for event in rule.events)
        consumed = consumed or explicit or bool(citation)
    if not consumed:
        return
    configured_kit = data.get("kit", "agent-work-kit")
    kit = Path(configured_kit)
    if not kit.is_absolute():
        kit = top / kit
    hint = ("inspect the intended guide source, then correct only kit in rules.toml to an existing project-relative "
            "or absolute directory; preserve custom rules/comments and rerun awkit doctor. Reinstalling awkit "
            "does not repair preserved project rules")
    try:
        mode = kit.stat().st_mode
    except FileNotFoundError:
        add("rules kit directory", "warning", f"{kit}: consumed kit directory does not exist", hint)
    except NotADirectoryError:
        add("rules kit directory", "warning", f"{kit}: consumed kit path has a non-directory component", hint)
    except (OSError, ValueError) as exc:
        add("rules kit directory", "warning", f"{kit}: directory inspection unavailable ({type(exc).__name__})", hint)
    else:
        if not stat.S_ISDIR(mode):
            add("rules kit directory", "warning", f"{kit}: consumed kit value is not a directory", hint)
        else:
            add("rules kit directory", "ok", f"{kit}: directory exists; individual guides, freshness and client loading unverified")


def diagnose(folder="."):
    """A list of findings: {item, status ("ok", "missing", "warning"), detail, fix}."""
    folder = Path(folder).resolve()
    findings = []

    def add(item, status, detail, fix=""):
        findings.append({"item": item, "status": status, "detail": detail, "fix": fix})

    version = sys.version_info[:3]
    add("python", "ok" if version >= MIN_PYTHON else "missing", ".".join(map(str, version)) + f" at {sys.executable}",
        "" if version >= MIN_PYTHON else _install_hint("python"))
    add("awkit runtime", "ok", f"{__version__} at {Path(__file__).resolve().parent}")
    add("awkit source", "ok", runtime_origin())

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
            "run pipx ensurepath, then restart the terminal and the app that runs hooks")
    else:
        add("awkit on PATH", "ok", shutil.which("awkit"))

    checks_folder = folder
    if folder.is_dir() and shutil.which("git") is not None:
        top = _git(folder, "rev-parse", "--show-toplevel")
        if not top:
            add("project repository", "warning", f"{folder} is not in a Git repository",
                "run git init and commit the files; the review commands need committed files")
        else:
            top = Path(top)
            checks_folder = top
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
    _checks(checks_folder, add)
    _rules(checks_folder, add)
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
    warnings = sum(f["status"] == "warning" for f in findings)
    if missing:
        lines.append(f"{missing} required item(s) missing")
    elif warnings:
        lines.append(f"required tools available; review {warnings} warning(s) above")
    else:
        lines.append("required tools available; check results and automatic hook execution not verified")
    return "\n".join(lines)
