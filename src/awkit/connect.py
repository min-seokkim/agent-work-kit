"""Install the kit in three layers, record what was added, and take it out again.

The person's computer holds awkit, the guides inside the package and the skills in the user's skill
folders (`kit skills`). A project commits only what finishing means there: `checks.toml`, with the `[kit]`
table, and the `rules.toml` that `kit hooks` drafts. The hooks and `.awkit/` stay local to the clone, since
hooks run code. `kit init` writes the first, calls `kit hooks` for the second and records what it wrote in
`.awkit/installed.json`; `kit skills` records the user folder's files in `~/.awkit/installed.json`.
`kit remove` reads both records and restores each file: byte for byte when the file is as awkit left it,
otherwise by taking out only awkit's own part. awkit writes nowhere else (see WRITES); memory files and the
project's instruction files are only read.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from . import environment
from .environment import BEGIN, END, GENERATED

RECORD = Path(".awkit") / "installed.json"
BACKUP = Path(".awkit") / "backup"
# Records worth keeping when the kit is removed: check runs, accepted versions, the review channel and
# the hook log. The rest of .awkit/ is state that means nothing without the kit.
RECORDS = ("reviews", "accepted", "channel.sqlite3", "hooks.ndjson")
# What an awkit before the three layers appended to instruction files; `kit remove` still takes it out.
CLAUDE_IMPORT = f"{BEGIN}\n@AGENTS.md\n{END}\n"
CHECKS = "checks.toml"
KIT_KEYS = ("version", "done", "recipient", "records")
KIT_MARK = "# Agent Work Kit:"
# Every place awkit writes, relative to the project or (with ~) the home folder. tests/test_layers.py
# fails when init, skills, hooks or remove change anything else.
WRITES = (".awkit/", CHECKS, "rules.toml", ".claude/settings.json", ".claude/settings.local.json",
          ".codex/hooks.json", ".git/info/exclude", ".git/hooks/", "~/.claude/skills/awkit-*",
          "~/.agents/skills/awkit-*", "~/.awkit/")
INSTRUCTION_LINE = ("Agent Work Kit: follow the `awkit-workflow` skill (or `awkit kit guide workflow`); what done "
                    "means here is the `[kit]` table in checks.toml.")

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
        self.excluded_now = False

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

    def save(self, force=False):
        """Write the record when something changed, or always with `force`. Returns its path or None."""
        if not (self.changed or force):
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
                self.excluded_now = True
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        return self.path


def _exclude_file(top):
    probe = _git(top, "rev-parse", "--git-path", "info/exclude")
    if probe.returncode:
        return None
    path = Path(probe.stdout.strip())
    return path if path.is_absolute() else top / path


# Installing: checks.toml with the [kit] table, the hooks through `kit hooks`, and the record.


def kit_table(path):
    """The `[kit]` table of a checks.toml, {} when it has none, or None when the file is missing or does
    not parse."""
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    table = data.get("kit")
    return table if isinstance(table, dict) else {}


def _toml(value):
    return json.dumps(value, ensure_ascii=False)  # a JSON string is a TOML basic string


def kit_values(top, found=None):
    """The values init writes: the installed version, and for records a pointer to where the project already
    keeps state; done and recipient are the user's to say."""
    from . import __version__
    found = environment.detect(top) if found is None else found
    records = ", ".join(m["path"] for m in found["memory"] if not Path(m["path"]).is_absolute())
    return {"version": __version__, "done": "", "recipient": "", "records": records}


def kit_block(values):
    lines = [f"{KIT_MARK} what finishing means in this project. `awkit doctor` compares version with the",
             "# installed awkit. Fill done (one sentence), recipient (who or what receives the result) and records",
             "# (where the project keeps its state) with the user: `awkit kit guide connect`.", "[kit]"]
    return "\n".join(lines + [f"{key} = {_toml(values[key])}" for key in KIT_KEYS]) + "\n"


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


