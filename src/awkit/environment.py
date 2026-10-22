"""Find what a project already has for its agents: instruction files, skills, hooks, memory and completion gates.

`kit scan` reports it, and `kit init`, `kit skills` and `kit hooks` read it before adding anything, so the
kit uses what the project has instead of saying the same thing a second time. Everything here only reads.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# Instruction files and the agent that reads each one at the start of every session.
INSTRUCTION_FILES = (
    ("CLAUDE.md", "claude"), (".claude/CLAUDE.md", "claude"), ("CLAUDE.local.md", "claude"),
    ("AGENTS.md", "codex"), ("AGENTS.override.md", "codex"),
    (".github/copilot-instructions.md", "copilot"), (".cursorrules", "cursor"), ("GEMINI.md", "gemini"),
)
SKILL_FOLDERS = {"claude": Path(".claude") / "skills", "codex": Path(".agents") / "skills"}
IMPORT = re.compile(r"^\s*@(\S+)\s*$", re.M)
# The marker awkit puts in every file it writes or block it appends, so `kit remove` and a later scan
# can find them without the record in .awkit/.
BEGIN, END = "<!-- awkit:begin -->", "<!-- awkit:end -->"
GENERATED = "<!-- awkit:generated"
# Method bundles that plan, review and delegate their own way. Signs: a plugin key, skill names, a folder.
SUPERPOWERS_SKILLS = {"brainstorming", "writing-plans", "executing-plans", "subagent-driven-development",
                      "dispatching-parallel-agents", "requesting-code-review", "receiving-code-review",
                      "test-driven-development", "systematic-debugging", "verification-before-completion",
                      "using-git-worktrees", "finishing-a-development-branch", "using-superpowers"}
BUNDLES = {"superpowers": "superpowers", "get-shit-done": "gsd"}
MEMORY = (("MEMORY.md", "memory file"), (".claude/MEMORY.md", "memory file"), (".beads", "Beads issue tracker"),
          (".planning", "planning folder"), ("docs/plans", "plan documents"))


def _read(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _json(path: Path):
    text = _read(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def words(text: str) -> int:
    return len(text.split())


def awkit_block(text: str):
    """The block awkit appended to an instruction file, markers included, or None."""
    start = text.find(BEGIN)
    if start < 0:
        return None
    end = text.find(END, start)
    return text[start:end + len(END)] if end >= 0 else text[start:]


def instructions(top: Path):
    """Instruction files with their reader, size, imports and the words awkit added to them."""
    found = []
    candidates = [(name, reader) for name, reader in INSTRUCTION_FILES]
    rules = top / ".cursor" / "rules"
    if rules.is_dir():
        candidates += [(p.relative_to(top).as_posix(), "cursor") for p in sorted(rules.rglob("*"))
                       if p.is_file() and p.suffix in (".md", ".mdc")]
    for name, reader in candidates:
        text = _read(top / name)
        if text is None:
            continue
        block = awkit_block(text)
        found.append({"path": name, "reader": reader, "words": words(text),
                      "imports": IMPORT.findall(text) if reader == "claude" else [],
                      "awkit_words": words(block) if block else 0})
    return found


def read_every_session(top: Path, reader: str, files=None):
    """The instruction files `reader` loads at the start of a session: its own files and, for Claude Code,
    the files they import with @path (one level, which covers `@AGENTS.md`)."""
    files = instructions(top) if files is None else files
    names = [f["path"] for f in files if f["reader"] == reader]
    for entry in [f for f in files if f["reader"] == reader]:
        for target in entry["imports"]:
            resolved = (top / Path(entry["path"]).parent / target).resolve()
            try:
                relative = resolved.relative_to(top.resolve()).as_posix()
            except ValueError:
                continue
            if relative not in names and resolved.is_file():
                names.append(relative)
    return names


def _front_matter(text):
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return {}
    head = text[4:].split("\n---", 1)[0]
    meta = {}
    for line in head.splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            value = value.strip()
            if value.startswith('"'):
                try:
                    value = json.loads(value)
                except ValueError:
                    pass
            meta[key.strip()] = value
    return meta


def is_awkit_skill(text):
    """A skill file awkit wrote: the generated marker, or the pointer body earlier versions wrote."""
    return GENERATED in text or "It is a situation guide of Agent Work Kit" in text


def skills(top: Path):
    """{provider: [{name, description, awkit}]} for the project's skill folders."""
    found = {}
    for provider, folder in SKILL_FOLDERS.items():
        entries = []
        root = top / folder
        if root.is_dir():
            for path in sorted(root.glob("*/SKILL.md")):
                text = _read(path) or ""
                meta = _front_matter(text)
                entries.append({"name": path.parent.name, "description": str(meta.get("description", "")),
                                "awkit": is_awkit_skill(text)})
        found[provider] = entries
    return found


