"""Managed runtime projections beside authoritative schema-1 channel exchanges."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .channel import REQUESTS, Channel

SCHEMA = """
CREATE TABLE awkit_session (singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    schema INTEGER NOT NULL, id TEXT UNIQUE NOT NULL, data TEXT NOT NULL);
CREATE TABLE awkit_posts (key TEXT PRIMARY KEY, message_id TEXT UNIQUE NOT NULL,
    entry TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE awkit_delivery (id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
    generation TEXT NOT NULL, native_id TEXT, rpc_id TEXT, turn_id TEXT, reply_id TEXT,
    state TEXT NOT NULL, outcome TEXT, error TEXT, created TEXT NOT NULL, updated TEXT NOT NULL,
    origin_generation TEXT, client_id TEXT, interruption_requested TEXT,
    provider_input_id TEXT, input_echoed INTEGER, provider_result_id TEXT);
CREATE TABLE awkit_cancellations (request_id TEXT PRIMARY KEY, created TEXT NOT NULL, disposition TEXT NOT NULL);
CREATE TABLE awkit_events (seq INTEGER PRIMARY KEY, key TEXT UNIQUE NOT NULL,
    generation TEXT NOT NULL, method TEXT NOT NULL, thread_id TEXT, turn_id TEXT,
    item_id TEXT, at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE awkit_decisions (id TEXT PRIMARY KEY, generation TEXT NOT NULL,
    rpc_id TEXT NOT NULL, method TEXT NOT NULL, params TEXT NOT NULL, choices TEXT NOT NULL,
    state TEXT NOT NULL, response TEXT, created TEXT NOT NULL, updated TEXT NOT NULL);
"""


def now():
    return datetime.now(UTC).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class SessionStore:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_file():
            raise ValueError("Managed session channel does not exist.")
        conn = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            if conn.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("Managed channels require the existing core schema 1.")
            self._metadata(conn)
        finally:
            conn.close()
        self.channel = Channel(self.path)

    @classmethod
    def create(cls, directory, *, name, project, responsibility, generation, permissions, provider="codex", enrollment=None):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        ident = str(uuid.uuid4())
        path = directory / f"{ident}.sqlite3"
        # Exclusive creation prevents replacement of an existing channel.
        with path.open("xb"):
            pass
        channel = Channel(path)
        data = dict(id=ident, name=name, provider=provider, project=str(Path(project).resolve()),
                    responsibility=responsibility, native_id=None, generation=generation,
                    permissions=permissions, state="creating", observed_at=now(),
                    source="local creation intent", error=None)
        if enrollment is not None:
            data["enrollment"] = enrollment
            data["startup_context"] = None
        with channel.transaction() as conn:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute("INSERT INTO awkit_session VALUES (1,?,?,?)", (4 if enrollment is not None else 3, ident, encoded(data)))
        return cls(path)

    @staticmethod
    def _metadata(conn):
        try:
            row = conn.execute("SELECT schema,id,data FROM awkit_session WHERE singleton=1").fetchone()
        except sqlite3.OperationalError as exc:
            raise ValueError("This is not a managed session channel.") from exc
        if row is None or row["schema"] not in (1, 2, 3, 4):
            raise ValueError("Unsupported managed session extension.")
        data = json.loads(row["data"])
        if row["schema"] != 4 and data.get("enrollment") is not None:
            raise ValueError("Enrolled Codex conversations require extension 4.")
        if row["schema"] == 4 and (data.get("provider") != "codex" or not isinstance(data.get("enrollment"), dict)):
            raise ValueError("Invalid enrolled Codex metadata.")
        if data.get("id") != row["id"] or str(uuid.UUID(row["id"])) != row["id"]:
            raise ValueError("Invalid stored session/channel identity.")
        return data

    def upgrade(self):
        """Explicit managed-only migration; caller holds the project controller lock."""
        with self.channel.transaction() as conn:
            version = conn.execute("SELECT schema FROM awkit_session WHERE singleton=1").fetchone()[0]
            if version == 1:
                for field in ("origin_generation", "client_id", "interruption_requested"):
                    conn.execute(f"ALTER TABLE awkit_delivery ADD COLUMN {field} TEXT")
                conn.execute("UPDATE awkit_delivery SET origin_generation=generation")
                conn.execute("CREATE TABLE awkit_cancellations (request_id TEXT PRIMARY KEY, "
                             "created TEXT NOT NULL, disposition TEXT NOT NULL)")
                conn.execute("UPDATE awkit_session SET schema=2 WHERE singleton=1")
                version = 2
            if version == 2:
                conn.execute("ALTER TABLE awkit_delivery RENAME TO awkit_delivery_v2")
                statement = next(part for part in SCHEMA.split(";") if "CREATE TABLE awkit_delivery " in part)
                conn.execute(statement)
                columns = [row[1] for row in conn.execute("PRAGMA table_info(awkit_delivery_v2)")]
                names = ",".join(columns)
                conn.execute(f"INSERT INTO awkit_delivery({names}) SELECT {names} FROM awkit_delivery_v2")
                conn.execute("DROP TABLE awkit_delivery_v2")
                conn.execute("UPDATE awkit_session SET schema=3 WHERE singleton=1")

    @staticmethod
    def _update(conn, **fields):
        data = SessionStore._metadata(conn)
        data.update(fields)
        conn.execute("UPDATE awkit_session SET data=? WHERE singleton=1", (encoded(data),))
        return data

    def metadata(self):
        with self.channel.transaction(write=False) as conn:
            return self._metadata(conn)

    def update(self, **fields):
        with self.channel.transaction() as conn:
            return self._update(conn, **fields)

    def post(self, key, body, *, kind="question", entry="agent"):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", key):
            raise ValueError("A client key contains 1 to 200 letters, digits, underscores or hyphens.")
        if kind not in (*REQUESTS, "notice") or entry not in ("agent", "human"):
            raise ValueError("Unsupported session message kind or entry.")
        self.channel._validate_post("main", "reviewer", kind, body)
        with self.channel.transaction() as conn:
            existing = conn.execute("SELECT m.* FROM awkit_posts p JOIN messages m ON m.id=p.message_id "
                                    "WHERE p.key=?", (key,)).fetchone()
            if existing:
                if existing["body"] != body or existing["kind"] != kind:
                    raise ValueError("This client key already names a different message.")
                return dict(existing)
            message = self.channel._post(conn, "main", "reviewer", kind, body)
            conn.execute("INSERT INTO awkit_posts VALUES (?,?,?,?)", (key, message, entry, now()))
            return dict(conn.execute("SELECT * FROM messages WHERE id=?", (message,)).fetchone())

    def claim(self, generation):
        """Reserve one idle request durably before the provider can see it."""
        with self.channel.transaction() as conn:
            data = self._metadata(conn)
            if (data["generation"] != generation or data["state"] != "idle"
                    or not (data["native_id"] or data.get("requested_native_id"))):
                return None
            if self._active(conn, generation) is not None:
                return None
            if conn.execute("SELECT 1 FROM messages WHERE kind='close'").fetchone():
                return None
            placeholders = ",".join("?" for _ in REQUESTS)
            request = conn.execute(
                f"SELECT m.* FROM messages m WHERE m.receiver='reviewer' AND m.kind IN ({placeholders}) "
                "AND NOT EXISTS(SELECT 1 FROM messages r WHERE r.sender='reviewer' AND r.reply_to=m.id) "
                "AND NOT EXISTS(SELECT 1 FROM awkit_delivery d WHERE d.request_id=m.id) "
                "AND NOT EXISTS(SELECT 1 FROM awkit_cancellations c WHERE c.request_id=m.id) ORDER BY m.seq LIMIT 1",
                REQUESTS).fetchone()
            if request is None:
                return None
            ident, at = str(uuid.uuid4()), now()
            conn.execute("INSERT INTO awkit_delivery(id,request_id,generation,native_id,state,created,updated,origin_generation,client_id,provider_input_id) "
                         "VALUES (?,?,?,?,'admitting',?,?,?,?,?)",
                         (ident, request["id"], generation, data["native_id"], at, at, generation, ident,
                          ident if data["provider"] == "claude" else None))
            self._update(conn, state="submitting", observed_at=at, source="durable local send intent")
            return dict(id=ident, request=dict(request), native_id=data["native_id"], generation=generation)

    @staticmethod
    def _active(conn, generation):
        return conn.execute("SELECT * FROM awkit_delivery WHERE generation=? AND state IN "
                            "('admitting','accepted','executing','uncertain') ORDER BY created DESC LIMIT 1",
                            (generation,)).fetchone()

    def bind_turn(self, generation, turn_id, *, executing=False):
        if not isinstance(turn_id, str) or not turn_id:
            raise ValueError("Provider did not return a turn identity.")
        with self.channel.transaction() as conn:
            row = self._active(conn, generation)
            if row is None or row["turn_id"] not in (None, turn_id):
                return False
            state = "executing" if executing or row["state"] == "executing" else "accepted"
            conn.execute("UPDATE awkit_delivery SET turn_id=?,state=?,updated=? WHERE id=?",
                         (turn_id, state, now(), row["id"]))
            self._update(conn, state="running" if state == "executing" else "accepted", observed_at=now(),
                         source="turn/started" if executing else "turn/start response")
            return True

    def uncertain(self, generation, error):
        with self.channel.transaction() as conn:
            row = self._active(conn, generation)
            if row:
                conn.execute("UPDATE awkit_delivery SET state='uncertain',error=?,updated=? WHERE id=?",
                             (str(error), now(), row["id"]))
            self._update(conn, state="unknown", observed_at=now(), source="connection/RPC uncertainty", error=str(error))

    def event(self, generation, method, params):
        payload = encoded(params)
        key = hashlib.sha256(encoded([generation, method, params]).encode()).hexdigest()
        item = params.get("item", {})
        turn = params.get("turn", {})
        with self.channel.transaction() as conn:
            conn.execute("INSERT OR IGNORE INTO awkit_events(key,generation,method,thread_id,turn_id,item_id,at,payload) "
                         "VALUES (?,?,?,?,?,?,?,?)", (key, generation, method, params.get("threadId"),
                                                     params.get("turnId", turn.get("id")), item.get("id"), now(), payload))

    def turn_updates(self):
        """Local intent/result events; these are not independent channel assignments."""
        with self.channel.transaction(write=False) as conn:
            return self._turn_updates(conn)

    @staticmethod
    def _turn_updates(conn):
        intents = {}
        for row in conn.execute("SELECT method,payload FROM awkit_events WHERE method IN "
                                "('awkit/turnUpdateIntent','awkit/turnUpdateResult') ORDER BY seq"):
            value = json.loads(row["payload"])
            if row["method"] == "awkit/turnUpdateIntent":
                intents[value["id"]] = value
            elif value["id"] in intents:
                intents[value["id"]].update(value)
        return list(intents.values())

    def turn_update_intent(self, generation, *, key, request_id, expected_turn_id, body, entry):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", key):
            raise ValueError("An update key contains 1 to 200 letters, digits, underscores or hyphens.")
        if entry not in ("agent", "human"):
            raise ValueError("Unsupported update entry.")
        self.channel._validate_post("main", "reviewer", "notice", body)
        with self.channel.transaction() as conn:
            meta = self._metadata(conn)
            active = self._active(conn, generation)
            if (meta["provider"] != "codex" or meta["generation"] != generation or active is None
                    or active["state"] not in ("accepted", "executing") or not expected_turn_id
                    or active["turn_id"] != expected_turn_id or active["request_id"] != request_id
                    or active["native_id"] != meta["native_id"]
                    or conn.execute("SELECT 1 FROM messages WHERE kind='close'").fetchone()):
                raise ValueError("Select the exact observed active Codex assignment and turn; no update was sent.")
            value = dict(id=str(uuid.uuid4()), key=key, request_id=request_id, attempt_id=active["id"],
                         generation=generation, native_id=meta["native_id"], expected_turn_id=expected_turn_id,
                         body=body, entry=entry, created=now(), state="uncertain",
                         source="durable intent; native admission not established")
            conn.execute("INSERT INTO awkit_events(key,generation,method,thread_id,turn_id,at,payload) "
                         "VALUES (?,?,?,?,?,?,?)", ("local:turn-update:" + key, generation, "awkit/turnUpdateIntent",
                         meta["native_id"], expected_turn_id, value["created"], encoded(value)))
            return value

    def finish(self, generation, turn_id, outcome, text, error=None):
        with self.channel.transaction() as conn:
            row = conn.execute("SELECT * FROM awkit_delivery WHERE generation=? AND turn_id=?",
                               (generation, turn_id)).fetchone()
            return self._finish(conn, row, outcome, text, error, "turn/completed")

    def _finish(self, conn, row, outcome, text, error, source, *, next_state="idle"):
        if row is None or row["state"] in ("returned", "failed", "no-reply"):
            return False
        reply = None
        if text.strip():
            reply = self.channel._post(conn, "reviewer", "main", "re", text, reply_to=row["request_id"])
        state = "returned" if reply else "failed" if outcome == "failed" else "no-reply"
        conn.execute("UPDATE awkit_delivery SET state=?,outcome=?,reply_id=?,error=?,updated=? WHERE id=?",
                     (state, outcome, reply, encoded(error) if error else None, now(), row["id"]))
        self._update(conn, state=next_state, observed_at=now(), source=source, error=error)
        return True

    def claude_echo(self, generation, input_id, native_id):
        with self.channel.transaction() as conn:
            row = self._active(conn, generation)
            if row is None or row["provider_input_id"] != input_id:
                return False
            conn.execute("UPDATE awkit_delivery SET input_echoed=1,native_id=?,state='executing',updated=? WHERE id=?",
                         (native_id, now(), row["id"]))
            self._update(conn, state="running", observed_at=now(), source="Claude input UUID echo")
            return True

    def claude_finish(self, generation, input_id, result_id, outcome, text, error=None, *, idle_observed=False):
        with self.channel.transaction() as conn:
            row = conn.execute("SELECT * FROM awkit_delivery WHERE generation=? AND provider_input_id=? AND input_echoed=1",
                               (generation, input_id)).fetchone()
            if row is None or row["state"] in ("returned", "failed", "no-reply"):
                return False
            if result_id and conn.execute("SELECT 1 FROM awkit_delivery WHERE provider_result_id=? AND id!=?",
                                          (result_id, row["id"])).fetchone():
                return False
            conn.execute("UPDATE awkit_delivery SET provider_result_id=?,native_id=? WHERE id=?",
                         (result_id, self._metadata(conn)["native_id"], row["id"]))
            for decision in conn.execute("SELECT id,params FROM awkit_decisions WHERE generation=? AND state='sending'", (generation,)).fetchall():
                params = json.loads(decision["params"])
                if params.get("provider_input_id") == input_id and params.get("agent_id") is None:
                    params["resolution_source"] = "correlated native parent result; response effect is not inferred"
                    conn.execute("UPDATE awkit_decisions SET state='resolved',params=?,updated=? WHERE id=?",
                                 (encoded(params), now(), decision["id"]))
            return self._finish(conn, row, outcome, text, error, "Claude correlated result; native idle " +
                                ("observed" if idle_observed else "awaited"), next_state="idle" if idle_observed else "waiting for idle")

    def add_decision(self, generation, rpc_id, method, params, choices):
        callback = hashlib.sha256(encoded([method, params.get("threadId"), params.get("turnId"),
                                          params.get("itemId"), params.get("approvalId"), params.get("startedAtMs")]).encode()).hexdigest()
        ident = f"{generation}:{encoded(rpc_id)}:{callback}"
        with self.channel.transaction() as conn:
            conn.execute("INSERT OR IGNORE INTO awkit_decisions VALUES (?,?,?,?,?,?,'pending',NULL,?,?)",
                         (ident, generation, encoded(rpc_id), method, encoded(params), encoded(choices), now(), now()))
            self._update(conn, state="decision needed", observed_at=now(), source=method)
        return ident

    def resolve_decisions(self, generation, rpc_id, thread_id):
        with self.channel.transaction() as conn:
            rows = conn.execute("SELECT id,params FROM awkit_decisions WHERE generation=? AND rpc_id=? "
                                "AND state IN ('pending','sending','sent','uncertain')", (generation, encoded(rpc_id))).fetchall()
            for row in rows:
                if json.loads(row["params"]).get("threadId") == thread_id:
                    conn.execute("UPDATE awkit_decisions SET state='resolved',updated=? WHERE id=?", (now(), row["id"]))

    def answer_intent(self, generation, ident, response):
        with self.channel.transaction() as conn:
            row = conn.execute("SELECT * FROM awkit_decisions WHERE id=? AND generation=?",
                               (ident, generation)).fetchone()
            if row is None or row["state"] != "pending":
                raise ValueError("This provider decision is no longer pending on this connection.")
            conn.execute("UPDATE awkit_decisions SET response=?,state='sending',updated=? WHERE id=?",
                         (encoded(response), now(), ident))
            return dict(row)

    def decision_state(self, ident, state):
        with self.channel.transaction() as conn:
            conn.execute("UPDATE awkit_decisions SET state=?,updated=? WHERE id=? AND state!='resolved'",
                         (state, now(), ident))

    def cancel(self, request_id):
        with self.channel.transaction() as conn:
            request = conn.execute("SELECT * FROM messages WHERE id=? AND receiver='reviewer'", (request_id,)).fetchone()
            if request is None or request["kind"] not in REQUESTS:
                raise ValueError("Select an original assignment in this conversation.")
            attempt = conn.execute("SELECT * FROM awkit_delivery WHERE request_id=?", (request_id,)).fetchone()
            disposition = "after-dispatch" if attempt else "before-dispatch"
            conn.execute("INSERT OR IGNORE INTO awkit_cancellations VALUES (?,?,?)", (request_id, now(), disposition))
            return dict(request_id=request_id, state="cancelled before dispatch" if not attempt else
                        "stop requested; delivery and provider outcome remain separate", disposition=disposition)

    def reconnect(self, generation):
        """Keep provenance while moving unfinished attempts onto the new owned route."""
        with self.channel.transaction() as conn:
            conn.execute("UPDATE awkit_delivery SET generation=?,state='unresolved',updated=? "
                         "WHERE state IN ('admitting','accepted','executing','uncertain','unresolved')", (generation, now()))
            conn.execute("UPDATE awkit_decisions SET state='route unavailable',updated=? "
                         "WHERE generation!=? AND state IN ('pending','sending','sent','uncertain')", (now(), generation))

    def recover_turn(self, generation, attempt_id, turn_id, *, running=False):
        with self.channel.transaction() as conn:
            conn.execute("UPDATE awkit_delivery SET generation=?,turn_id=?,state=?,updated=? WHERE id=? "
                         "AND state='unresolved'", (generation, turn_id, "executing" if running else "accepted", now(), attempt_id))

    def interruption(self, generation, turn_id):
        with self.channel.transaction() as conn:
            conn.execute("UPDATE awkit_delivery SET interruption_requested=?,updated=? "
                         "WHERE generation=? AND turn_id=?", (now(), now(), generation, turn_id))

    def snapshot(self):
        with self.channel.transaction(write=False) as conn:
            messages = [dict(row) for row in conn.execute("SELECT * FROM messages ORDER BY seq")]
            attempts = [dict(row) for row in conn.execute("SELECT * FROM awkit_delivery ORDER BY created")]
            version = conn.execute("SELECT schema FROM awkit_session WHERE singleton=1").fetchone()[0]
            cancellations = [dict(row) for row in conn.execute("SELECT * FROM awkit_cancellations")] if version >= 2 else []
            posts = [dict(row) for row in conn.execute("SELECT * FROM awkit_posts ORDER BY created")]
            decisions = []
            for row in conn.execute("SELECT * FROM awkit_decisions ORDER BY created"):
                value = dict(row)
                for key in ("rpc_id", "params", "choices", "response"):
                    value[key] = json.loads(value[key]) if value[key] is not None else None
                decisions.append(value)
            events = [dict(row) for row in conn.execute("SELECT * FROM awkit_events ORDER BY seq DESC LIMIT 30")]
            replied = {row["reply_to"] for row in messages if row["sender"] == "reviewer"}
            unanswered = [row["id"] for row in messages if row["receiver"] == "reviewer"
                          and row["kind"] in REQUESTS and row["id"] not in replied]
            return dict(session=self._metadata(conn), channel=str(self.path), messages=messages,
                        attempts=attempts, decisions=decisions, events=events, unanswered=unanswered,
                        turn_updates=self._turn_updates(conn),
                        cancellations=cancellations, posts=posts, extension_schema=version,
                        closed=any(row["kind"] == "close" for row in messages))

    def active(self, generation):
        with self.channel.transaction(write=False) as conn:
            row = self._active(conn, generation)
            return dict(row) if row else None

    def rpc_intent(self, generation, rpc_id):
        with self.channel.transaction() as conn:
            row = self._active(conn, generation)
            if row is None or row["state"] != "admitting":
                raise ValueError("No matching reserved send intent.")
            conn.execute("UPDATE awkit_delivery SET rpc_id=?,updated=? WHERE id=?",
                         (encoded(rpc_id), now(), row["id"]))

    def final_text(self, turn_id, items=()):
        with self.channel.transaction(write=False) as conn:
            retained = [json.loads(row[0]).get("item", {}) for row in conn.execute(
                "SELECT payload FROM awkit_events WHERE turn_id=? AND method='item/completed' ORDER BY seq", (turn_id,))]
        texts = {}
        for item in [*retained, *items]:
            if item.get("type") == "agentMessage" and item.get("phase") != "commentary":
                text = item.get("text")
                if isinstance(text, str):
                    texts[item.get("id", str(len(texts)))] = text
        return "\n\n".join(texts.values())

    def turn_events(self, turn_id):
        with self.channel.transaction(write=False) as conn:
            return [(row["method"], json.loads(row["payload"])) for row in conn.execute(
                "SELECT method,payload FROM awkit_events WHERE turn_id=? ORDER BY seq", (turn_id,))]

    def posted_key(self, key):
        with self.channel.transaction(write=False) as conn:
            return conn.execute("SELECT message_id FROM awkit_posts WHERE key=?", (key,)).fetchone() is not None