def _fill_keys(text, missing, values):
    """`text` with the missing [kit] keys added right after the `[kit]` header."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if re.match(r"\s*\[kit\]\s*(#.*)?$", line.rstrip("\r\n")):
            ending = line[len(line.rstrip("\r\n")):] or newline
            added = [f"{key} = {_toml(values[key])}{newline}" for key in missing]
            return "".join(lines[:index] + [line.rstrip("\r\n") + ending] + added + lines[index + 1:])
    return text


def write_checks(top, changes, found=None):
    """Write checks.toml from the scan's draft with the [kit] table, or add what an existing one lacks:
    the table, or keys missing from it. Nothing an existing file holds is changed. Returns (what, notes)."""
    from .scan import scan
    path = top / CHECKS
    values = kit_values(top, found)
    if not path.exists():
        draft = scan(top)["suggested_checks_toml"]
        text, _ = _append(draft, kit_block(values))
        changes.write(path, text, "created", kit="table")
        if "[[checks]]" not in draft:
            return "created", ["the scan found no check command; add the project's checks under [[checks]] before "
                               "`awkit review check`, which needs at least one"]
        return "created", ["the checks are a draft from `awkit kit scan`; run `awkit review check HEAD --config "
                           "checks.toml` once and keep only the commands that work here"]
    table = kit_table(path)
    if table is None:
        return "kept", [f"{path} does not parse as TOML, so it was left as it is; fix it and run kit init again"]
    text = read_exact(path)
    if not table and "[kit]" not in text:
        new, sep = _append(text, _newlines(kit_block(values), text))
        changes.write(path, new, "appended", kit="table", sep=sep)
        return "appended", []
    missing = [key for key in KIT_KEYS if key not in table]
    if not missing:
        return "kept", []
    new = _fill_keys(text, missing, values)
    if new == text:
        return "kept", [f"the [kit] table in {path} could not be found line by line; add {', '.join(missing)} by hand"]
    changes.write(path, new, "filled")
    entry = changes.data["files"][changes.key(path)]
    if entry.get("kit") != "table":  # a table init wrote goes whole; otherwise only the keys it added
        entry["kit_keys"] = sorted(set(entry.get("kit_keys", [])) | set(missing))
    return "filled", []


def providers(top):
    """The agents a project is set up for: Claude Code with CLAUDE.md or .claude/, Codex with AGENTS.md,
    .codex/ or .agents/; both when it has neither."""
    claude = any((top / name).exists() for name in ("CLAUDE.md", ".claude/CLAUDE.md", ".claude"))
    codex = any((top / name).exists() for name in ("AGENTS.md", ".codex", ".agents"))
    return [name for name, used in (("claude", claude), ("codex", codex)) if used] or ["claude", "codex"]


def run_kit_hooks(top, *arguments):
    """Run `awkit kit hooks` as a command. The hook side owns what it writes (rules.toml, the handlers and the
    Git hook line); init and remove only call it. Its output goes to this process's output. Returns its
    exit code."""
    print("running: awkit kit hooks " + " ".join(arguments), flush=True)
    return subprocess.run([sys.executable, "-m", "awkit", "kit", "hooks", str(top), *arguments]).returncode


def user_skills(home=None):
    """{provider: [(name, version)]} for the awkit skills in the user's skill folders."""
    from .kit_install import user_skill_folders
    found = {}
    for provider, folder in user_skill_folders(home).items():
        entries = []
        for path in sorted(folder.glob("awkit-*/SKILL.md")) if folder.is_dir() else []:
            text = path.read_text(encoding="utf-8", errors="replace")
            if environment.is_awkit_skill(text):
                match = re.search(re.escape(GENERATED) + r" by awkit ([^\s(,]+)", text)
                entries.append((path.parent.name, match.group(1) if match else None))
        found[provider] = entries
    return found