def plugins(top: Path):
    """Plugin keys enabled in the project's Claude Code settings."""
    keys = []
    for name in ("settings.json", "settings.local.json"):
        data = _json(top / ".claude" / name) or {}
        enabled = data.get("enabledPlugins")
        if isinstance(enabled, dict):
            keys += [key for key, on in enabled.items() if on and key not in keys]
    return keys


def bundles(top: Path, found_skills=None, found_plugins=None):
    """Method bundles the project uses, each with the sign it was found by."""
    found_skills = skills(top) if found_skills is None else found_skills
    found_plugins = plugins(top) if found_plugins is None else found_plugins
    names = {entry["name"] for entries in found_skills.values() for entry in entries}
    result = []
    for bundle, prefix in BUNDLES.items():
        keys = [key for key in found_plugins if key.split("@")[0].lower().startswith(prefix)]
        if keys:
            result.append({"name": bundle, "evidence": f"plugin {keys[0]}"})
    if not any(b["name"] == "superpowers" for b in result):
        shared = sorted(names & SUPERPOWERS_SKILLS)
        if len(shared) >= 3 or any(name.startswith("superpowers") for name in names):
            result.append({"name": "superpowers", "evidence": "skills " + ", ".join(shared[:4])})
    if (top / ".specify").is_dir():
        result.append({"name": "spec-kit", "evidence": ".specify/"})
    return result


def _hook_commands(data):
    """{event: [command]} from a Claude Code or Codex hooks settings object."""
    hooks = data.get("hooks") if isinstance(data, dict) else None
    events = {}
    if not isinstance(hooks, dict):
        return events
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        commands = [str(hook.get("command", "")) for entry in entries if isinstance(entry, dict)
                    for hook in entry.get("hooks", []) if isinstance(hook, dict)]
        if commands:
            events[event] = commands
    return events


def _git(top, *args):
    result = subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    return result.stdout.strip() if result.returncode == 0 else None


def git_hooks(top: Path):
    """The hooks folder Git uses, the hook manager behind it and the hooks present."""
    path = _git(top, "rev-parse", "--git-path", "hooks")
    if path is None:
        return {"folder": None, "manager": None, "hooks": []}
    folder = Path(path) if Path(path).is_absolute() else top / path
    configured = _git(top, "config", "--get", "core.hooksPath")
    manager = None
    if (configured and ".husky" in configured) or (top / ".husky").is_dir():
        manager = "husky"
    elif (top / ".pre-commit-config.yaml").is_file():
        manager = "pre-commit"
    elif any((top / name).is_file() for name in ("lefthook.yml", "lefthook.yaml", ".lefthook.yml")):
        manager = "lefthook"
    present = sorted(p.name for p in folder.iterdir() if p.is_file() and not p.name.endswith(".sample")) \
        if folder.is_dir() else []
    try:
        shown = folder.resolve().relative_to(top.resolve()).as_posix()
    except ValueError:
        shown = str(folder)
    return {"folder": shown, "manager": manager, "hooks": present}


def hooks(top: Path):
    found = {"claude": [], "codex": []}
    for name in ("settings.json", "settings.local.json"):
        data = _json(top / ".claude" / name)
        if data is not None:
            found["claude"].append({"file": f".claude/{name}", "events": _hook_commands(data)})
    data = _json(top / ".codex" / "hooks.json")
    if data is not None:
        found["codex"].append({"file": ".codex/hooks.json", "events": _hook_commands(data)})
    found["git"] = git_hooks(top)
    return found


