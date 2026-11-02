"""The one native Codex runtime awkit has verified: its version, executable hash and home, and local paths in
the spelling that runtime reports. Model selection, enrollment, discovery and turn updates require it."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

VERSION = "codex-cli 0.164.0-alpha.11.1"


EXECUTABLE_SHA256 = "4fd2f057bad603bf53dc202457ffd0c3591de62e867a8b01e73816e3fbce5a73"


def local_path(value):
    """Normalize the native Windows extended-drive spelling, retaining local-only scope."""
    value = os.fspath(value)
    if os.name == "nt" and value.startswith("\\\\?\\"):
        value = value[4:]
    if not Path(value).is_absolute() or value.startswith("\\\\"):
        raise ValueError("Enrollment requires an absolute local path.")
    return Path(value).resolve(strict=True)


def runtime(command):
    if len(command) != 1:
        raise ValueError("Enrollment requires the supported unmodified native executable, without wrapper/config arguments.")
    executable = Path(shutil.which(command[0]) or command[0]).resolve(strict=True)
    with executable.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != EXECUTABLE_SHA256:
        raise ValueError("This executable is outside the verified Codex enrollment runtime; no connection was opened.")
    result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode or result.stdout.strip() != VERSION:
        raise ValueError("Codex enrollment runtime version is unsupported.")
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve(strict=True)
    return dict(executable=str(executable), executable_sha256=digest, version=VERSION, codex_home=str(home))
