"""Project-owned managed conversations; channel messages remain task authority."""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import session_states as states
from .channel_status import observe
from .claude_session import ClaudeSession, availability
from .codex_session import CodexSession, ProviderError
from .local_state import prepare
from .session_capabilities import describe
from .session_history import HistoryViews, unavailable_channel
from .session_models import hold, verify_runtime
from .session_models import observe as observe_model
from .session_models import ready as model_ready
from .session_models import validate as validate_model
from .session_routes import DECISIONS, DISPATCH_ERRORS, route
from .session_store import SessionStore, now

PREVENTS = {"awkit session": ("F1", "F29")}
__all__ = ["DECISIONS", "SessionController"]


class SessionController:
    def __init__(self, project, command, *, record=None, provider_factory=CodexSession,
                 claude_cli=None, claude_factory=ClaudeSession):
        self.project = Path(project).resolve(strict=True)
        if not self.project.is_dir():
            raise ValueError("The selected project is not a directory.")
        self.directory = self.project / ".awkit/sessions"
        prepare(self.project, self.directory / "controller.lock.sqlite3")
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
        self.unavailable_channels = {}
        self._stores = {}
        self._mutex = threading.RLock()
        self._creation = threading.Lock()
        self._closed = False
        # Sessions whose provider connection this controller already tried to restore; routes read and update it.
        self.recovery_attempted = self._recovery_attempted = set()
        self._discovery_pages = {}
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
                self.unavailable_channels[str(path)] = unavailable_channel(path, self.project, exc)
        self._worker = threading.Thread(target=self._dispatch, daemon=True)
        self._worker.start()

    # The public surface that routes and helper modules use instead of the controller's private attributes.

    @property
    def guard(self):
        """The lock held while reading or changing the set of managed sessions."""
        return self._mutex

    @property
    def stopping(self):
        return self._closed or self._stop.is_set()

    @property
    def discovery_pages(self):
        return self._discovery_pages

    def stores(self):
        with self._mutex:
            return list(self._stores.values())

    def store_by_id(self, ident):
        """The session with exactly this local ID, or None; names are not matched."""
        with self._mutex:
            return self._stores.get(ident)

    def native_owner(self, native_id, *, excluding=None):
        """The other managed session that selects this native conversation (as its enrolled thread or its
        native ID), or None. One session per native conversation is the rule every creation path checks."""
        with self._mutex:
            for store in self._stores.values():
                meta = store.metadata()
                if meta["id"] == excluding:
                    continue
                if native_id in ((meta.get("enrollment") or {}).get("thread_id"), meta.get("native_id")):
                    return store
        return None

    def registered_natives(self):
        """The native conversations Codex sessions already select."""
        selected = set()
        for store in self.stores():
            meta = store.metadata()
            if meta.get("provider") == "codex":
                selected.add((meta.get("enrollment") or {}).get("thread_id") or meta.get("native_id"))
        return selected

    def connection(self, store):
        meta = store.metadata()
        return route(meta).connection(self, meta)

    def event_handler(self, generation, owned_id):
        """The callback a dedicated provider connection uses to deliver its events to this controller."""
        return lambda message: self._message(message, generation=generation, owned_id=owned_id)

    def owned_provider(self):
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
            self.client.update(getattr(self.provider, "runtime", {}))
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
                client = self.owned_provider()
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
                if self.native_owner(native_id, excluding=ident) is not None:
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
                self.recovery_attempted.add(ident)
                self._stores[ident] = store
            self.resume_enrolled(store)
            return store.snapshot()

    def resume_enrolled(self, store):
        from .codex_enrollment import resume as enroll_resume

        self.recovery_attempted.add(store.metadata()["id"])
        try:
            enroll_resume(self, store)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError, ProviderError) as exc:
            client = self.enrolled_clients.pop(store.metadata()["id"], None)
            if client:
                client.close()
            store.update(state="unknown", error=str(exc), source="Codex enrollment refused or uncertain; no task sent", observed_at=now())

    _resume_enrolled = resume_enrolled

    def store(self, ident):
        with self._mutex:
            if ident in self._stores:
                return self._stores[ident]
            matches = []
            for store in self._stores.values():
                try:
                    if store.metadata()["name"] == ident:
                        matches.append(store)
                except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                    self.unavailable_channels[str(store.path)] = unavailable_channel(store.path, self.project, exc)
            if len(matches) == 1:
                return matches[0]
        raise ValueError("Select an existing managed session by its name or ID. Stored history has no native send control.")

    _store = store

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
            route(store.metadata()).resume(self, store)
            return store.snapshot()

    _connection = connection

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
            for store in self.stores():
                try:
                    meta = store.metadata()
                    if model_ready(meta):
                        route(meta).dispatch(self, store, meta)
                except DISPATCH_ERRORS as exc:
                    try:
                        route(store.metadata()).failed(self, store, exc)
                    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as failure:
                        # A broken channel cannot stop the worker serving the other channels.
                        with self._mutex:
                            self.unavailable_channels[str(store.path)] = unavailable_channel(store.path, self.project, failure)

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
            self.apply_turn(store, method, params)

    def apply_turn(self, store, method, params):
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


    _apply_turn = apply_turn

    def decide(self, ident, decision_id, choice):
        store = self._store(ident)
        return route(store.metadata()).decide(self, store, decision_id, choice)

    def interrupt(self, ident):
        store = self._store(ident)
        return route(store.metadata()).interrupt(self, store)

    def status(self, *, session=None, request=None):
        from .session_reading import SelectorError, decision_request, exact_request, selectors

        selection = selectors({key: value for key, value in (("session", session), ("request", request)) if value is not None})
        session, request = selection.get("session"), selection.get("request")
        if selection:
            try:
                stores = [self._store(selection["session"])]
            except ValueError as exc:
                aliases = self.history.registrations()
                if any(value.get("id") == session or session in value.get("parties", {}).values() for value in aliases):
                    raise SelectorError("History-only aliases are not managed session selectors.") from exc
                with self._mutex:
                    native = any(value.metadata().get("native_id") == session for value in self._stores.values())
                if native:
                    raise SelectorError("Select the local managed session name or ID, not its native conversation ID.") from exc
                raise SelectorError("No unique managed session matches that local name or ID.") from exc
        else:
            with self._mutex:
                stores = list(self._stores.values())
        views = []
        for store in stores:
            try:
                snapshot = store.snapshot()
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                views.append(unavailable_channel(store.path, self.project, exc))
                continue
            meta = snapshot["session"]
            if request is not None:
                provider, generation = route(meta).request_connection(self, meta)
            else:
                provider, generation = route(meta).connection(self, meta)
            connected = bool(provider and provider.alive and meta["generation"] == generation)
            age = (datetime.now(UTC) - datetime.fromisoformat(meta["observed_at"])).total_seconds()
            can_send = (connected and model_ready(meta) and bool(meta["native_id"] or meta.get("requested_native_id")) and not snapshot["closed"]
                        and meta["state"] in states.SENDABLE)
            reason = ("The requested Codex configuration is unverified or differs from its creation receipt. Work remains held."
                      if not model_ready(meta) else "This channel is closed." if snapshot["closed"] else
                      "Conversation state is uncertain. Inspect unfinished work; reconnecting never resends uncertain work." if connected else
                      "Reconnecting the saved conversation, or connection unavailable. History remains readable.")
            if not can_send and meta.get("error"):
                reason += " " + str(meta["error"])
            for decision in snapshot["decisions"]:
                decision["can_answer"] = connected and decision["generation"] == generation and decision["state"] == "pending"
                decision["request_id"] = decision_request(snapshot, decision)
            from .session_reading import dispositions

            snapshot.update(connected=connected, can_send=can_send,
                            dispositions=dispositions(snapshot), can_resume=bool(meta["native_id"] or meta.get("enrollment")) and not can_send,
                            execution_state=meta["state"] if connected and age < 60 else "unknown",
                            parties={"main": "Coordinator", "reviewer": meta["name"]},
                            control_reason="" if can_send else reason)
            from .session_updates import supported

            if request is not None:
                candidates = [row for row in snapshot["attempts"] if row["generation"] == generation
                              and row["state"] in states.ATTEMPT_LIVE]
                active = candidates[0] if len(candidates) == 1 else None
                snapshot["configuration_held"] = not model_ready(meta)
                snapshot["scoped_control_reason"] = ("Requested configuration held." if not model_ready(meta) else
                                                      "Channel closed." if snapshot["closed"] else
                                                      "Connection or native execution unverified." if not connected else
                                                      "Use the selected request's retained facts separately from session activity.")
            else:
                active = store.active(generation)
            snapshot["update_target"] = (dict(request_id=active["request_id"], expected_turn_id=active["turn_id"],
                native_id=meta["native_id"], observed_at=meta["observed_at"], source=meta["source"])
                if connected and model_ready(meta) and supported(meta) and not snapshot["closed"] and active and active["turn_id"]
                and active["state"] in states.ATTEMPT_STARTED and meta["state"] in states.WORKING else None)
            views.append(snapshot)
        if not selection:
            seen = {view["channel"] for view in views}
            with self._mutex:
                views.extend(view for path, view in self.unavailable_channels.items() if path not in seen)
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
            view["capabilities"] = describe(view["session"]["provider"], view["session"].get("client") or {})
            project(view, declarations)
        if selection:
            selected = views[0]
            identity = dict(session_id=selected["session"]["id"])
            if request is not None:
                selected = exact_request(selected, request, declarations)
                identity["request_id"] = request
            return dict(project=str(self.project), generation=self.generation, selection=identity, sessions=[selected])
        claude = availability()
        providers = {name: describe(name, self.client if self.provider else None) for name in ("codex", "claude")}
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
