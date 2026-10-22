"""Connect the kit to a project without copying it, record what was added, and take it out again.

`kit init` reads what the project has (environment.py) and adds three things: a short section at the end
of the instruction file agents already read, self-contained skills, and `.awkit/installed.json`, the
record of every file it wrote. `kit skills` and `kit hooks` add to the same record. `kit remove` reads it
and restores each file: byte for byte when the file is as awkit left it, otherwise by taking out only
awkit's own block, entries or line. awkit writes nowhere else in the project; memory files are read only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from . import environment
from .environment import BEGIN, END, GENERATED, awkit_block, words

RECORD = Path(".awkit") / "installed.json"
BACKUP = Path(".awkit") / "backup"
# Records worth keeping when the kit is removed: check runs, accepted versions, the review channel and
# the hook log. The rest of .awkit/ is state that means nothing without the kit.
RECORDS = ("reviews", "accepted", "channel.sqlite3", "hooks.ndjson")
CLAUDE_IMPORT = f"{BEGIN}\n@AGENTS.md\n{END}\n"
FIELDS = ("Desired result", "Source material and its version", "Files to change and conditions to preserve",
          "How completion is checked", "Where results and records go")

# The failure catalogue entries (kit/failures.md) these commands guard against: kit text that never reaches
# a later session or duplicates where the project keeps its state (F29), always-on text added before
# anything shows it is needed (F12), and the project's own files and settings changed beyond what was
# asked (F7).
PREVENTS = {"awkit kit init": ("F7", "F12", "F29"), "awkit kit remove": ("F7",)}


def read_exact(path):
    """A file's text with its line endings and any undecodable bytes kept, so writing it back changes
    nothing awkit did not mean to change."""
    return Path(path).read_bytes().decode("utf-8", errors="surrogateescape")


def write_exact(path, text):
    Path(path).write_bytes(text.encode("utf-8", errors="surrogateescape"))


def _newlines(text, like):
    return text.replace("\n", "\r\n") if "\r\n" in like else text


def sha(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def _git(top, *args):
    return subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def project_top(folder):
    """The repository's top folder, or the folder itself outside a repository."""
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError(f"The folder does not exist: {folder}")
    probe = _git(folder, "rev-parse", "--show-toplevel")
    return Path(probe.stdout.strip()).resolve() if probe.returncode == 0 else folder


class Changes:
    """Writes files and records each one in .awkit/installed.json: what it held before, what awkit wrote,
    and a backup of the original so `kit remove` can restore it exactly."""

    def __init__(self, top, exclude=True):
        self.top = Path(top).resolve()
        # A record in a project keeps .awkit/ out of Git; one in the home folder leaves Git alone.
        self.exclude = exclude
        self.path = self.top / RECORD
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.data.get("files"), dict):
                raise ValueError
        except (OSError, ValueError, AttributeError):
            self.data = {"schema": 1, "files": {}, "dirs": []}
        self.changed = []

    def key(self, path):
        path = Path(path).absolute()
        try:
            return path.relative_to(self.top).as_posix()
        except ValueError:
            return str(path)

    def resolve(self, key):
        path = Path(key)
        return path if path.is_absolute() else self.top / path

    def write(self, path, text, action, **extra):
        """Write `text` to `path` unless it holds it already. Returns True when the file changed."""
        path = Path(path).absolute()
        data = text.encode("utf-8", errors="surrogateescape")
        before = path.read_bytes() if path.is_file() else None
        if before == data:
            return False
        key = self.key(path)
        entry = self.data["files"].get(key)
        if entry is None:
            entry = {"action": action, "before": sha(before), **extra}
            if before is not None:
                backup = self.top / BACKUP / key.replace(":", "_").lstrip("/")
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(before)
                entry["backup"] = backup.relative_to(self.top).as_posix()
            self.data["files"][key] = entry
        missing, parent = [], path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for folder in reversed(missing):
            folder.mkdir()
            self.data["dirs"].append(self.key(folder))
        path.write_bytes(data)
        entry["after"] = sha(data)
        self.changed.append(path)
        return True

    def save(self):
        if not self.changed:
            return None
        from .kit_install import kit_source
        self.data.update(kit_source())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.exclude and (self.top / ".git").exists():
            exclude = _exclude_file(self.top)
            before = exclude.read_text(encoding="utf-8") if exclude and exclude.is_file() else ""
            from .review import exclude_locally
            exclude_locally(self.top, ".awkit/")
            after = exclude.read_text(encoding="utf-8") if exclude and exclude.is_file() else ""
            if after != before:
                self.data["excluded"] = True
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        return self.path


