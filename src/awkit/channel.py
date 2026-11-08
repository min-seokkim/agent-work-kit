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

from .local_state import prepare

# The failure catalogue entries (kit/failures.md) this command guards against: reviews of an unnamed
# version, closing with outstanding responses, and readers losing messages.
PREVENTS = {"awkit channel": ("F1", "F29"), "awkit channel status": ("F29",)}

ROLES = ("main", "reviewer")
REQUESTS = ("review", "scout", "test", "draft", "question", "final")
KINDS = (*REQUESTS, "notice", "close", "re", "rebut", "withdraw")
VERSION = 2
SHARED_CONSUMER = ""  # Reserved for callers that omit --consumer, including migrated cursors.
ID = re.compile(r"[MR]-[0-9]{3,}\Z")


SCHEMA = """
    CREATE TABLE IF NOT EXISTS messages (
        seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
        sender TEXT NOT NULL, receiver TEXT NOT NULL,
        kind TEXT NOT NULL, reply_to TEXT, snap TEXT,
        at TEXT NOT NULL, body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cursors (
        role TEXT NOT NULL, consumer TEXT NOT NULL, seq INTEGER NOT NULL,
        PRIMARY KEY (role, consumer));
"""


def protocol_state(rows):
    """Compute effective replies and closure obligations from one database snapshot."""
    by_id = {row["id"]: row for row in rows}
    withdrawals = [row for row in rows if row["kind"] == "withdraw"]
    withdrawn = {row["reply_to"] for row in withdrawals}
    replies = [row for row in rows if row["kind"] == "re"
               and row["id"] not in withdrawn and row["reply_to"] not in withdrawn]
    answered = {row["reply_to"] for row in replies}
    verdicts = {row["id"] for row in replies if row["sender"] == "reviewer"
                and by_id[row["reply_to"]]["kind"] in ("review", "final")}
    blockers = {
        "unanswered-request": [row["id"] for row in rows
                               if row["kind"] in REQUESTS and row["id"] not in answered],
        "unanswered-rebuttal": [row["id"] for row in rows
                                if row["kind"] == "rebut" and row["id"] not in answered],
        "unacknowledged-verdict": [row["id"] for row in replies
                                   if row["id"] in verdicts and row["id"] not in answered],
        "unresolved-withdrawal": [row["id"] for row in withdrawals if not any(
            reply["sender"] == "reviewer" and reply["seq"] > row["seq"]
            and reply["reply_to"] == by_id[row["reply_to"]]["reply_to"] for reply in replies)],
    }
    return dict(withdrawn=withdrawn, replies=replies, answered=answered,
                verdicts=verdicts, blockers=blockers)


def validate_reply(parent, sender, receiver, kind):
    if kind == "withdraw":
        if (sender != "reviewer" or not parent or parent["kind"] != "re"
                or parent["sender"] != sender or parent["receiver"] != receiver):
            raise ValueError("withdraw must reference the reviewer's own re sent to main.")
    elif not parent or parent["sender"] != receiver or parent["receiver"] != sender:
        raise ValueError("A reply must answer a message the other side sent.")


