"""`awkit kit hooks`: connect the hook runner to a project, and `--remove` to take it out again.

It writes four things, each marked as awkit's: rules.toml from the kit's default rules when the project has
none (its first line says `kit hooks` wrote it), a handler `awkit hook <event> --kit-hooks` per hook event in
`.claude/settings.local.json` and in Codex's project hook file `.codex/hooks.json`, and the commit identity
check in the repository's commit-msg hook (a line after an existing hook's commands, with husky or pre-commit
in their files; see checks.install_git_hook). Hooks run code, so nothing goes into the user's own folders:
the handlers exist only in projects that chose awkit.

What it writes is recorded in `.awkit/kit-hooks.json` with a copy of each file as it was, so `--remove`
restores a file byte for byte while it is as awkit left it, and otherwise takes out only what carries the
marker. It reads no other install state, so `kit init` and `kit remove` can call it.
"""

import hashlib
import json
import shutil
from pathlib import Path

EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop")
MARK = "--kit-hooks"
SETTINGS = {"claude": Path(".claude") / "settings.local.json", "codex": Path(".codex") / "hooks.json"}
# Files of the same agent that may already run the runner; a second handler would run every rule twice.
OTHER_SETTINGS = {"claude": [Path(".claude") / "settings.json"], "codex": []}
RECORD = Path(".awkit") / "kit-hooks.json"
BACKUP = Path(".awkit") / "kit-hooks"
DRAFT_MARK = "# Written by `awkit kit hooks`"


