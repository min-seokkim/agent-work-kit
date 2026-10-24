"""Project-owned managed conversations; channel messages remain task authority."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .channel_status import observe
from .codex_session import CodexSession, ProviderError
from .session_history import HistoryViews
from .session_store import SessionStore, encoded, now

PREVENTS = {"awkit session": ("F24", "F29")}
DECISIONS = {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}


class SessionController:
    def __init__(self, project, command, *, record=None, provider_factory=CodexSession):
        self.project = Path(project).resolve(strict=True)
        if not self.project.is_dir():
            raise ValueError("The selected project is not a directory.")
        self.directory = self.project / ".awkit/sessions"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = sqlite3.connect(self.directory / "controller.lock.sqlite3", timeout=0)
        try:
            self.lock.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            self.lock.close()
            raise ValueError("Another controller owns this project; it has not been stopped or replaced.") from exc
        self.generation = str(uuid.uuid4())
        self.command = list(command)
        self.record = record
        self.provider_factory = provider_factory
        self.provider = None
        self.provider_error = None
        self.client = {}
        self.errors = []
        self._stores = {}
        self._mutex = threading.RLock()
        self._creation = threading.Lock()
        self._closed = False
        self._stop = threading.Event()
        self.history = HistoryViews(self.project, self.directory)
        for path in sorted((self.directory / "channels").glob("*.sqlite3")):
            try:
                store = SessionStore(path)
                data = store.metadata()
                if Path(data["project"]).resolve() != self.project:
                    raise ValueError("Managed channel belongs to a different project.")
                if data["id"] in self._stores:
                    if not self._stores[data["id"]].path.samefile(path):
                        raise ValueError("Conflicting copied channel identity; no delivery is permitted.")
                else:
                    self._stores[data["id"]] = store
            except (OSError, ValueError, sqlite3.Error) as exc:
                self.errors.append(f"{path.name}: {exc}")
        self._worker = threading.Thread(target=self._dispatch, daemon=True)
        self._worker.start()

    def _owned_provider(self):
        if self._stop.is_set():
            raise ProviderError("The controller is stopping; no provider will be started.")
        if self.provider is not None:
            if not self.provider.alive:
                raise ProviderError("Owned provider is unavailable. Automatic restart/replay is not supported.")
            return self.provider
        if self.provider_error:
            raise ProviderError(self.provider_error)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            version = subprocess.run([*self.command, "--version"], capture_output=True, timeout=10, creationflags=flags, cwd=self.project)
            self.client = dict(command=self.command, version=version.stdout.decode("utf-8", errors="replace").strip()[:300],
                               version_exit=version.returncode)
            executable = Path(self.command[0])
            if executable.is_file():
                self.client["executable_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
            self.provider = self.provider_factory(self.command, self.project, self._message)
            self.client["initialization"] = self.provider.initialization
            self.client["owned_pid"] = self.provider.process.pid
            return self.provider
        except (OSError, ValueError, subprocess.SubprocessError, ProviderError) as exc:
            self.provider_error = str(exc)
            raise ProviderError(self.provider_error) from exc

    def create(self, *, name, responsibility, project=None, provider="codex", sandbox="read-only"):
        if provider != "codex":
            raise ValueError("This unit supports managed Codex only; Claude and native IDE attachment are unavailable.")
        if project is not None and Path(project).resolve() != self.project:
            raise ValueError("This controller manages only its selected project.")
        for value, label, limit in ((name, "name", 200), (responsibility, "responsibility", 2000)):
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"Session {label} must contain 1 to {limit} characters.")
        if sandbox not in ("read-only", "workspace-write"):
            raise ValueError("Select read-only or workspace-write permissions.")
        with self._creation:
            if self._stop.is_set():
                raise ValueError("The controller is stopping; no new conversation will be created.")
            with self._mutex:
                if any(store.metadata()["name"].casefold() == name.strip().casefold() for store in self._stores.values()):
                    raise ValueError("A session already uses this name in this project.")
                store = SessionStore.create(self.directory / "channels", name=name.strip(), project=self.project,
                                             responsibility=responsibility.strip(), generation=self.generation,
                                             permissions={"requested": {"sandbox": sandbox, "approvalPolicy": "on-request",
                                                                        "approvalsReviewer": "user"}})
                ident = store.metadata()["id"]
                self._stores[ident] = store
            startup = dict(name=name.strip(), responsibility=responsibility.strip(), project=str(self.project),
                           developer_instructions=f"Your assigned role is {name.strip()}. Responsibility: {responsibility.strip()}",
                           source="thread/start parameters", admission="pending")
            store.update(startup_context=startup)
            try:
                result = self._owned_provider().call("thread/start", {
                    "cwd": str(self.project), "sandbox": sandbox, "approvalPolicy": "on-request",
                    "approvalsReviewer": "user", "serviceName": "awkit",
                    "developerInstructions": startup["developer_instructions"]})
                thread = result["thread"]
                native_id = thread["id"]
                if not isinstance(native_id, str) or not native_id:
                    raise ValueError("Provider returned an invalid conversation identity.")
                startup = dict(startup, admission="provider response received", returned_native_id=native_id)
                store.update(returned_native_id=native_id, client=self.client, startup_context=startup)
                if Path(result["cwd"]).resolve() != self.project:
                    raise ValueError("Provider returned a different project; the returned identity is retained but not bound.")
                with self._mutex:
                    if any(other.metadata().get("native_id") == native_id for key, other in self._stores.items() if key != ident):
                        raise ValueError("Provider returned another managed conversation's identity.")
                permissions = {key: result[key] for key in ("cwd", "sandbox", "approvalPolicy", "approvalsReviewer")}
                permissions["source"] = "thread/start response"
                state = "idle" if thread.get("status", {}).get("type") == "idle" else "unknown"
                store.update(native_id=native_id, permissions=permissions, model=result.get("model"),
                             model_provider=result.get("modelProvider"), client=self.client, state=state,
                             observed_at=now(), source="thread/start response", error=None)
            except (OSError, ValueError, KeyError, TypeError, ProviderError) as exc:
                store.update(state="unknown", observed_at=now(), source="thread/start failure or uncertainty", error=str(exc),
                             client=self.client)
            return store.snapshot()

    def _store(self, ident):
        with self._mutex:
            if ident in self._stores:
                return self._stores[ident]
            matches = [store for store in self._stores.values() if store.metadata()["name"] == ident]
            if len(matches) == 1:
                return matches[0]
        raise ValueError("Select an existing managed session by its name or ID. Stored history has no native send control.")

    def send(self, ident, *, key, body, kind="question", entry="agent"):
        store = self._store(ident)
        if store.metadata()["generation"] != self.generation:
            raise ValueError("This conversation belongs to an earlier controller. Resuming it after restart is not supported yet.")
        if (self.provider is None or not self.provider.alive or not store.metadata()["native_id"]
                or store.metadata()["state"] == "unknown"):
            raise ValueError("Provider connection or conversation state is unavailable; the assignment has not been submitted.")
        with self._mutex:
            for other in self._stores.values():
                if other is not store and other.posted_key(key):
                    raise ValueError("This client key already names a message for a different recipient.")
            row = store.post(key, body, kind=kind, entry=entry)
        return dict(session=store.metadata()["id"], key=key, message=row, state="stored")

    def register_history(self, **args):
        path = self.project / Path(args.get("channel", ""))
        with self._mutex:
            for store in self._stores.values():
                try:
                    same = path.samefile(store.path)
                except OSError:
                    same = False
                if same:
                    raise ValueError("This managed channel is already shown; select its named session to read it.")
            return self.history.register(**args)

    def _dispatch(self):
        while not self._stop.wait(0.35):
            with self._mutex:
                stores = list(self._stores.values())
            for store in stores:
                try:
                    meta = store.metadata()
                    if meta["generation"] != self.generation or meta["state"] not in ("idle", "waiting for idle") or not meta["native_id"]:
                        continue
                    snapshot = store.snapshot()
                    attempted = {row["request_id"] for row in snapshot["attempts"]}
                    if not any(ident not in attempted for ident in snapshot["unanswered"]):
                        continue
                    provider = self.provider
                    if provider is None or not provider.alive:
                        continue
                    result = provider.call("thread/read", {"threadId": meta["native_id"]})
                    thread = result.get("thread", {})
                    state = thread.get("status", {}).get("type")
                    if thread.get("id") != meta["native_id"] or state not in ("idle", "active"):
                        store.update(state="unknown", observed_at=now(), source="thread/read", error="Provider identity or availability is uncertain.")
                        continue
                    if state == "active":
                        store.update(state="waiting for idle", observed_at=now(), source="thread/read")
                        continue
                    store.update(state="idle", observed_at=now(), source="thread/read")
                    claim = store.claim(self.generation)
                    if claim is None:
                        continue
                    result = provider.call("turn/start", {
                        "threadId": claim["native_id"], "input": [{"type": "text", "text": claim["request"]["body"]}]},
                        on_request=lambda rpc_id, target=store: target.rpc_intent(self.generation, rpc_id))
                    turn_id = result["turn"]["id"]
                    store.bind_turn(self.generation, turn_id)
                    # Events can precede the RPC response. Bind only the response's actual turn.
                    for method, params in store.turn_events(turn_id):
                        self._apply_turn(store, method, params)
                except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, ProviderError) as exc:
                    store.uncertain(self.generation, str(exc))

    def _message(self, message):
        method, params = message.get("method", ""), message.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("Invalid provider event parameters.")
        if method.startswith(("account/", "config/", "item/reasoning")) or params.get("item", {}).get("type") == "reasoning":
            return
        with self._mutex:
            stores = list(self._stores.values())
        if method == "awkit/connectionError":
            for store in stores:
                if store.metadata()["generation"] == self.generation:
                    store.uncertain(self.generation, params.get("reason", "Provider connection lost"))
            return
        if method == "serverRequest/resolved":
            ident = f"{self.generation}:{encoded(params.get('requestId'))}"
            for store in stores:
                store.decision_state(ident, "resolved")
            return
        native_id = params.get("threadId", params.get("thread", {}).get("id"))
        store = next((value for value in stores if value.metadata().get("native_id") == native_id
                      and value.metadata()["generation"] == self.generation), None)
        if store is None:
            if "id" in message:
                self.errors.append(f"Unrouted provider request {method}; no decision was granted.")
            return
        if method == "item/agentMessage/delta":
            return  # Completed messages below retain the full actual body.
        store.event(self.generation, method, params)
        if "id" in message:
            choices = []
            if method in DECISIONS:
                available = params.get("availableDecisions", ["accept", "acceptForSession", "decline", "cancel"])
                choices = [value for value in available if isinstance(value, str)
                           and value in ("accept", "acceptForSession", "decline", "cancel")]
            store.add_decision(self.generation, message["id"], method, params, choices)
        else:
            self._apply_turn(store, method, params)

    def _apply_turn(self, store, method, params):
        if method not in ("turn/started", "turn/completed"):
            return
        turn = params["turn"]
        active = store.active(self.generation)
        if active is None or active["turn_id"] != turn["id"]:
            return
        if method == "turn/started":
            store.bind_turn(self.generation, turn["id"], executing=True)
        else:
            store.finish(self.generation, turn["id"], turn["status"],
                         store.final_text(turn["id"], turn.get("items", [])), turn.get("error"))

    def decide(self, ident, decision_id, choice):
        store = self._store(ident)
        decision = next((row for row in store.snapshot()["decisions"] if row["id"] == decision_id), None)
        if (decision is None or decision["generation"] != self.generation or decision["method"] not in DECISIONS
                or choice not in decision["choices"]):
            raise ValueError("This choice is unavailable for the originating provider request.")
        active = store.active(self.generation)
        if (self.provider is None or not self.provider.alive or active is None
                or decision["params"].get("threadId") != active["native_id"]
                or decision["params"].get("turnId") != active["turn_id"]):
            raise ValueError("The originating provider turn is not correlated on this live connection; no answer was sent.")
        row = store.answer_intent(self.generation, decision_id, {"decision": choice})
        try:
            self.provider.respond(json.loads(row["rpc_id"]), {"decision": choice})
        except ProviderError:
            store.decision_state(decision_id, "uncertain")
            raise
        store.decision_state(decision_id, "sent")
        return dict(state="sent", decision=decision_id)

    def interrupt(self, ident):
        store = self._store(ident)
        active = store.active(self.generation)
        if active is None or not active["turn_id"] or self.provider is None or not self.provider.alive:
            raise ValueError("There is no observed live turn to interrupt on this connection.")
        self.provider.call("turn/interrupt", {"threadId": active["native_id"], "turnId": active["turn_id"]})
        return dict(state="interrupt requested", task_result="unverified")

    def status(self):
        with self._mutex:
            stores = list(self._stores.values())
        views = []
        for store in stores:
            snapshot = store.snapshot()
            meta = snapshot["session"]
            connected = bool(self.provider and self.provider.alive and meta["generation"] == self.generation)
            age = (datetime.now(UTC) - datetime.fromisoformat(meta["observed_at"])).total_seconds()
            can_send = connected and bool(meta["native_id"]) and not snapshot["closed"] and meta["state"] != "unknown"
            reason = ("This channel is closed." if snapshot["closed"] else
                      "Conversation state is uncertain; automatic replay/recovery is unavailable." if connected else
                      "Connection unavailable. Resuming a saved conversation after restart is not supported yet.")
            snapshot.update(connected=connected, can_send=can_send,
                            execution_state=meta["state"] if connected and age < 60 else "unknown",
                            parties={"main": "Coordinator", "reviewer": meta["name"]},
                            control_reason="" if can_send else reason)
            views.append(snapshot)
        try:
            views.extend(self.history.snapshots())
        except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
            self.errors.append(f"History registration unavailable: {exc}")
        declarations = None
        if self.record:
            try:
                report, exit_code = observe(self.record)
                links = {}
                for relation in report["relationships"]:
                    for view in views:
                        try:
                            same = Path(relation["channel"]).samefile(view["channel"])
                        except OSError:
                            same = False
                        if same:
                            links[relation["id"]] = view["session"]["id"]
                declarations = dict(report=report, exit_code=exit_code, view_links=links)
            except (OSError, ValueError, sqlite3.Error) as exc:
                declarations = dict(error=str(exc))
        return dict(project=str(self.project), generation=self.generation, sessions=views,
                    provider_error=self.provider_error, diagnostics=self.errors[-10:], declarations=declarations,
                    capabilities={"managed_codex": True,
                                  "codex_executable_available": bool(shutil.which(self.command[0])),
                                  "restart_resume": False, "claude": False, "ide_attachment": False})

    def close(self):
        self._stop.set()
        with self._creation:
            if self._closed:
                return
            self._closed = True
            if self.provider:
                self.provider.close()
        self._worker.join(timeout=5)
        self.lock.rollback()
        self.lock.close()
