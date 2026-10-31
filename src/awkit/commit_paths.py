"""Explicit Git-for-Windows Bash path input for the bundled commit adapter."""

import json
import ntpath
import re
import sys

ENV_KEY = "AWKIT_CLAUDE_BASH_PATHS"
MODE = "git-bash"
ARGUMENT = "--bash-paths=git-bash"


def selected(value, payload):
    """Keep invalid selections visible too, but only in the supported tool/runtime."""
    return value if sys.platform == "win32" and payload.get("tool_name") == "Bash" else None


def declaration_error(value, root):
    """Validate a selected value against exactly the current rule project's declaration."""
    if value != MODE:
        return "AWKIT_CLAUDE_BASH_PATHS must be git-bash"
    try:
        settings = json.loads((root / ".claude/settings.local.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return "current local Git-Bash path declaration is missing, unreadable or malformed"
    env = settings.get("env") if isinstance(settings, dict) else None
    if not isinstance(env, dict) or env.get(ENV_KEY) != value:
        return "current local Git-Bash path declaration does not match the selected value"
    return None


def component(value):
    """Convert one literal path before joining it; reject roots we cannot interpret."""
    if not value or any(c in value for c in "\x00\r\n$`*?[]{}") or value.startswith("~"):
        raise ValueError("Git-Bash commit path needs a literal, unambiguous path")
    if value.startswith(("//", "\\\\")):
        drive, tail = ntpath.splitdrive(value)
        parts = drive.replace("\\", "/").split("/")
        if len(parts) != 4 or not all(parts[2:]) or parts[2].lower() in ("wsl$", "wsl.localhost", "."):
            raise ValueError("unsupported UNC or WSL commit path")
        return value
    match = re.match(r"^/([A-Za-z])(?:/|$)", value)
    if match:
        return match[1].upper() + ":/" + value[match.end():]
    if value.startswith(("/", "\\")):
        raise ValueError("unsupported POSIX or drive-relative commit path")
    drive, tail = ntpath.splitdrive(value)
    if drive and (not re.fullmatch(r"[A-Za-z]:", drive) or not tail.startswith(("/", "\\"))):
        raise ValueError("unsupported drive-relative commit path")
    if ":" in tail:
        raise ValueError("ambiguous commit path")
    return value


def join(parent, value):
    return ntpath.join(parent, component(value))
