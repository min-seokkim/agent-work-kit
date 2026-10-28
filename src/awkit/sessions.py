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
from .claude_session import ClaudeSession, availability, recover_local_results
from .codex_session import CodexSession, ProviderError
from .session_capabilities import describe
from .session_history import HistoryViews
from .session_models import hold, verify_runtime
from .session_models import observe as observe_model
from .session_models import ready as model_ready
from .session_models import validate as validate_model
from .session_recovery import resume
from .session_store import SessionStore, now

PREVENTS = {"awkit session": ("F24", "F29")}
DECISIONS = {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}


class SessionController:
    def __init__(self, project, command, *, record=None, provider_factory=CodexSession,
                 claude_cli=None, claude_factory=ClaudeSession):
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
        self.claude_cli = claude_cli
        self.claude_factory = claude_factory
        self.claude_clients = {}
        self.enrolled_clients = {}
        self.client = {}
        self.errors = []
        self._stores = {}
        self._mutex = threading.RLock()
        self._creation = threading.Lock()
        self._closed = False
        self._recovery_attempted = set()
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
                    store.upgrade()
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

    def create(self, *, name, responsibility, project=None, provider="codex", sandbox=None, permission_mode=None,
               model=None, reasoning_effort=None):
        validate_model(model, provider, reasoning_effort)
        if provider not in ("codex", "claude"):
            raise ValueError("Select Codex or Claude.")
        if provider == "claude" and (sandbox is not None or permission_mode not in (None, "default")):
            raise ValueError("Claude uses its native default permission mode; Codex sandbox choices cannot be transferred.")
        if provider == "codex" and permission_mode is not None:
            raise ValueError("Claude permission modes cannot be transferred to Codex.")
        if provider == "claude" and not availability()["available"]:
            raise ValueError(availability()["reason"])
        sandbox = sandbox or "read-only"
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
                                                                        "approvalsReviewer": "user"}} if provider == "codex" else
                                             {"requested": {"permission_mode": "default", "setting_sources": ["user", "project", "local"]},
                                              "effective_rules": "unverified", "windows_sandbox": "not established"}, provider=provider)
                ident = store.metadata()["id"]
                self._stores[ident] = store
            startup = dict(name=name.strip(), responsibility=responsibility.strip(), project=str(self.project),
                           developer_instructions=f"Your assigned role is {name.strip()}. Responsibility: {responsibility.strip()}",
                           source="thread/start parameters", admission="pending")
            store.update(startup_context=startup)
            if model is not None:
                selection = dict(requested=model, creation=None, latest=None, state="pending" if provider == "codex" else "requested")
                if reasoning_effort is not None:
                    selection["requested_effort"] = reasoning_effort
                store.update(model_selection=selection)
            if provider == "claude":
                store.update(requested_native_id=str(uuid.uuid4()),
                             startup_context=dict(startup, source="Claude native preset with role append"))
                try:
                    self.claude_clients[ident] = self.claude_factory(store, cli_path=self.claude_cli)
                except (OSError, ValueError, RuntimeError, ImportError) as exc:
                    store.update(state="unknown", error=str(exc), source="Claude initialization unavailable", observed_at=now())
                return store.snapshot()
            try:
                client = self._owned_provider()
                if model is not None:
                    verify_runtime(self, client)
                params = {
                    "cwd": str(self.project), "sandbox": sandbox, "approvalPolicy": "on-request",
                    "approvalsReviewer": "user", "serviceName": "awkit",
                    "developerInstructions": startup["developer_instructions"]}
                if model is not None:
                    params["model"] = model
                if reasoning_effort is not None:
                    params["config"] = {"model_reasoning_effort": reasoning_effort}
                result = client.call("thread/start", params)
                if model is not None and not isinstance(result, dict):
                    raise ValueError("Native creation returned no configuration observation; work remains held.")
                if model is not None:
                    # Preserve actual configuration even if identity/policy admission later fails.
                    store.update(model=result.get("model"), model_provider=result.get("modelProvider"))
                    try:
                        observe_model(store, result, creation=True)
                    except ValueError:
                        pass  # Retain the returned identity through the existing safety checks first.
                thread = result["thread"]
                native_id = thread["id"]
                if not isinstance(native_id, str) or not native_id:
                    raise ValueError("Provider returned an invalid conversation identity.")
                startup = dict(startup, admission="provider response received", returned_native_id=native_id)
                store.update(returned_native_id=native_id, client=self.client, startup_context=startup)
                if Path(result["cwd"]).resolve() != self.project:
                    raise ValueError("Provider returned a different project; the returned identity is retained but not bound.")
                with self._mutex:
                    if any((other.metadata().get("native_id") == native_id
                            or (other.metadata().get("enrollment") or {}).get("thread_id") == native_id)
                           for key, other in self._stores.items() if key != ident):
                        raise ValueError("Provider returned another managed conversation's identity.")
                permissions = {key: result[key] for key in ("cwd", "sandbox", "approvalPolicy", "approvalsReviewer")}
                permissions["source"] = "thread/start response"
                state = "idle" if thread.get("status", {}).get("type") == "idle" else "unknown"
                store.update(native_id=native_id, permissions=permissions, model=result.get("model"),
                             model_provider=result.get("modelProvider"), client=self.client, state=state,
                             observed_at=now(), source="thread/start response", error=None)
                if model is not None and not model_ready(store.metadata()):
                    raise ValueError("Returned Codex configuration does not match the explicit creation selection; work remains held.")
            except (OSError, ValueError, KeyError, TypeError, ProviderError) as exc:
                hold(store)
                store.update(state="unknown", observed_at=now(), source="thread/start failure or uncertainty", error=str(exc),
                             client=self.client)
            return store.snapshot()

    def enroll(self, *, name, thread_id, provider="codex"):
        if provider not in ("codex", "claude"):
            raise ValueError("Select Codex or Claude.")
        capability = describe(provider)["operations"]["enrollment"]
        if not capability["supported"]:
            raise ValueError(capability["reason"])
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("Session name must contain 1 to 200 characters.")
        if not isinstance(thread_id, str) or str(uuid.UUID(thread_id)) != thread_id:
            raise ValueError("Select the exact canonical native Codex thread UUID.")
        with self._creation:
            if self._stop.is_set():
                raise ValueError("The controller is stopping; no enrollment was attempted.")
            with self._mutex:
                for store in self._stores.values():
                    meta = store.metadata()
                    selected = (meta.get("enrollment") or {}).get("thread_id") or meta.get("native_id")
                    if selected == thread_id:
                        if meta.get("enrollment") and meta["name"] == name.strip():
                            return store.snapshot()
                        raise ValueError("This native identity is already registered; no second owner was created.")
                    if meta["name"].casefold() == name.strip().casefold():
                        raise ValueError("A session already uses this name; no target was replaced.")
                store = SessionStore.create(self.directory / "channels", name=name.strip(), project=self.project,
                    responsibility="Existing Codex conversation; original instructions retained.",
                    generation=self.generation, permissions={}, provider="codex",
                    enrollment=dict(thread_id=thread_id, admission="selected; native ownership unverified"))
                ident = store.metadata()["id"]
                self._recovery_attempted.add(ident)
                self._stores[ident] = store
            self._resume_enrolled(store)
            return store.snapshot()

    def _resume_enrolled(self, store):
        from .codex_enrollment import resume as enroll_resume

        self._recovery_attempted.add(store.metadata()["id"])
        try:
            enroll_resume(self, store)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError, ProviderError) as exc:
            client = self.enrolled_clients.pop(store.metadata()["id"], None)
            if client:
                client.close()
            store.update(state="unknown", error=str(exc), source="Codex enrollment refused or uncertain; no task sent", observed_at=now())

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
        meta = store.metadata()
        if not model_ready(meta):
            raise ValueError("The explicit model selection is unverified or mismatched; work remains held.")
        provider, generation = self._connection(store)
        if meta["generation"] != generation:
            raise ValueError("This conversation is reconnecting. Its saved history remains readable.")
        if (provider is None or not provider.alive or not (meta["native_id"] or meta.get("requested_native_id"))
                or store.metadata()["state"] == "unknown"):
            raise ValueError("Provider connection or conversation state is unavailable; the assignment has not been submitted.")
        with self._mutex:
            for other in self._stores.values():
                if any(row["key"] == key for row in other.turn_updates()):
                    raise ValueError("This caller key already names a turn update; a new assignment needs a fresh key.")
                if other is not store and other.posted_key(key):
                    raise ValueError("This client key already names a message for a different recipient.")
            row = store.post(key, body, kind=kind, entry=entry)
        return dict(session=store.metadata()["id"], key=key, message=row, state="stored")

    def resume(self, ident):
        store = self._store(ident)
        with self._creation:
            if self._stop.is_set():
                raise ValueError("The controller is stopping; no provider connection will be started.")
            if store.metadata().get("enrollment"):
                prior = self.enrolled_clients.get(store.metadata()["id"])
                if not prior or not prior.alive or store.metadata()["state"] == "unknown":
                    self._resume_enrolled(store)
                return store.snapshot()
            if store.metadata()["provider"] == "claude":
                meta = store.metadata()
                prior = self.claude_clients.get(meta["id"])
                if prior and prior.alive and meta["state"] != "unknown":
                    return store.snapshot()
                if prior:
                    prior.close()
                self.claude_clients.pop(meta["id"], None)
                recover_local_results(store)
                generation = str(uuid.uuid4())
                store.reconnect(generation)
                store.update(generation=generation, state="reconnecting", observed_at=now(), source="exact-ID Claude resume")
                self._recovery_attempted.add(meta["id"])
                try:
                    self.claude_clients[meta["id"]] = self.claude_factory(store, cli_path=self.claude_cli, resume=True)
                except (OSError, ValueError, RuntimeError, ImportError) as exc:
                    store.update(state="unknown", error=str(exc), source="Claude resume unavailable; no resend", observed_at=now())
                return store.snapshot()
            self.provider_error = None
            if self.provider is not None and not self.provider.alive:
                self.provider.close()
                self.provider = None
                self.provider_error = None
                # Native request IDs are scoped to this connection, not the HTTP process.
                self.generation = str(uuid.uuid4())
                self._recovery_attempted.clear()
            if store.metadata()["generation"] == self.generation and store.metadata()["state"] != "unknown":
                return store.snapshot()
            self._recovery_attempted.add(store.metadata()["id"])
            try:
                resume(self, store)
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, ProviderError) as exc:
                hold(store)
                store.update(state="unknown", observed_at=now(), source="resume unavailable; history retained", error=str(exc))
            return store.snapshot()

    def _connection(self, store):
        meta = store.metadata()
        if meta.get("enrollment"):
            client = self.enrolled_clients.get(meta["id"])
            return client, client.generation if client else meta["generation"]
        if meta["provider"] == "claude":
            client = self.claude_clients.get(meta["id"])
            return client, client.generation if client else self.generation
        return self.provider, self.generation

    def cancel(self, ident, request_id):
        return self._store(ident).cancel(request_id)

    def update_turn(self, ident, **args):
        from .session_updates import submit

        meta = self._store(ident).metadata()
        capability = describe(meta["provider"])["operations"]["active_turn_update"]
        if not capability["supported"]:
            raise ValueError(capability["reason"])
        if not model_ready(meta):
            raise ValueError("The explicit model selection is unverified or mismatched; work remains held.")
        return submit(self, ident, **args)

    def discover(self, *, cursor=None, limit=20, provider="codex"):
        from .session_discovery import discover

        if provider not in ("codex", "claude"):
            raise ValueError("Select Codex or Claude.")
        capability = describe(provider)["operations"]["discovery"]
        if not capability["supported"]:
            return dict(available=False, reason=capability["reason"], project=str(self.project), conversations=[], next_cursor=None)
        return discover(self, cursor=cursor, limit=limit)

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
                    if not model_ready(meta):
                        continue
                    if meta["provider"] == "claude":
                        if meta["id"] not in self.claude_clients and meta["id"] not in self._recovery_attempted:
                            self.resume(meta["id"])
                        client = self.claude_clients.get(meta["id"])
                        if client and client.alive and store.metadata()["state"] == "idle":
                            claim = store.claim(client.generation)
                            if claim:
                                client.submit(claim)
                        continue
                    if (meta.get("enrollment") and meta["id"] not in self.enrolled_clients
                            and meta["id"] not in self._recovery_attempted):
                        self.resume(meta["id"])
                        meta = store.metadata()
                    elif not meta.get("enrollment") and meta["generation"] != self.generation and meta["id"] not in self._recovery_attempted:
                        self.resume(meta["id"])
                        meta = store.metadata()
                    provider, generation = self._connection(store)
                    if (not model_ready(meta) or meta["generation"] != generation
                            or meta["state"] not in ("idle", "waiting for idle") or not meta["native_id"]):
                        continue
                    snapshot = store.snapshot()
                    attempted = {row["request_id"] for row in snapshot["attempts"]}
                    attempted.update(row["request_id"] for row in snapshot["cancellations"])
                    if not any(ident not in attempted for ident in snapshot["unanswered"]):
                        continue
                    if provider is None or not provider.alive:
                        continue
                    if meta.get("enrollment"):
                        from .codex_enrollment import observe

                        observe(self, store, provider)
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
                    claim = store.claim(generation)
                    if claim is None:
                        continue
                    result = provider.call("turn/start", {
                        "threadId": claim["native_id"], "clientUserMessageId": claim["id"],
                        "input": [{"type": "text", "text": claim["request"]["body"]}]},
                        on_request=lambda rpc_id, target=store, gen=generation: target.rpc_intent(gen, rpc_id))
                    turn_id = result["turn"]["id"]
                    store.bind_turn(generation, turn_id)
                    # Events can precede the RPC response. Bind only the response's actual turn.
                    for method, params in store.turn_events(turn_id):
                        self._apply_turn(store, method, params)
                except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, ProviderError) as exc:
                    store.uncertain(self._connection(store)[1], str(exc))
                    if store.metadata().get("enrollment"):
                        client = self.enrolled_clients.pop(store.metadata()["id"], None)
                        if client:
                            client.close()

    def _message(self, message, *, generation=None, owned_id=None):
        generation = generation or self.generation
        method, params = message.get("method", ""), message.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("Invalid provider event parameters.")
        if method.startswith(("account/", "config/", "item/reasoning")) or params.get("item", {}).get("type") == "reasoning":
            return
        with self._mutex:
            stores = ([self._stores[owned_id]] if owned_id in self._stores else []) if owned_id else [
                store for store in self._stores.values() if not store.metadata().get("enrollment")]
        if method == "awkit/connectionError":
            for store in stores:
                if store.metadata()["provider"] == "codex" and store.metadata()["generation"] == generation:
                    store.uncertain(generation, params.get("reason", "Provider connection lost"))
            return
        if method == "serverRequest/resolved":
            for store in stores:
                if store.metadata()["provider"] == "codex":
                    store.resolve_decisions(generation, params.get("requestId"), params.get("threadId"))
            return
        native_id = params.get("threadId", params.get("thread", {}).get("id"))
        store = next((value for value in stores if value.metadata()["provider"] == "codex" and value.metadata().get("native_id") == native_id
                      and value.metadata()["generation"] == generation), None)
        if store is None:
            if "id" in message:
                self.errors.append(f"Unrouted provider request {method}; no decision was granted.")
            return
        if method == "item/agentMessage/delta":
            return  # Completed messages below retain the full actual body.
        if owned_id and method == "thread/started":
            return  # Resumed metadata may contain an old preview; do not import it.
        if owned_id and (method.startswith(("item/", "turn/"))) and store.active(generation) is None:
            return
        store.event(generation, method, params)
        if "id" in message:
            choices = []
            if method in DECISIONS:
                available = params.get("availableDecisions", ["accept", "acceptForSession", "decline", "cancel"])
                choices = [value for value in available if isinstance(value, str)
                           and value in ("accept", "acceptForSession", "decline", "cancel")]
            store.add_decision(generation, message["id"], method, params, choices)
        else:
            self._apply_turn(store, method, params)

    def _apply_turn(self, store, method, params):
        if method not in ("turn/started", "turn/completed"):
            return
        turn = params["turn"]
        generation = store.metadata()["generation"]
        active = store.active(generation)
        if active is None or active["turn_id"] != turn["id"]:
            return
        if method == "turn/started":
            store.bind_turn(generation, turn["id"], executing=True)
        else:
            store.finish(generation, turn["id"], turn["status"],
                         store.final_text(turn["id"], turn.get("items", [])), turn.get("error"))

    def decide(self, ident, decision_id, choice):
        store = self._store(ident)
        if store.metadata()["provider"] == "claude":
            client = self.claude_clients.get(store.metadata()["id"])
            if not client or not client.alive:
                raise ValueError("The original Claude callback connection is unavailable.")
            return client.decide(decision_id, choice)
        provider, generation = self._connection(store)
        decision = next((row for row in store.snapshot()["decisions"] if row["id"] == decision_id), None)
        if (decision is None or decision["generation"] != generation or decision["method"] not in DECISIONS
                or choice not in decision["choices"]):
            raise ValueError("This choice is unavailable for the originating provider request.")
        active = store.active(generation)
        if (provider is None or not provider.alive or active is None
                or decision["params"].get("threadId") != active["native_id"]
                or decision["params"].get("turnId") != active["turn_id"]):
            raise ValueError("The originating provider turn is not correlated on this live connection; no answer was sent.")
        row = store.answer_intent(generation, decision_id, {"decision": choice})
        try:
            provider.respond(json.loads(row["rpc_id"]), {"decision": choice})
        except ProviderError:
            store.decision_state(decision_id, "uncertain")
            raise
        store.decision_state(decision_id, "sent")
        return dict(state="sent", decision=decision_id)

    def interrupt(self, ident):
        store = self._store(ident)
        if store.metadata()["provider"] == "claude":
            client = self.claude_clients.get(store.metadata()["id"])
            active = store.active(client.generation) if client else None
            if not active or not client.alive:
                raise ValueError("No correlated Claude work is active on this connection.")
            with store.channel.transaction() as conn:
                conn.execute("UPDATE awkit_delivery SET interruption_requested=?,updated=? WHERE id=?", (now(), now(), active["id"]))
            client.interrupt()
            return dict(state="interrupt requested", task_result="unverified")
        provider, generation = self._connection(store)
        active = store.active(generation)
        if active is None or not active["turn_id"] or provider is None or not provider.alive:
            raise ValueError("There is no observed live turn to interrupt on this connection.")
        store.interruption(generation, active["turn_id"])
        provider.call("turn/interrupt", {"threadId": active["native_id"], "turnId": active["turn_id"]})
        return dict(state="interrupt requested", task_result="unverified")

    def status(self):
        with self._mutex:
            stores = list(self._stores.values())
        views = []
        for store in stores:
            snapshot = store.snapshot()
            meta = snapshot["session"]
            provider, generation = self._connection(store)
            connected = bool(provider and provider.alive and meta["generation"] == generation)
            age = (datetime.now(UTC) - datetime.fromisoformat(meta["observed_at"])).total_seconds()
            can_send = (connected and model_ready(meta) and bool(meta["native_id"] or meta.get("requested_native_id")) and not snapshot["closed"]
                        and meta["state"] in ("idle", "waiting for idle", "running", "accepted", "decision needed", "submitting"))
            reason = ("The requested Codex configuration is unverified or differs from its creation receipt. Work remains held."
                      if not model_ready(meta) else "This channel is closed." if snapshot["closed"] else
                      "Conversation state is uncertain. Inspect unfinished work; reconnecting never resends uncertain work." if connected else
                      "Reconnecting the saved conversation, or connection unavailable. History remains readable.")
            if not can_send and meta.get("error"):
                reason += " " + str(meta["error"])
            for decision in snapshot["decisions"]:
                decision["can_answer"] = connected and decision["generation"] == generation and decision["state"] == "pending"
                decision["request_id"] = next((row["request_id"] for row in snapshot["attempts"]
                                               if (row["provider_input_id"] == decision["params"].get("provider_input_id")
                                                   if meta["provider"] == "claude" else row["turn_id"] == decision["params"].get("turnId"))), None)
            from .session_reading import dispositions

            snapshot.update(connected=connected, can_send=can_send,
                            dispositions=dispositions(snapshot), can_resume=bool(meta["native_id"] or meta.get("enrollment")) and not can_send,
                            execution_state=meta["state"] if connected and age < 60 else "unknown",
                            parties={"main": "Coordinator", "reviewer": meta["name"]},
                            control_reason="" if can_send else reason)
            from .session_updates import supported

            active = store.active(generation)
            snapshot["update_target"] = (dict(request_id=active["request_id"], expected_turn_id=active["turn_id"],
                native_id=meta["native_id"], observed_at=meta["observed_at"], source=meta["source"])
                if connected and model_ready(meta) and supported(meta) and not snapshot["closed"] and active and active["turn_id"]
                and active["state"] in ("accepted", "executing") and meta["state"] in ("running", "accepted", "decision needed") else None)
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
                names = {}
                for relation in report["relationships"]:
                    view = next((value for value in views if value["session"]["id"] == links.get(relation["id"])), None)
                    if view:
                        local = relation["local_role"]
                        for identity, role in ((report["session"], local), (relation["counterpart"], "reviewer" if local == "main" else "main")):
                            names.setdefault(identity, set()).add(view["parties"][role])
                for view in views:
                    if view["session"].get("native_id"):
                        names.setdefault(view["session"]["native_id"], set()).add(view["session"]["name"])
                for obligation in report["obligations"]:
                    candidates = names.get(obligation["responsible_session"], set())
                    obligation["display_name"] = next(iter(candidates)) if len(candidates) == 1 else None
                declarations = dict(report=report, exit_code=exit_code, view_links=links)
            except (OSError, ValueError, sqlite3.Error) as exc:
                declarations = dict(error=str(exc))
        from .session_reading import project

        for view in views:
            view["capabilities"] = describe(view["session"]["provider"])
            project(view, declarations)
        claude = availability()
        providers = {name: describe(name) for name in ("codex", "claude")}
        providers["codex"].update(available=bool(shutil.which(self.command[0])), unavailable_reason="Codex executable unavailable.")
        providers["claude"].update(available=claude["available"], unavailable_reason=claude.get("reason", ""))
        return dict(project=str(self.project), generation=self.generation, sessions=views,
                    provider_error=self.provider_error, diagnostics=self.errors[-10:], declarations=declarations,
                    capabilities={"managed_codex": True,
                                  "providers": providers,
                                  "codex_executable_available": bool(shutil.which(self.command[0])),
                                  "restart_resume": True, "codex_enrollment": True, "claude": claude["available"],
                                  "claude_runtime": claude, "ide_attachment": False})

    def close(self):
        self._stop.set()
        with self._creation:
            if self._closed:
                return
            self._closed = True
            if self.provider:
                self.provider.close()
            for client in self.claude_clients.values():
                client.close()
            for client in self.enrolled_clients.values():
                client.close()
        self._worker.join(timeout=5)
        self.lock.rollback()
        self.lock.close()
