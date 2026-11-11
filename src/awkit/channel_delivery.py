"""Host-local delivery receipts for a bound remote channel participant."""

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .channel import REQUESTS, ROLES, Channel, protocol_state

SEGMENT_CHARS = 4096
BODY_BYTES = 65536
PAGE_SIZE = 20
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS channel_delivery_instance (singleton INTEGER PRIMARY KEY CHECK(singleton=1), id TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS channel_delivery_posts (sender TEXT, key TEXT, digest TEXT NOT NULL, message_id TEXT NOT NULL, PRIMARY KEY(sender,key))",
    "CREATE TABLE IF NOT EXISTS channel_delivery_consumers (role TEXT, consumer TEXT, seq INTEGER NOT NULL DEFAULT 0, offset INTEGER NOT NULL DEFAULT 0, receipt TEXT, delivery_seq INTEGER, delivery_end INTEGER, delivery_total INTEGER, last_ack TEXT, PRIMARY KEY(role,consumer))",
)


def identifier(value, label):
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or not all(
        c.isascii() and (c.isalnum() or c in "-_.:") for c in value
    ):
        raise ValueError(f"{label} must be 1-128 ASCII letters, digits or -_.:")
    return value


class Delivery:
    def __init__(self, path, role, consumer):
        path = Path(path)
        if not path.is_absolute():
            raise ValueError("serve requires an absolute channel path")
        if role not in ROLES:
            raise ValueError("Unknown channel role")
        self.path = path.resolve(strict=True)
        self.role = role
        self.peer = "reviewer" if role == "main" else "main"
        self.consumer = identifier(consumer, "consumer")
        self.instance = None
        self.channel = Channel(self.path, project=self.path.parent)
        with self.transaction(write=True, initialize=True) as conn:
            for statement in SCHEMA:
                conn.execute(statement)
            conn.execute("INSERT OR IGNORE INTO channel_delivery_instance VALUES (1,?)", (uuid.uuid4().hex,))
            self.instance = conn.execute("SELECT id FROM channel_delivery_instance WHERE singleton=1").fetchone()[0]

    @contextmanager
    def transaction(self, *, write=False, initialize=False):
        # mode=rw never creates a replacement if the configured file disappears.
        conn = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if conn.execute("PRAGMA user_version").fetchone()[0] != 2:
                raise ValueError("serve requires an existing schema-2 channel")
            conn.execute("SELECT seq,id,sender,receiver,kind,reply_to,snap,at,body FROM messages LIMIT 0")
            conn.execute("SELECT role,consumer,seq FROM cursors LIMIT 0")
            if not initialize:
                try:
                    row = conn.execute("SELECT id FROM channel_delivery_instance WHERE singleton=1").fetchone()
                except sqlite3.Error as exc:
                    raise ValueError("Channel instance missing or changed; explicitly rebind and restart") from exc
                if row is None or row[0] != self.instance:
                    raise ValueError("Channel instance changed; explicitly rebind and restart the server")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    @staticmethod
    def closed(conn):
        return bool(conn.execute("SELECT 1 FROM messages WHERE kind='close'").fetchone())

    def result(self, **values):
        return {"channel_id": self.instance, **values}

    def post(self, channel_id, key, kind, body, reply_to=None, snap=None):
        if channel_id != self.instance:
            raise ValueError("Caller channel_id does not match; recover the intended channel before sending")
        identifier(key, "idempotency key")
        if not isinstance(body, str) or len(body.encode("utf-8")) > BODY_BYTES:
            raise ValueError("body must be text of at most 65536 UTF-8 bytes")
        if not isinstance(kind, str) or any(v is not None and not isinstance(v, str) for v in (reply_to, snap)):
            raise ValueError("kind, reply_to and snap must be strings")
        payload = json.dumps([kind, body, reply_to, snap], ensure_ascii=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with self.transaction(write=True) as conn:
            old = conn.execute("SELECT digest,message_id FROM channel_delivery_posts WHERE sender=? AND key=?",
                               (self.role, key)).fetchone()
            if old:
                if old["digest"] != digest:
                    raise ValueError("Idempotency key already used with another payload")
                return self.result(message_id=old["message_id"], duplicate=True)
            message_id = self.channel._post(conn, self.role, self.peer, kind, body, reply_to=reply_to, snap=snap)
            conn.execute("INSERT INTO channel_delivery_posts VALUES (?,?,?,?)", (self.role, key, digest, message_id))
            return self.result(message_id=message_id, duplicate=False)

    @staticmethod
    def segment(row, offset):
        message = dict(row)
        body = message.pop("body")
        if type(offset) is not int or not 0 <= offset <= len(body):
            raise ValueError("Invalid message offset")
        end = min(len(body), offset + SEGMENT_CHARS)
        message["body"] = body[offset:end]
        return {"message": message, "offset": offset, "next_offset": end,
                "total_chars": len(body), "complete": end == len(body)}

    def read(self):
        with self.transaction(write=True) as conn:
            conn.execute("INSERT OR IGNORE INTO channel_delivery_consumers(role,consumer) VALUES (?,?)",
                         (self.role, self.consumer))
            state = conn.execute("SELECT * FROM channel_delivery_consumers WHERE role=? AND consumer=?",
                                 (self.role, self.consumer)).fetchone()
            closed = self.closed(conn)
            if state["receipt"]:
                row = conn.execute("SELECT * FROM messages WHERE receiver=? AND seq=?",
                                   (self.role, state["delivery_seq"])).fetchone()
                if row is None:
                    raise ValueError("Outstanding channel message is missing")
            else:
                row = conn.execute("SELECT * FROM messages WHERE receiver=? AND seq>? ORDER BY seq LIMIT 1",
                                   (self.role, state["seq"])).fetchone()
            if row is None:
                return self.result(closed=closed, receipt=None, segment=None)
            segment = self.segment(row, state["offset"])
            receipt = state["receipt"] or uuid.uuid4().hex
            if state["receipt"]:
                if (segment["next_offset"], segment["total_chars"]) != (state["delivery_end"], state["delivery_total"]):
                    raise ValueError("Outstanding channel message changed")
            else:
                conn.execute("UPDATE channel_delivery_consumers SET receipt=?,delivery_seq=?,delivery_end=?,delivery_total=? WHERE role=? AND consumer=?",
                             (receipt, row["seq"], segment["next_offset"], segment["total_chars"], self.role, self.consumer))
            return self.result(closed=closed, receipt=receipt, segment=segment)

    def ack(self, receipt):
        identifier(receipt, "receipt")
        with self.transaction(write=True) as conn:
            state = conn.execute("SELECT * FROM channel_delivery_consumers WHERE role=? AND consumer=?",
                                 (self.role, self.consumer)).fetchone()
            if state and state["last_ack"] == receipt:
                return self.result(acknowledged=True, duplicate=True)
            if not state or state["receipt"] != receipt:
                raise ValueError("Unknown or stale receipt for this consumer")
            complete = state["delivery_end"] == state["delivery_total"]
            conn.execute("UPDATE channel_delivery_consumers SET seq=?,offset=?,last_ack=?,receipt=NULL,delivery_seq=NULL,delivery_end=NULL,delivery_total=NULL WHERE role=? AND consumer=?",
                         (state["delivery_seq"] if complete else state["seq"],
                          0 if complete else state["delivery_end"], receipt, self.role, self.consumer))
            return self.result(acknowledged=True, duplicate=False)

    def message(self, message_id, offset=0):
        if not isinstance(message_id, str):
            raise ValueError("message_id must be text")
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM messages WHERE id=? AND receiver=?", (message_id, self.role)).fetchone()
            if row is None:
                raise ValueError("Incoming message not found in this channel")
            return self.result(closed=self.closed(conn), segment=self.segment(row, offset))

    def requests(self, after_seq=0):
        if type(after_seq) is not int or after_seq < 0:
            raise ValueError("after_seq must be a nonnegative integer")
        with self.transaction() as conn:
            rows = [dict(row) for row in conn.execute("SELECT seq,id,sender,receiver,kind,reply_to,snap,at FROM messages ORDER BY seq")]
            answered = protocol_state(rows)["answered"]
            found = [row for row in rows if row["receiver"] == self.role and row["seq"] > after_seq
                     and row["kind"] in (*REQUESTS, "rebut") and row["id"] not in answered]
            page = found[:PAGE_SIZE]
            return self.result(closed=self.closed(conn), requests=page, next_after=page[-1]["seq"] if len(found) > PAGE_SIZE else None)
