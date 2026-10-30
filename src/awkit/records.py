"""Small helpers for the JSON records that awkit writes."""

import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")

# Windows refuses to replace a file while another process, such as a scanner or indexer, holds it open.
# The hold is usually brief; elsewhere PermissionError means a real permission problem.
REPLACE_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6) if os.name == "nt" else ()


def stamp():
    return datetime.now(UTC).isoformat()


def replace(source, target):
    """os.replace, retried for about three seconds while Windows reports the target as in use."""
    for delay in REPLACE_DELAYS:
        try:
            return os.replace(source, target)
        except PermissionError:
            time.sleep(delay)
    return os.replace(source, target)


def atomic_json(path, value):
    """Write JSON so that a reader sees either the old file or the complete new one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