def _exclude_file(top):
    probe = _git(top, "rev-parse", "--git-path", "info/exclude")
    if probe.returncode:
        return None
    path = Path(probe.stdout.strip())
    return path if path.is_absolute() else top / path


# Planning: what init adds, decided from what the project has.


def _profile(found, ci):
    checked = ""
    if found["gates"]:
        checked = ", ".join(f"{g['name']} ({g['evidence']})" for g in found["gates"])
    elif ci:
        checked = "the checks in " + ", ".join(f"`{w['file']}`" for w in ci)
    records = ", ".join(f"`{m['path']}`" for m in found["memory"] if not Path(m["path"]).is_absolute())
    return {"How completion is checked": checked, "Where results and records go": records}


def block_text(found, ci=None):
    """The section appended to the instruction file: that the kit is here, where to look, and the project
    profile as pointers to what the project already keeps."""
    if found["bundles"]:
        bundle = found["bundles"][0]["name"]
        lead = (f"Plan, review and delegate with {bundle}. For checks and reports, follow the `awkit-workflow` "
                "skill; the other `awkit-*` skills load by situation.")
    else:
        lead = "Follow the `awkit-workflow` skill for each task; the other `awkit-*` skills load by situation."
    values = _profile(found, ci or [])
    lines = [BEGIN, "## Agent Work Kit", "", lead, "",
             "Project profile: point to where things are kept rather than copying them, and fill empty fields "
             "with the user.", ""]
    lines += [f"- {field}: {values.get(field, '')}".rstrip() for field in FIELDS]
    lines.append(END)
    return "\n".join(lines) + "\n"


def plan(folder, found=None, ci=None):
    """What `init` would add: {top, targets, create, providers, block}. Targets are existing instruction files
    that get the block; with none, AGENTS.md is created and CLAUDE.md imports it."""
    top = project_top(folder)
    found = environment.detect(top, ci) if found is None else found
    names = {entry["path"] for entry in found["instructions"]}
    claude = next((name for name in ("CLAUDE.md", ".claude/CLAUDE.md") if name in names), None)
    targets = []
    if "AGENTS.md" in names:
        targets.append("AGENTS.md")
    same_file = claude and "AGENTS.md" in names and (top / claude).resolve() == (top / "AGENTS.md").resolve()
    if claude and not same_file and "AGENTS.md" not in environment.read_every_session(top, "claude",
                                                                                      found["instructions"]):
        targets.append(claude)
    create = not targets
    providers = [provider for provider, present in (
        ("claude", claude or (top / ".claude").is_dir() or create),
        ("codex", "AGENTS.md" in names or (top / ".codex").is_dir() or (top / ".agents").is_dir() or create))
        if present]
    notes = []
    if "claude" in providers and not claude and not create:
        notes.append("Claude Code reads CLAUDE.md, not AGENTS.md, so it sees the kit only through the skill "
                     "descriptions; a CLAUDE.md with the line `@AGENTS.md` gives it the section too")
    return {"top": top, "targets": targets, "create": create, "providers": providers,
            "block": block_text(found, ci), "found": found, "notes": notes}


def connected(top, found=None):
    """Whether awkit has already added anything here: the record, a block or an awkit skill."""
    found = environment.detect(top) if found is None else found
    return ((Path(top) / RECORD).is_file() or any(f["awkit_words"] for f in found["instructions"])
            or any(s["awkit"] for skills in found["skills"].values() for s in skills))


def predicted_words(the_plan):
    """Words `init` would add to every session per agent, from the plan."""
    from .kit_install import planned_skills
    top, found = the_plan["top"], the_plan["found"]
    block = words(the_plan["block"])
    result = {}
    for reader in ("claude", "codex"):
        if the_plan["create"]:
            added = block + (words(CLAUDE_IMPORT) if reader == "claude" else 0)
        else:
            loaded = environment.read_every_session(top, reader, found["instructions"])
            added = block * sum(1 for target in the_plan["targets"] if target in loaded)
        if reader in the_plan["providers"]:
            planned, _ = planned_skills(top, reader, found_bundles=found["bundles"])
            added += sum(words(_description(text)) for _, _, text in planned)
        result[reader] = added
    return result


def _description(text):
    line = next((line for line in text.splitlines() if line.startswith("description: ")), "")
    value = line.removeprefix("description: ")
    try:
        return json.loads(value)
    except ValueError:
        return value


