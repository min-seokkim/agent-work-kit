"""Reading and writing a project's own files without changing their bytes needlessly: exact reads, JSON in the
file's own format, the [kit] table of checks.toml and the paths of awkit's install record."""

import hashlib
import json
import tomllib
from pathlib import Path

RECORD = Path(".awkit") / "installed.json"


BACKUP = Path(".awkit") / "backup"


CHECKS = "checks.toml"


def read_exact(path):
    """A file's text with its line endings and any undecodable bytes kept, so writing it back changes
    nothing awkit did not mean to change."""
    return Path(path).read_bytes().decode("utf-8", errors="surrogateescape")


def _newlines(text, like):
    return text.replace("\n", "\r\n") if "\r\n" in like else text


def sha(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def kit_table(path):
    """The `[kit]` table of a checks.toml, {} when it has none, or None when the file is missing or does
    not parse."""
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    table = data.get("kit")
    return table if isinstance(table, dict) else {}


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