def init(folder, hooks=True, git=True):
    """Install the project layer: checks.toml with the [kit] table, the hooks through `kit hooks`, and
    .awkit/ excluded from Git, all recorded in .awkit/installed.json. Commits nothing and never writes to
    the project's instruction files, skills or memory. Returns a report for the command to print."""
    top = project_top(folder)
    found = environment.detect(top)
    changes = Changes(top, exclude=git)
    repository = (top / ".git").exists()
    report = {"top": str(top), "checks": None, "hooks": None, "excluded": False, "notes": [], "record": None}
    report["checks"], notes = write_checks(top, changes, found)
    report["notes"] += notes
    report["record"] = changes.save(force=True)
    report["excluded"] = changes.excluded_now
    if not repository and git:
        report["notes"].append(f"{top} is not a Git repository: the hooks and the .awkit/ exclusion need one; run "
                               "`git init` and then `awkit kit init` again")
    if hooks and git and repository:
        arguments = ["--git", *(f"--{name}" for name in providers(top))]
        report["hooks"] = (arguments, run_kit_hooks(top, *arguments))
    skills = user_skills()
    if not any(skills.values()) and not any(s["awkit"] for entries in found["skills"].values() for s in entries):
        report["notes"].append("the guides are not in your user folder yet: run `awkit kit skills` once on this "
                               "computer")
    report["words"] = environment.session_words(top)
    return report


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
    if path.name == CHECKS and (entry.get("kit") or entry.get("kit_keys")):
        rest = strip_kit(text, entry.get("kit_keys") if not entry.get("kit") else None, entry.get("sep"))
        write_exact(path, rest)
        return "stripped"
    if path.suffix == ".json":
        return _strip_hooks(path, created)
    if entry.get("action") == "chained" or "awkit" in text:
        return _strip_git_hook(path, created)
    return "unchanged"


def strip_kit(text, keys=None, sep=None):
    """`text` without the [kit] table and the comment kit init wrote above it, or with `keys`, without only
    those keys of the table."""
    lines = text.splitlines(keepends=True)
    header = next((i for i, line in enumerate(lines) if re.match(r"\s*\[kit\]\s*(#.*)?$", line.rstrip("\r\n"))), None)
    if header is None:
        return text
    end = next((i for i in range(header + 1, len(lines)) if re.match(r"\s*\[", lines[i])), len(lines))
    if keys is not None:
        pattern = re.compile(r"\s*(" + "|".join(map(re.escape, keys)) + r")\s*=")
        return "".join(line for i, line in enumerate(lines) if not (header < i < end and pattern.match(line)))
    start = header
    while start > 0 and lines[start - 1].startswith("#"):
        start -= 1
    if not lines[start].startswith(KIT_MARK):
        start = header
    before, after = "".join(lines[:start]), "".join(lines[end:])
    if not after and sep is not None and before.endswith(sep):
        before = before[:len(before) - len(sep)]
    elif not after:
        newline = "\r\n" if "\r\n" in text else "\n"
        before = before.rstrip("\r\n") + (newline if before.strip() else "")
    return before + after


def _found_by_markers(top, hooks=True):
    """Files carrying awkit's markers, for a clone without the record: the [kit] table, blocks earlier
    versions appended, generated skills and, unless `kit hooks --remove` took them out, settings entries and
    the Git hook line."""
    from .checks import GIT_MARK, git_hook_path
    from .hooks import SETTINGS, is_awkit_command
    found = []
    checks = top / CHECKS
    if checks.is_file() and KIT_MARK in checks.read_text(encoding="utf-8", errors="replace"):
        found.append((checks, {"before": "", "kit": "table"}))

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
    for relative in [*SETTINGS.values(), Path(".claude") / "settings.local.json"] if hooks else []:
        path = top / relative
        if path.is_file():
            commands = environment._hook_commands(environment._json(path) or {})
            if any(is_awkit_command(c) for cs in commands.values() for c in cs):
                found.append((path, {"before": ""}))
    try:
        hook = git_hook_path(top) if hooks else None
    except Exception:  # noqa: BLE001 - not a repository
        hook = None
    for path in [hook, hook and hook.with_name("commit-msg.legacy")] if hook else []:
        if path and path.is_file() and GIT_MARK in path.read_text(encoding="utf-8", errors="replace"):
            found.append((path, {"before": "", "action": "chained"}))
    return found