def _dirty(top, name):
    probe = _git(top, "status", "--porcelain", "--", name)
    return probe.returncode == 0 and bool(probe.stdout.strip())


def _append(text, block):
    """(new text, separator) with `block` after a blank line at the end of `text`."""
    newline = "\r\n" if "\r\n" in text else "\n"
    if not text or text.endswith(newline * 2):
        sep = ""
    elif text.endswith(newline):
        sep = newline
    else:
        sep = newline * 2
    return text + sep + block, sep


def init(folder):
    """Connect the kit: the block in the instruction files, skills for each agent the project uses, and the
    record. Never touches a block or skill that is already there except to regenerate awkit's skills."""
    from .kit_install import install_skills
    the_plan = plan(folder, ci=_ci(folder))
    top = the_plan["top"]
    changes = Changes(top)
    report = {"top": str(top), "appended": [], "created": [], "kept": [], "skills": {}, "dirty": []}
    if the_plan["create"]:
        for name, text in (("AGENTS.md", the_plan["block"]), ("CLAUDE.md", CLAUDE_IMPORT)):
            path = top / name
            if changes.write(path, text, "created"):
                report["created"].append(path)
    for name in the_plan["targets"]:
        path = top / name
        text = read_exact(path)
        if awkit_block(text):
            report["kept"].append(path)
            continue
        if _dirty(top, name):
            report["dirty"].append(name)
        new, sep = _append(text, _newlines(the_plan["block"], text))
        changes.write(path, new, "appended", sep=sep)
        report["appended"].append(path)
    for provider in the_plan["providers"]:
        report["skills"][provider] = install_skills(top, provider, changes=changes)
    report["notes"] = the_plan["notes"]
    report["record"] = changes.save()
    report["changes"] = changes
    report["words"] = environment.session_words(top)
    return report


def _ci(folder):
    from .scan import _ci as find_ci
    return find_ci(project_top(folder))


# Removal


def _strip_block(text, sep=None):
    start = text.find(BEGIN)
    end = text.find(END, start)
    end = len(text) if end < 0 else end + len(END)
    before, after = text[:start], text[end:]
    newline = "\r\n" if "\r\n" in text else "\n"
    if after.startswith(newline):
        after = after[len(newline):]
    if sep is not None and before.endswith(sep) and not after:
        before = before[:len(before) - len(sep)]
    elif not after:
        before = before.rstrip("\r\n") + (newline if before.strip() else "")
    return before + after


def json_format(text):
    """(indent, trailing newline) of a JSON file, so a rewrite changes only what it must."""
    indent = 2
    for line in text.splitlines()[1:]:
        stripped = line.lstrip()
        if stripped and line != stripped:
            whitespace = line[:len(line) - len(stripped)]
            indent = "\t" if whitespace.startswith("\t") else len(whitespace)
            break
    return indent, text.endswith("\n")


def dump_json(data, original=""):
    indent, newline = json_format(original) if original else (2, True)
    return _newlines(json.dumps(data, indent=indent, ensure_ascii=False) + ("\n" if newline else ""), original)


def _strip_hooks(path, created):
    """Take awkit's hook entries out of a Claude Code or Codex settings file; delete a file awkit created
    once nothing else is left in it. Returns what happened."""
    from .hooks import is_awkit_command
    text = read_exact(path)
    data = json.loads(text)
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return "unchanged"
    removed = False
    for event, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        kept = [entry for entry in entries if not (isinstance(entry, dict) and entry.get("hooks") and all(
            isinstance(hook, dict) and is_awkit_command(str(hook.get("command", ""))) for hook in entry["hooks"]))]
        if len(kept) == len(entries):
            continue
        removed = True
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not removed:
        return "unchanged"
    if not hooks and created:
        del data["hooks"]
    if created and not data:
        path.unlink()
        return "deleted"
    write_exact(path, dump_json(data, text))
    return "stripped"


def _strip_git_hook(path, created):
    from .checks import GIT_MARK
    text = read_exact(path)
    kept = [line for line in text.splitlines(keepends=True) if GIT_MARK not in line]
    rest = "".join(kept)
    whole = "Installed by `awkit kit hooks --git`" in text
    if created or whole or not rest.strip() or rest.strip() == "#!/bin/sh":
        path.unlink()
        return "deleted"
    write_exact(path, rest)
    return "stripped"


