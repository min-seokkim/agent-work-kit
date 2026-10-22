"""Look at a project folder and report what an agent needs to connect the kit to it.

The scan reads file names and a few well-known manifests. Everything it reports is a
starting point for the project profile and the check configuration, not a verified fact:
the agent or the person confirms each command before relying on it.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import tomllib
from pathlib import Path

MANIFESTS = {
    "pyproject.toml": "python", "setup.py": "python", "requirements.txt": "python",
    "package.json": "javascript", "pnpm-lock.yaml": "javascript", "yarn.lock": "javascript",
    "tsconfig.json": "typescript", "go.mod": "go", "Cargo.toml": "rust", "pom.xml": "java",
    "build.gradle": "java", "build.gradle.kts": "kotlin", "Gemfile": "ruby", "composer.json": "php",
    "CMakeLists.txt": "c/c++", "Makefile": "make", "Dockerfile": "docker", "docker-compose.yml": "docker",
    "mkdocs.yml": "docs", "docusaurus.config.js": "docs", "conf.py": "docs", "book.toml": "docs",
}
RUN_LINE = re.compile(r"^\s*-?\s*run:\s*(.+?)\s*$")
# A CI step is offered as a check when it starts with one of these and needs no shell.
CHECK_TOOLS = {"pytest", "ruff", "mypy", "flake8", "black", "tox", "nox", "npm", "pnpm", "yarn", "npx", "go", "cargo",
               "make", "mvn", "gradle", "./gradlew", "dotnet", "bundle", "rake", "composer"}
CHECK_WORDS = {"test", "tests", "lint", "check", "typecheck", "build", "unittest", "pytest", "ruff", "mypy", "vet"}
SHELL = re.compile(r"[|&;<>$`*?(){}\\]")
MAKE_TARGET = re.compile(r"^([A-Za-z][A-Za-z0-9_.-]*):(?!=)")


def _git(folder):
    def run(*args):
        result = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        return result.stdout.strip() if result.returncode == 0 else None
    top = run("rev-parse", "--show-toplevel")
    if top is None:
        return {"repository": None}
    status = run("status", "--porcelain")
    return {"repository": top, "head": run("rev-parse", "--verify", "-q", "HEAD^{commit}"),
            "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "uncommitted_files": len(status.splitlines()) if status else 0,
            "remote": run("remote", "get-url", "origin")}


def _package_json(path, commands):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return
    for name in ("test", "lint", "build", "check", "typecheck", "e2e"):
        if name in scripts:
            commands.append({"name": name, "argv": ["npm", "run", name], "source": "package.json scripts",
                             "runs": str(scripts[name])})


def _pyproject(path, commands):
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    tool = data.get("tool", {}) if isinstance(data, dict) else {}
    # A tests folder alone does not say which runner the project uses; ask for an explicit sign.
    folder = path.parent
    if ("pytest" in tool or (folder / "pytest.ini").is_file() or (folder / "conftest.py").is_file()
            or (folder / "tests" / "conftest.py").is_file()):
        commands.append({"name": "tests", "argv": ["{python}", "-m", "pytest", "-q"], "source": "pytest configuration"})
    if "ruff" in tool:
        commands.append({"name": "lint", "argv": ["{python}", "-m", "ruff", "check", "."], "source": "pyproject.toml [tool.ruff]"})
    if "mypy" in tool:
        commands.append({"name": "types", "argv": ["{python}", "-m", "mypy", "."], "source": "pyproject.toml [tool.mypy]"})


def _makefile(path, commands):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    targets = [m.group(1) for line in lines if (m := MAKE_TARGET.match(line)) and not line.startswith("\t")]
    for name in ("test", "lint", "check", "build", "docs"):
        if name in targets:
            commands.append({"name": f"make-{name}", "argv": ["make", name], "source": "Makefile"})


def ci_checks(ci):
    """Turn CI run lines that call a test, lint or build tool without a shell into check commands."""
    found = []
    for workflow in ci:
        for line in workflow["run"]:
            if SHELL.search(line):
                continue
            try:
                argv = shlex.split(line)
            except ValueError:
                continue
            if not argv:
                continue
            head = argv[0].lower()
            if head in ("python", "python3", "py") and len(argv) > 2 and argv[1] == "-m":
                if argv[2] not in ("pytest", "unittest", "ruff", "mypy", "flake8", "black", "tox", "nox"):
                    continue
                argv = ["{python}", *argv[1:]]
            elif head not in CHECK_TOOLS or not CHECK_WORDS & {a.lower() for a in argv[1:]} | {head}:
                continue
            if head in ("npm", "pnpm", "yarn") and argv[1:2] in (["install"], ["ci"], ["i"]):
                continue
            words = [a for a in _key(argv) if not a.startswith("-")][:2]
            name = re.sub(r"[^a-z0-9]+", "-", " ".join(words).lower()).strip("-") or "ci"
            found.append({"name": name[:40], "argv": argv, "source": workflow["file"]})
    return found


def _key(argv):
    """The command without the interpreter prefix and verbosity flags, to spot the same check twice."""
    argv = list(argv)
    if argv[:2] == ["{python}", "-m"]:
        argv = argv[2:]
    if argv[:3] in (["npm", "run", "test"], ["pnpm", "run", "test"], ["yarn", "run", "test"]):
        argv = [argv[0], "test", *argv[3:]]  # `npm test` is `npm run test`
    return tuple(a for a in argv if a not in ("-v", "-q", "-vv", "--verbose", "--quiet"))


def _ci(folder):
    found = []
    for path in sorted((folder / ".github" / "workflows").glob("*.y*ml")):
        runs = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = RUN_LINE.match(line)
            if match and match.group(1) not in ("|", ">", "|-", ">-"):
                runs.append(match.group(1))
        found.append({"file": path.relative_to(folder).as_posix(), "run": runs[:20]})
    return found


def _kit(folder):
    kit = folder / "agent-work-kit"
    if not kit.is_dir():
        return {"present": False}
    profile = kit / "templates" / "project.md"
    filled = None
    if profile.is_file():
        text = profile.read_text(encoding="utf-8", errors="replace")
        start = text.split("## Start here", 1)[-1].split("##", 1)[0] if "## Start here" in text else ""
        fields = [line for line in start.splitlines() if line.startswith("- ")]
        # Template labels end with a colon; anything after the first colon is a value the user wrote.
        filled = sum(1 for line in fields if line.split(":", 1)[-1].strip())
        filled = {"start_here_fields": len(fields), "start_here_filled": filled}
    return {"present": True, "profile": str(profile) if profile.is_file() else None, **(filled or {})}


def suggested_checks(commands):
    lines = ["schema = 1", "timeout_seconds = 600", "",
             "# Suggested by `awkit kit scan` from the project's manifests. Confirm each command before relying on it.",
             "# List the files a passing run must produce under artifacts and required_artifacts.", "artifacts = []", ""]
    for command in commands:
        lines += ["[[checks]]", f'name = "{command["name"]}"', "argv = " + json.dumps(command["argv"]), ""]
    return "\n".join(lines)


def scan(folder):
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError(f"The folder does not exist: {folder}")
    manifests = sorted(name for name in MANIFESTS if (folder / name).is_file())
    languages = sorted({MANIFESTS[name] for name in manifests})
    commands = []
    if "package.json" in manifests:
        _package_json(folder / "package.json", commands)
    if "pyproject.toml" in manifests:
        _pyproject(folder / "pyproject.toml", commands)
    if "Makefile" in manifests:
        _makefile(folder / "Makefile", commands)
    if "go.mod" in manifests:
        commands.append({"name": "go-test", "argv": ["go", "test", "./..."], "source": "go.mod"})
    if "Cargo.toml" in manifests:
        commands.append({"name": "cargo-test", "argv": ["cargo", "test"], "source": "Cargo.toml"})
    ci = _ci(folder)
    # What CI already runs comes first; a manifest guess is dropped when CI runs the same argv.
    merged, seen = [], set()
    for command in ci_checks(ci) + commands:
        if _key(command["argv"]) not in seen:
            seen.add(_key(command["argv"]))
            merged.append(command)
    commands = merged
    names = set()
    for command in commands:
        base, number = command["name"], 2
        while command["name"] in names:
            command["name"], number = f"{base}-{number}", number + 1
        names.add(command["name"])
    docs = sorted(p.name for p in folder.iterdir() if p.is_dir() and p.name.lower() in ("docs", "doc", "documentation"))
    markdown = len([p for p in folder.glob("*.md")]) + sum(len(list((folder / d).rglob("*.md"))) for d in docs)
    return {
        "folder": str(folder), "git": _git(folder), "manifests": manifests, "languages": languages,
        "commands": commands, "ci": ci, "docs_folders": docs, "markdown_files": markdown,
        "kit": _kit(folder), "awkit_state": {"reviews": (folder / ".awkit" / "reviews").is_dir(),
                                             "accepted": (folder / ".awkit" / "accepted").is_dir()},
        "suggested_checks_toml": suggested_checks(commands),
        "note": "File names and manifests only; confirm every command before using it as evidence.",
    }