class Channel:
    def __init__(self, path: Path, *, project=None):
        self.path = Path(path)
        self.project = Path.cwd() if project is None else Path(project)
        self._ready = False

    def _prepare(self, conn):
        # Create the schema once per process; later calls skip straight to the query.
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version in (0, 1):
            conn.execute("BEGIN IMMEDIATE")
            try:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                if version == 0:
                    for statement in SCHEMA.split(";"):
                        if statement.strip():
                            conn.execute(statement)
                elif version == 1:
                    conn.execute("ALTER TABLE cursors RENAME TO cursors_v1")
                    conn.execute("CREATE TABLE cursors (role TEXT NOT NULL, consumer TEXT NOT NULL, "
                                 "seq INTEGER NOT NULL, PRIMARY KEY (role, consumer))")
                    conn.execute("INSERT INTO cursors SELECT role, ?, seq FROM cursors_v1",
                                 (SHARED_CONSUMER,))
                    conn.execute("DROP TABLE cursors_v1")
                if version not in (0, 1, VERSION):
                    raise ValueError("Unsupported channel database version.")
                conn.execute(f"PRAGMA user_version={VERSION}")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != VERSION:
            raise ValueError("Unsupported channel database version.")
        self._ready = True

    @contextmanager
    def transaction(self, write=True):
        """Writers take the lock up front; readers use a shared lock and never block each other."""
        needs_write = write or not self.path.is_file()
        if not needs_write and not self._ready:
            probe = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                needs_write = probe.execute("PRAGMA user_version").fetchone()[0] in (0, 1)
            finally:
                probe.close()
        if needs_write:
            prepare(self.project, self.path)
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

    @staticmethod
    def _validate_post(sender, receiver, kind, body, reply_to=None, snap=None):
        if not isinstance(body, str) or not body.strip():
            raise ValueError("The message body is empty.")
        if sender not in ROLES or receiver not in ROLES or sender == receiver:
            raise ValueError("Messages go between main and reviewer only.")
        if kind not in KINDS or (kind == "close" and sender != "main"):
            raise ValueError("Unknown message kind, or close was not sent by main.")
        if kind == "withdraw" and sender != "reviewer":
            raise ValueError("Only reviewer can withdraw a response.")
        if (kind in ("re", "rebut", "withdraw")) != bool(reply_to):
            raise ValueError("re, rebut and withdraw require --reply-to; other kinds do not take it.")
        if reply_to and not ID.fullmatch(reply_to):
            raise ValueError("Invalid reply target ID.")
        if snap and not re.fullmatch(r"[0-9a-f]{7,64}", snap):
            raise ValueError("A snapshot ID is 7 to 64 lowercase hex characters.")

    def _post(self, conn, sender, receiver, kind, body, *, reply_to=None, snap=None):
        """Insert inside an existing transaction, including managed delivery correlation."""
        self._validate_post(sender, receiver, kind, body, reply_to, snap)
        if conn.execute("SELECT 1 FROM messages WHERE kind='close'").fetchone():
            raise ValueError("This channel is closed. Use another database path for new work.")
        if reply_to:
            parent = conn.execute(
                "SELECT * FROM messages WHERE id=?", (reply_to,)
            ).fetchone()
            validate_reply(parent, sender, receiver, kind)
        if kind == "close":
            state = protocol_state(list(conn.execute("SELECT * FROM messages ORDER BY seq")))
            pending = [f"{kind}: {', '.join(ids)}" for kind, ids in state["blockers"].items() if ids]
            if pending:
                raise ValueError("Cannot close channel; " + "; ".join(pending))
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

    def post(self, sender, receiver, kind, body, *, reply_to=None, snap=None):
        self._validate_post(sender, receiver, kind, body, reply_to, snap)
        with self.transaction() as conn:
            return self._post(conn, sender, receiver, kind, body, reply_to=reply_to, snap=snap)

    def find(self, role, mode, target=None, *, consumer=None):
        if role not in ROLES or mode not in ("request", "new", "reply", "peek"):
            raise ValueError("Unknown role or wait mode.")
        if consumer is not None and (mode != "new" or not isinstance(consumer, str) or not consumer.strip()):
            raise ValueError("--consumer requires a nonempty ID and new mode.")
        consumer = SHARED_CONSUMER if consumer is None else consumer
        if mode == "reply" and (not target or not ID.fullmatch(target)):
            raise ValueError("reply mode requires a message ID.")
        if mode != "reply" and target:
            raise ValueError("A message ID is accepted in reply mode only.")
        if mode == "new":
            # Check under a read lock first so idle waiters never queue for the write lock.
            with self.transaction(write=False) as conn:
                closed = role == "reviewer" and conn.execute(
                    "SELECT 1 FROM messages WHERE kind='close'").fetchone()
                cursor = conn.execute("SELECT seq FROM cursors WHERE role=? AND consumer=?",
                                      (role, consumer)).fetchone()
                unseen = conn.execute("SELECT 1 FROM messages WHERE receiver=? AND seq>?",
                                      (role, cursor[0] if cursor else 0)).fetchone()
            if closed:
                return 3, []
            if not unseen:
                return 1, []
        with self.transaction(write=(mode == "new")) as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM messages ORDER BY seq")]
            if mode != "peek" and role == "reviewer" and any(row["kind"] == "close" for row in rows):
                return 3, []
            incoming = [row for row in rows if row["receiver"] == role]
            if mode == "request":
                answered = protocol_state(rows)["answered"]
                found = [row for row in incoming if row["kind"] in (*REQUESTS, "rebut")
                         and row["id"] not in answered]
            elif mode == "reply":
                withdrawn = protocol_state(rows)["withdrawn"]
                found = [row for row in incoming if row["reply_to"] == target
                         and row["id"] not in withdrawn
                         and not (row["kind"] == "re" and target in withdrawn)]
            elif mode == "peek":
                found = incoming
            else:
                cursor = conn.execute("SELECT seq FROM cursors WHERE role=? AND consumer=?",
                                      (role, consumer)).fetchone()
                seen = cursor[0] if cursor else 0
                found = [row for row in incoming if row["seq"] > seen]
                if found:
                    conn.execute("INSERT OR REPLACE INTO cursors VALUES (?,?,?)",
                                 (role, consumer, found[-1]["seq"]))
            return (0 if found else 1), found

    def wait(self, role, mode, target=None, *, seconds=120, poll=0.25, consumer=None):
        if not math.isfinite(seconds) or not math.isfinite(poll) or seconds < 0 or poll <= 0:
            raise ValueError("The wait must be 0 or more seconds and the poll interval positive.")
        deadline = time.monotonic() + seconds
        while True:
            code, rows = self.find(role, mode, target, consumer=consumer)
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