def _sha(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def _read(path):
    return Path(path).read_bytes().decode("utf-8", errors="surrogateescape")


def _json_format(text):
    """(indent, trailing newline) of a JSON file, so a rewrite changes only what it must."""
    indent = 2
    for line in text.splitlines()[1:]:
        stripped = line.lstrip()
        if stripped and line != stripped:
            whitespace = line[:len(line) - len(stripped)]
            indent = "\t" if whitespace.startswith("\t") else len(whitespace)
            break
    return indent, text.endswith("\n") or not text


def _dump(data, original=""):
    indent, newline = _json_format(original)
    text = json.dumps(data, indent=indent, ensure_ascii=False) + ("\n" if newline else "")
    return text.replace("\n", "\r\n") if "\r\n" in original else text


def handler_command(event, skip=()):
    """The handler for one event. It names awkit, not an interpreter, so the file works after reinstalling;
    `|| exit 0` keeps a missing awkit from blocking the agent, and MARK says which handlers this command added."""
    return " ".join(["awkit", "hook", event, MARK, *(f"--skip {name}" for name in skip)]) + " || exit 0"


def is_ours(command):
    return isinstance(command, str) and command.strip().startswith("awkit hook") and MARK in command


def _runs_awkit(command):
    return isinstance(command, str) and command.strip().startswith("awkit hook")


def _commands(entries):
    return [hook.get("command") for entry in entries if isinstance(entry, dict)
            for hook in entry.get("hooks", []) if isinstance(hook, dict)]


class Record:
    """What kit hooks wrote: the hash before and after and a copy of the original for each file, the folders
    it created and whether it excluded .awkit/ from Git. Has the `write(path, text, action)` that
    checks.install_git_hook calls."""

    def __init__(self, top):
        self.top = Path(top)
        try:
            self.data = json.loads((self.top / RECORD).read_text(encoding="utf-8"))
            if not isinstance(self.data.get("files"), dict) or not isinstance(self.data.get("dirs"), list):
                raise ValueError
        except (OSError, ValueError, AttributeError):
            self.data = {"schema": 1, "files": {}, "dirs": []}
        self.changed = False
        self.had_awkit = (self.top / ".awkit").exists()

    def key(self, path):
        path = Path(path).absolute()
        try:
            return path.relative_to(self.top.absolute()).as_posix()
        except ValueError:
            return str(path)

    def write(self, path, text, action="written"):
        path = Path(path).absolute()
        data = text.encode("utf-8", errors="surrogateescape")
        before = path.read_bytes() if path.is_file() else None
        if before == data:
            return False
        key = self.key(path)
        entry = self.data["files"].get(key)
        if entry is None:
            entry = {"action": action, "before": _sha(before)}
            if before is not None:
                backup = self.top / BACKUP / key.replace(":", "_").lstrip("/")
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(before)
                entry["backup"] = backup.relative_to(self.top).as_posix()
                entry["mode"] = path.stat().st_mode & 0o777
            self.data["files"][key] = entry
        missing, parent = [], path.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for folder in reversed(missing):
            folder.mkdir()
            self.data["dirs"].append(self.key(folder))
        path.write_bytes(data)
        entry["after"] = _sha(data)
        self.changed = True
        return True

    def save(self):
        if not self.changed:
            return
        path = self.top / RECORD
        path.parent.mkdir(parents=True, exist_ok=True)
        if not self.had_awkit:
            self.data["created_awkit"] = True
        if (self.top / ".git").exists() and not self.data.get("excluded"):
            from .review import exclude_locally
            exclude = _exclude_file(self.top)
            before = exclude.read_text(encoding="utf-8") if exclude and exclude.is_file() else ""
            exclude_locally(self.top, ".awkit/")
            after = exclude.read_text(encoding="utf-8") if exclude and exclude.is_file() else ""
            self.data["excluded"] = after != before
        path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")


def _exclude_file(top):
    from .review import git
    try:
        path = Path(git(top, "rev-parse", "--git-path", "info/exclude"))
    except Exception:  # noqa: BLE001 - not a repository
        return None
    return path if path.is_absolute() else Path(top) / path


def _top(folder):
    from .review import git
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError(f"The folder does not exist: {folder}")
    try:
        return Path(git(folder, "rev-parse", "--show-toplevel")).resolve(), True
    except Exception:  # noqa: BLE001 - outside a repository the folder is the project
        return folder, False


# Installing


def draft_rules(top):
    """The text of rules.toml written from the kit's default rules, with {kit} pointing at a kit folder in the
    project or at the kit installed with awkit."""
    import re

    from .hooks import BUNDLE, kit_folder
    from .kit_install import kit_root
    kit = kit_root()
    first, *rest = [Path(kit.joinpath(name)).read_text(encoding="utf-8") for name in BUNDLE]
    folder = kit_folder(top)
    first = re.sub(r'(?m)^kit = "[^"]*"', lambda _: f"kit = {json.dumps(folder, ensure_ascii=False)}", first, count=1)
    head = (f"{DRAFT_MARK} from the kit's default rules. Change it as the project needs; `awkit kit hooks --remove`\n"
            "# deletes it only while it is unchanged, and asks otherwise. The format is in the kit's reference.md.\n")
    return head + "\n".join([first, *rest])


def install_settings(top, provider, record, skip=()):
    """Add a handler per event to the agent's project hook file, beside the handlers there. An event that
    already runs `awkit hook` in this file or another of the same agent's files is left alone. Returns
    (path, "installed" or "kept")."""
    path = top / SETTINGS[provider]
    original = _read(path) if path.is_file() else ""
    settings = json.loads(original) if original.strip() else {}
    if not isinstance(settings, dict) or not isinstance(settings.setdefault("hooks", {}), dict):
        raise ValueError(f"{path} does not hold a JSON object with a `hooks` object")
    elsewhere = set()
    for other in OTHER_SETTINGS[provider]:
        try:
            data = json.loads(_read(top / other))
            for event, entries in data.get("hooks", {}).items():
                if isinstance(entries, list) and any(_runs_awkit(c) for c in _commands(entries)):
                    elsewhere.add(event)
        except (OSError, ValueError, AttributeError):
            continue
    changed = False
    for event in EVENTS:
        if event in elsewhere:
            continue
        entries = settings["hooks"].setdefault(event, [])
        if not isinstance(entries, list):
            raise ValueError(f"{path}: `hooks.{event}` is not a list")
        if any(_runs_awkit(c) for c in _commands(entries)):
            continue
        entries.append({"hooks": [{"type": "command", "command": handler_command(event, skip), "timeout": 60}]})
        changed = True
    if changed:
        record.write(path, _dump(settings, original), "merged")
    return path, "installed" if changed else "kept"


def install(folder, use_git=True, use_claude=True, use_codex=True):
    """Connect the hook runner. Returns {installed, connected, kept, notes} lists of lines to print."""
    from .hooks import RULES_FILE
    top, repository = _top(folder)
    record = Record(top)
    result = {"installed": [], "connected": [], "kept": [], "notes": []}
    rules = top / RULES_FILE
    if not rules.exists():
        record.write(rules, draft_rules(top), "created")
        result["installed"].append(f"{rules} (the kit's default rules; change them as the project needs)")
    else:
        result["kept"].append(str(rules))
    providers = [name for name, chosen in (("claude", use_claude), ("codex", use_codex)) if chosen]
    skip = []
    if providers:
        from .environment import gates
        found = gates(top)
        if found:
            skip.append("done-check")
            result["notes"].append("the done check is left out: " + ", ".join(f"{g['name']} ({g['evidence']})"
                                   for g in found) + " already stops the agent from finishing unchecked work")
    for provider in providers:
        try:
            path, what = install_settings(top, provider, record, skip)
        except ValueError as exc:
            result["notes"].append(f"{exc}; no handler was added there")
            continue
        result[what].append(str(path))
    if "codex" in providers:
        result["notes"].append("Codex runs project hooks only in a trusted project, after each is approved under /hooks")
    if use_git:
        if repository:
            from .checks import install_git_hook
            path, what, note = install_git_hook(top, record)
            result[what].append(str(path) + (f" ({note})" if note else ""))
        else:
            result["notes"].append("not a Git repository: no commit-msg hook")
    record.save()
    return result


# Removing


def _strip_settings(path):
    """Take the marked handlers out of an agent's hook file. Returns True when the file changed."""
    text = _read(path)
    data = json.loads(text)
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return False
    changed = False
    for event, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        kept = []
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("hooks"), list):
                inner = [h for h in entry["hooks"] if not (isinstance(h, dict) and is_ours(h.get("command")))]
                if len(inner) != len(entry["hooks"]):
                    changed = True
                    if not inner:
                        continue
                    entry = {**entry, "hooks": inner}
            kept.append(entry)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if changed:
        path.write_bytes(_dump(data, text).encode("utf-8", errors="surrogateescape"))
    return changed


