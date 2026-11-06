"""Native Codex launch evidence and minimum version; protocol support is probed separately."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

MIN_VERSION = "0.164.0-alpha.11.1"


def version_key(value):
    match = re.fullmatch(r"(?:codex-cli )?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+(?:\.\d+)*))?(?:\+[\w.-]+)?", value)
    if not match:
        raise ValueError("Unrecognized Codex version.")
    major, minor, patch, stage, number = match.groups()
    return (int(major), int(minor), int(patch), {"alpha": 0, "beta": 1, "rc": 2, None: 3}[stage],
            tuple(map(int, number.split("."))) if number else ())


def supported_version(value):
    try:
        return version_key(value) >= version_key(MIN_VERSION)
    except (TypeError, ValueError):
        return False


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
        magic = handle.read(4)
        if magic[:2] != b"MZ" and magic not in (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                                               b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe",
                                               b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"):
            raise ValueError("Codex requires a native executable; script wrappers are unsupported.")
        handle.seek(0)
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    version = result.stdout.strip()
    if result.returncode or not supported_version(version):
        raise ValueError(f"Codex requires version {MIN_VERSION} or newer.")
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()
    return dict(executable=str(executable), executable_sha256=digest, version=version, version_exit=0,
                native_executable=True, codex_home=str(home))