def _undo(path, entry):
    """Take awkit's part out of a file that changed since awkit wrote it."""
    created = entry.get("before") is None
    text = read_exact(path)
    if GENERATED in text and path.name == "SKILL.md":
        path.unlink()
        return "deleted"
    if BEGIN in text:
        rest = _strip_block(text, entry.get("sep"))
        if created and not rest.strip():
            path.unlink()
            return "deleted"
        write_exact(path, rest)
        return "stripped"
    if path.suffix == ".json":
        return _strip_hooks(path, created)
    if entry.get("action") == "chained" or "awkit" in text:
        return _strip_git_hook(path, created)
    return "unchanged"


def _found_by_markers(top):
    """Files carrying awkit's markers, for a clone without the record: blocks, generated skills,
    settings entries and the Git hook line."""
    from .checks import GIT_MARK, git_hook_path
    from .hooks import SETTINGS, is_awkit_command
    found = []
    for name, _ in environment.INSTRUCTION_FILES:
        path = top / name
        if path.is_file() and BEGIN in path.read_text(encoding="utf-8", errors="replace"):
            text = path.read_text(encoding="utf-8")
            # CLAUDE.md written by init holds only the import.
            found.append((path, {"before": "" if text != CLAUDE_IMPORT else None}))
    for folder in environment.SKILL_FOLDERS.values():
        for path in sorted((top / folder).glob("*/SKILL.md")):
            if environment.is_awkit_skill(path.read_text(encoding="utf-8", errors="replace")):
                found.append((path, {"before": None}))
    for relative in [*SETTINGS.values(), Path(".claude") / "settings.local.json"]:
        path = top / relative
        if path.is_file():
            commands = environment._hook_commands(environment._json(path) or {})
            if any(is_awkit_command(c) for cs in commands.values() for c in cs):
                found.append((path, {"before": ""}))
    try:
        hook = git_hook_path(top)
    except Exception:  # noqa: BLE001 - not a repository
        hook = None
    for path in [hook, hook and hook.with_name("commit-msg.legacy")] if hook else []:
        if path and path.is_file() and GIT_MARK in path.read_text(encoding="utf-8", errors="replace"):
            found.append((path, {"before": "", "action": "chained"}))
    return found


def awkit_records(top):
    folder = Path(top) / ".awkit"
    return [name for name in RECORDS if (folder / name).exists()]


def remove(folder, keep_records=None):
    """Undo init, skills and hooks. `keep_records` decides about run records in .awkit/: True keeps the
    folder without awkit's install record and backups, False deletes it, None keeps it when it holds
    records. Returns {files: [(path, what happened)], dirs, awkit_folder, records}."""
    top = project_top(folder)
    changes = Changes(top)
    report = {"top": str(top), "files": [], "dirs": [], "records": awkit_records(top), "recorded": bool(changes.data["files"])}
    done = set()
    for key, entry in reversed(list(changes.data["files"].items())):
        path = changes.resolve(key)
        done.add(path.absolute())
        if not path.exists():
            report["files"].append((path, "already gone"))
            continue
        current = path.read_bytes()
        if sha(current) == entry.get("after"):
            if entry.get("before") is None:
                path.unlink()
                report["files"].append((path, "deleted"))
                continue
            backup = top / entry.get("backup", "")
            if entry.get("backup") and backup.is_file() and sha(backup.read_bytes()) == entry["before"]:
                path.write_bytes(backup.read_bytes())
                report["files"].append((path, "restored"))
                continue
        report["files"].append((path, _undo(path, entry)))
    for path, entry in _found_by_markers(top):
        if path.absolute() not in done and path.exists():
            report["files"].append((path, _undo(path, entry)))
    for key in reversed(changes.data.get("dirs", [])):
        path = changes.resolve(key)
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            report["dirs"].append(path)
    awkit = top / ".awkit"
    if awkit.is_dir():
        keep = bool(report["records"]) if keep_records is None else keep_records
        if keep:
            for leftover in (top / RECORD, top / BACKUP):
                if leftover.is_dir():
                    shutil.rmtree(leftover)
                elif leftover.exists():
                    leftover.unlink()
            report["awkit_folder"] = "kept"
        else:
            shutil.rmtree(awkit)
            report["awkit_folder"] = "deleted"
            if changes.data.get("excluded"):
                _unexclude(top)
    else:
        report["awkit_folder"] = "absent"
    return report


def _unexclude(top):
    exclude = _exclude_file(top)
    if exclude is None or not exclude.is_file():
        return
    lines = exclude.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if line.strip() != ".awkit/"]
    if len(kept) != len(lines):
        exclude.write_text("".join(kept), encoding="utf-8")