def awkit_records(top):
    folder = Path(top) / ".awkit"
    return [name for name in RECORDS if (folder / name).exists()]


def _restore(changes):
    """Restore every file in a record: [(path, what happened)] and the set of paths handled."""
    report, done = [], set()
    for key, entry in reversed(list(changes.data["files"].items())):
        path = changes.resolve(key)
        done.add(path.absolute())
        if not path.exists():
            report.append((path, "already gone"))
            continue
        current = path.read_bytes()
        if sha(current) == entry.get("after"):
            if entry.get("before") is None:
                path.unlink()
                report.append((path, "deleted"))
                continue
            backup = changes.top / entry.get("backup", "")
            if entry.get("backup") and backup.is_file() and sha(backup.read_bytes()) == entry["before"]:
                path.write_bytes(backup.read_bytes())
                report.append((path, "restored"))
                continue
        report.append((path, _undo(path, entry)))
    return report, done


def _remove_dirs(changes):
    removed = []
    for key in reversed(changes.data.get("dirs", [])):
        path = changes.resolve(key)
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            removed.append(path)
    return removed


def remove(folder, keep_records=None, hooks=True):
    """Undo the project layer. `kit hooks --remove` takes out the hooks and rules.toml first; then every file
    in the record is restored, the [kit] table taken out of checks.toml, and .awkit/ handled: `keep_records`
    True keeps the folder without awkit's install record and backups, False deletes it (and the exclude
    line), None keeps it when it holds records. Returns {files: [(path, what happened)], dirs, hooks,
    awkit_folder, records}."""
    top = project_top(folder)
    report = {"top": str(top), "files": [], "dirs": [], "records": awkit_records(top), "hooks": None}
    if hooks and (top / ".git").exists():
        report["hooks"] = run_kit_hooks(top, "--remove")
    changes = Changes(top)  # read after kit hooks, which keeps its own part of the record
    report["recorded"] = bool(changes.data["files"]) or (top / RECORD).is_file()
    report["files"], done = _restore(changes)
    for path, entry in _found_by_markers(top, hooks=report["hooks"] != 0):
        if path.absolute() not in done and path.exists():
            report["files"].append((path, _undo(path, entry)))
    report["dirs"] = _remove_dirs(changes)
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


def remove_user(home=None):
    """Take the skills `kit skills` wrote out of the user's skill folders, from `~/.awkit/installed.json`, or by
    their marker without it. Returns {files, dirs, recorded}."""
    from .kit_install import user_skill_folders
    home = Path.home() if home is None else Path(home)
    changes = Changes(home, exclude=False)
    files, done = _restore(changes)
    for folder in user_skill_folders(home).values():
        for path in sorted(folder.glob("awkit-*/SKILL.md")) if folder.is_dir() else []:
            if path.absolute() not in done and environment.is_awkit_skill(path.read_text("utf-8", errors="replace")):
                path.unlink()
                files.append((path, "deleted"))
                if not any(path.parent.iterdir()):
                    path.parent.rmdir()
    dirs = _remove_dirs(changes)
    recorded = changes.path.is_file()
    for leftover in (home / BACKUP, home / RECORD):
        if leftover.is_dir():
            shutil.rmtree(leftover)
        elif leftover.exists():
            leftover.unlink()
    awkit = home / ".awkit"
    if awkit.is_dir() and not any(awkit.iterdir()):
        awkit.rmdir()
    return {"files": files, "dirs": dirs, "recorded": recorded}


def _unexclude(top):
    exclude = _exclude_file(top)
    if exclude is None or not exclude.is_file():
        return
    lines = exclude.read_bytes().splitlines(keepends=True)
    kept = [line for line in lines if line.strip() != b".awkit/"]
    if len(kept) != len(lines):
        exclude.write_bytes(b"".join(kept))
