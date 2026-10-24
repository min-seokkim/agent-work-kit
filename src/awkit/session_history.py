"""Explicit project-local history references; channel files stay read-only."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import uuid
from pathlib import Path

from .channel import REQUESTS
from .channel_status import _read_channel
from .session_store import now


class HistoryViews:
    def __init__(self, project, directory):
        self.project = Path(project).resolve()
        self.path = Path(directory) / "views.json"
        self.lock = threading.RLock()

    def registrations(self):
        with self.lock:
            if not self.path.exists():
                return []
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("views"), list):
                raise ValueError("Unsupported history registration record; it has not been replaced.")
            return data["views"]

    def register(self, channel, main_name, reviewer_name, *, local_role="main", task=""):
        selected = Path(channel)
        path = (self.project / selected).resolve(strict=True)
        if not path.is_relative_to(self.project) or not path.is_file():
            raise ValueError("Select an existing channel file inside this project.")
        if local_role not in ("main", "reviewer"):
            raise ValueError("Select one of the channel's existing roles.")
        for value in (main_name, reviewer_name):
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError("Each participant needs a name of at most 200 characters.")
        if not isinstance(task, str) or len(task) > 1000:
            raise ValueError("The history task label is at most 1,000 characters.")
        rows = _read_channel(path, include_body=True)
        if any(not isinstance(row["body"], str) for row in rows):
            raise ValueError("Unsupported channel body data.")
        value = dict(id="history-" + str(uuid.uuid4()), channel=str(path), local_role=local_role,
                     parties=dict(main=main_name.strip(), reviewer=reviewer_name.strip()), task=task)
        with self.lock:
            values = self.registrations()
            for existing in values:
                try:
                    same = Path(existing["channel"]).samefile(path)
                except OSError:
                    same = existing["channel"] == str(path)
                if same:
                    if any(existing[key] != value[key] for key in ("parties", "local_role", "task")):
                        raise ValueError("This channel alias already has different participant labels or a role mapping.")
                    return existing
            values.append(value)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix="views-", suffix=".tmp", delete=False) as handle:
                json.dump(dict(schema=1, views=values), handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, self.path)
            return value

    def snapshots(self):
        values = []
        for registration in self.registrations():
            parties = registration["parties"]
            meta = dict(id=registration["id"], name=f"{parties['main']} ↔ {parties['reviewer']}",
                        provider="Stored channel", project=str(self.project), responsibility=registration["task"],
                        native_id=None, state="history only", observed_at=now(), source="read-only channel snapshot",
                        permissions={"available": False, "reason": "No native conversation is attached to this history."},
                        history=True, error=None)
            messages = []
            try:
                path = Path(registration["channel"]).resolve(strict=True)
                if not path.is_relative_to(self.project):
                    raise ValueError("Registered channel is outside this project.")
                messages = _read_channel(path, include_body=True)
                if any(not isinstance(row["body"], str) for row in messages):
                    raise ValueError("Unsupported channel body data.")
            except (OSError, ValueError, sqlite3.Error) as exc:
                meta.update(state="unavailable", error=str(exc))
            replied = {row["reply_to"] for row in messages}
            unanswered = [row["id"] for row in messages if row["kind"] in REQUESTS and row["id"] not in replied]
            values.append(dict(session=meta, channel=registration["channel"], parties=parties, messages=messages,
                               attempts=[], decisions=[], events=[], unanswered=unanswered,
                               closed=any(row["kind"] == "close" for row in messages), connected=False,
                               can_send=False, control_reason="Stored history is read-only; native attachment is unavailable.",
                               execution_state=meta["state"]))
        return values