def _strip_git_hook(path, created):
    from .checks import GIT_MARK
    text = _read(path)
    if GIT_MARK not in text:
        return "unchanged"
    if created:
        path.unlink()
        return "deleted"
    rest = "".join(line for line in text.splitlines(keepends=True) if GIT_MARK not in line)
    path.write_bytes(rest.encode("utf-8", errors="surrogateescape"))
    return "stripped"


def _ask_delete(path):
    import sys
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        answer = input(f"{path} was changed after `awkit kit hooks` wrote it. Delete it anyway? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def remove(folder, ask=None):
    """Take out what `install` added. A file still as it was written is restored from its copy, or deleted when
    kit hooks created it; a file changed since loses only the marked handlers or line. rules.toml goes only
    while unchanged; a changed one is deleted when `ask(path)` says so (by default, the person at a terminal;
    without one it is kept). Returns [(path, what happened)]."""
    from .checks import git_hook_path
    from .hooks import RULES_FILE
    top, repository = _top(folder)
    record = Record(top)
    done, report = set(), []
    ask = _ask_delete if ask is None else ask
    for key, entry in reversed(list(record.data["files"].items())):
        path = Path(key) if Path(key).is_absolute() else top / key
        done.add(path.absolute())
        if not path.exists():
            report.append((path, "already gone"))
            continue
        current = path.read_bytes()
        created = entry.get("before") is None
        if _sha(current) == entry.get("after"):
            if created:
                path.unlink()
                report.append((path, "deleted"))
                continue
            backup = top / entry.get("backup", "")
            if entry.get("backup") and backup.is_file() and _sha(backup.read_bytes()) == entry["before"]:
                path.write_bytes(backup.read_bytes())
                if "mode" in entry:
                    path.chmod(entry["mode"])
                report.append((path, "restored"))
                continue
        if path.name == RULES_FILE and path.parent == top:
            if ask(path):
                path.unlink()
                report.append((path, "deleted"))
            else:
                report.append((path, "kept (changed since it was written)"))
        elif path.suffix == ".json":
            report.append((path, "stripped" if _strip_settings(path) else "unchanged"))
        else:
            report.append((path, _strip_git_hook(path, created)))
    # Without the record, as in another clone, the markers show what is awkit's.
    candidates = [top / relative for relative in SETTINGS.values()]
    if repository:
        hook = git_hook_path(top)
        candidates += [hook, hook.with_name("commit-msg.legacy"), top / ".husky" / "commit-msg"]
    for path in candidates:
        if path.absolute() in done or not path.is_file():
            continue
        try:
            if path.suffix == ".json":
                if _strip_settings(path):
                    report.append((path, "stripped"))
            elif _strip_git_hook(path, False) == "stripped":
                report.append((path, "stripped"))
        except (OSError, ValueError):
            continue
    rules = top / RULES_FILE
    if rules.absolute() not in done and rules.is_file() and _read(rules).startswith(DRAFT_MARK):
        if _read(rules) == draft_rules(top) or ask(rules):
            rules.unlink()
            report.append((rules, "deleted"))
        else:
            report.append((rules, "kept (changed since it was written)"))
    for key in reversed(record.data.get("dirs", [])):
        path = Path(key) if Path(key).is_absolute() else top / key
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    _forget(top, record)
    return report


def _forget(top, record):
    """Delete the record and the copies, then .awkit/ when kit hooks created it and nothing else is left."""
    (top / RECORD).unlink(missing_ok=True)
    shutil.rmtree(top / BACKUP, ignore_errors=True)
    folder = top / ".awkit"
    if record.data.get("created_awkit") and folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()
        if record.data.get("excluded"):
            exclude = _exclude_file(top)
            if exclude and exclude.is_file():
                lines = exclude.read_text(encoding="utf-8").splitlines(keepends=True)
                exclude.write_text("".join(line for line in lines if line.strip() != ".awkit/"), encoding="utf-8")