def auto_memory(top: Path):
    """Claude Code's automatic memory folder for this project, under the user's home folder."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(top.resolve()))
    return Path.home() / ".claude" / "projects" / slug / "memory"


def memory(top: Path):
    """Where the project keeps state and records already. Read only; awkit never writes there."""
    found = [{"path": name, "kind": kind} for name, kind in MEMORY if (top / name).exists()]
    folder = auto_memory(top)
    if folder.is_dir() and any(folder.iterdir()):
        found.append({"path": str(folder), "kind": "Claude Code automatic memory"})
    return found


def gates(top: Path, found_hooks=None, found_plugins=None, ci=None):
    """Completion gates that already stop an agent from finishing unchecked work: kkamak (gate.json),
    groundtruth (a Stop hook or its skill) and cngx (.cngx/ or `cngx verify` in CI or a hook)."""
    found_hooks = hooks(top) if found_hooks is None else found_hooks
    found_plugins = plugins(top) if found_plugins is None else found_plugins
    commands = [(entry["file"], command) for provider in ("claude", "codex") for entry in found_hooks[provider]
                for event_commands in entry["events"].values() for command in event_commands]
    user = _json(Path.home() / ".claude" / "settings.json")
    if user is not None:
        commands += [("~/.claude/settings.json", c) for cs in _hook_commands(user).values() for c in cs]
    result = []
    gate = _json(top / "gate.json")
    if gate is not None and "check" in gate:
        result.append({"name": "kkamak", "evidence": "gate.json"})
    elif any(key.split("@")[0] == "kkamak" for key in found_plugins):
        result.append({"name": "kkamak", "evidence": "plugin kkamak"})
    for file, command in commands:
        if "groundtruth" in command and not any(g["name"] == "groundtruth" for g in result):
            result.append({"name": "groundtruth", "evidence": f"hook in {file}"})
    for folder in (top / ".claude" / "skills" / "groundtruth", Path.home() / ".claude" / "skills" / "groundtruth"):
        if folder.is_dir() and not any(g["name"] == "groundtruth" for g in result):
            result.append({"name": "groundtruth", "evidence": str(folder)})
    if (top / ".cngx").is_dir():
        result.append({"name": "cngx", "evidence": ".cngx/"})
    else:
        runs = [(w["file"], line) for w in (ci or []) for line in w["run"]] + commands
        for file, line in runs:
            if re.search(r"\bcngx\s+(verify|gate|check)\b", line):
                result.append({"name": "cngx", "evidence": f"`cngx` in {file}"})
                break
    return result


def detect(top: Path, ci=None):
    """Everything above in one report."""
    top = Path(top)
    found_skills = skills(top)
    found_plugins = plugins(top)
    found_hooks = hooks(top)
    return {"instructions": instructions(top), "skills": found_skills, "plugins": found_plugins,
            "bundles": bundles(top, found_skills, found_plugins), "hooks": found_hooks, "memory": memory(top),
            "gates": gates(top, found_hooks, found_plugins, ci)}


def user_skills(home=None):
    """{provider: [{name, description, awkit}]} for the user's skill folders, which the agent reads in every
    project: `~/.claude/skills` and `~/.agents/skills`."""
    return skills(Path.home() if home is None else Path(home))


def session_words(top: Path, found=None, home=None):
    """Words awkit adds to every session, per agent: its block in the instruction files the agent loads
    (awkit before the three layers appended one) and the descriptions of its skills in the project and the
    user folder, which agents keep in context to decide when to load a skill. A skill in both counts once."""
    top = Path(top)
    found = detect(top) if found is None else found
    by_path = {f["path"]: f for f in found["instructions"]}
    users = user_skills(home)
    result = {}
    for reader in SKILL_FOLDERS:
        loaded = read_every_session(top, reader, found["instructions"])
        block = 0
        for name in loaded:
            entry = by_path.get(name)
            if entry is None:
                text = _read(top / name) or ""
                found_block = awkit_block(text)
                block += words(found_block) if found_block else 0
            else:
                block += entry["awkit_words"]
        mine = {s["name"]: s["description"] for s in users[reader] if s["awkit"]}
        mine.update({s["name"]: s["description"] for s in found["skills"][reader] if s["awkit"]})
        result[reader] = block + sum(words(description) for description in mine.values())
    return result
