"""Local review messages with transactional, cross-platform storage."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

# The failure catalogue entries (kit/failures.md) this command guards against: reviews of an unnamed
# version, and rebuttals without end.
PREVENTS = {"awkit channel": ("F17", "F18")}

ROLES = ("main", "reviewer")
REQUESTS = ("review", "scout", "test", "draft", "question", "final")
KINDS = (*REQUESTS, "notice", "close", "re", "rebut")
ID = re.compile(r"[MR]-[0-9]{3,}\Z")


SCHEMA = """
    CREATE TABLE IF NOT EXISTS messages (
        seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
        sender TEXT NOT NULL, receiver TEXT NOT NULL,
        kind TEXT NOT NULL, reply_to TEXT, snap TEXT,
        at TEXT NOT NULL, body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cursors (
        role TEXT PRIMARY KEY, seq INTEGER NOT NULL);
"""


class Channel:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._ready = False

    def _prepare(self, conn):
        # Create the schema once per process; later calls skip straight to the query.
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if conn.execute("PRAGMA user_version").fetchone()[0] == 0:
                    for statement in SCHEMA.split(";"):
                        if statement.strip():
                            conn.execute(statement)
                    conn.execute("PRAGMA user_version=1")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != 1:
            raise ValueError("Unsupported channel database version.")
        self._ready = True

    @contextmanager
    def transaction(self, write=True):
        """Writers take the lock up front; readers use a shared lock and never block each other."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            if not self._ready:
                self._prepare(conn)
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def post(self, sender, receiver, kind, body, *, reply_to=None, snap=None):
        if not isinstance(body, str) or not body.strip():
            raise ValueError("The message body is empty.")
        if sender not in ROLES or receiver not in ROLES or sender == receiver:
            raise ValueError("Messages go between main and reviewer only.")
        if kind not in KINDS or (kind == "close" and sender != "main"):
            raise ValueError("Unknown message kind, or close was not sent by main.")
        if (kind in ("re", "rebut")) != bool(reply_to):
            raise ValueError("re and rebut require --reply-to; other kinds do not take it.")
        if reply_to and not ID.fullmatch(reply_to):
            raise ValueError("Invalid reply target ID.")
        if snap and not re.fullmatch(r"[0-9a-f]{7,64}", snap):
            raise ValueError("A snapshot ID is 7 to 64 lowercase hex characters.")
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM messages WHERE kind='close'").fetchone():
                raise ValueError("This channel is closed. Use another database path for new work.")
            if reply_to:
                parent = conn.execute(
                    "SELECT * FROM messages WHERE id=?", (reply_to,)
                ).fetchone()
                if not parent or parent["sender"] != receiver or parent["receiver"] != sender:
                    raise ValueError("A reply must answer a message the other side sent.")
            count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE sender=?", (sender,)
            ).fetchone()[0]
            message_id = f"{'M' if sender == 'main' else 'R'}-{count + 1:03d}"
            conn.execute(
                "INSERT INTO messages(id,sender,receiver,kind,reply_to,snap,at,body) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (message_id, sender, receiver, kind, reply_to, snap,
                 datetime.now(UTC).isoformat(), body),
            )
            return message_id

    def find(self, role, mode, target=None):
        if role not in ROLES or mode not in ("request", "new", "reply"):
            raise ValueError("Unknown role or wait mode.")
        if mode == "reply" and (not target or not ID.fullmatch(target)):
            raise ValueError("reply mode requires a message ID.")
        if mode != "reply" and target:
            raise ValueError("A message ID is accepted in reply mode only.")
        if mode == "new":
            # Check under a read lock first so idle waiters never queue for the write lock.
            with self.transaction(write=False) as conn:
                closed = role == "reviewer" and conn.execute(
                    "SELECT 1 FROM messages WHERE kind='close'").fetchone()
                cursor = conn.execute("SELECT seq FROM cursors WHERE role=?", (role,)).fetchone()
                unseen = conn.execute("SELECT 1 FROM messages WHERE receiver=? AND seq>?",
                                      (role, cursor[0] if cursor else 0)).fetchone()
            if closed:
                return 3, []
            if not unseen:
                return 1, []
        with self.transaction(write=(mode == "new")) as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM messages ORDER BY seq")]
            if role == "reviewer" and any(row["kind"] == "close" for row in rows):
                return 3, []
            incoming = [row for row in rows if row["receiver"] == role]
            if mode == "request":
                answered = {row["reply_to"] for row in rows if row["sender"] == role}
                found = [row for row in incoming if row["kind"] in (*REQUESTS, "rebut")
                         and row["id"] not in answered]
            elif mode == "reply":
                found = [row for row in incoming if row["reply_to"] == target]
            else:
                cursor = conn.execute("SELECT seq FROM cursors WHERE role=?", (role,)).fetchone()
                seen = cursor[0] if cursor else 0
                found = [row for row in incoming if row["seq"] > seen]
                if found:
                    conn.execute("INSERT OR REPLACE INTO cursors VALUES (?,?)",
                                 (role, found[-1]["seq"]))
            return (0 if found else 1), found

    def wait(self, role, mode, target=None, *, seconds=120, poll=0.25):
        if not math.isfinite(seconds) or not math.isfinite(poll) or seconds < 0 or poll <= 0:
            raise ValueError("The wait must be 0 or more seconds and the poll interval positive.")
        deadline = time.monotonic() + seconds
        while True:
            code, rows = self.find(role, mode, target)
            if code != 1 or time.monotonic() >= deadline:
                return code, rows
            time.sleep(min(poll, max(0, deadline - time.monotonic())))

    def export(self):
        with self.transaction(write=False) as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM messages ORDER BY seq")]


def render(rows, as_json=False):
    if as_json:
        return json.dumps(rows, ensure_ascii=False, indent=2)
    blocks = []
    for row in rows:
        kind = row["kind"] + (f" {row['reply_to']}" if row["reply_to"] else "")
        head = f"## {row['id']} | {row['sender']} → {row['receiver']} | {kind} | {row['at']}"
        if row["snap"]:
            head += f" | snap {row['snap']}"
        # Quote every body line. A body cannot masquerade as another message header.
        blocks.append(head + "\n\n" + "\n".join("> " + line for line in row["body"].splitlines()))
    return "\n\n".join(blocks)
