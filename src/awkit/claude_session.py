"""Optional owned Claude SDK connection. No one-shot calls or implicit replay."""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import importlib.metadata
import json
import os
import shutil
import threading
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path

from .codex_session import ProviderError
from .session_models import claude_observe, claude_options, claude_submitted
from .session_store import now

SDK_VERSION = "0.2.174"
PREVENTS = {"awkit session": ("F25",)}


def result_outcome(reason, is_error):
    if reason in ("aborted_streaming", "aborted_tools"):
        return "interrupted"
    if is_error:
        return "failed"
    if reason == "max_turns":
        return "max_turns"
    return "completed" if reason in (None, "completed") else "unknown termination"


def availability():
    try:
        version = importlib.metadata.version("claude-agent-sdk")
    except importlib.metadata.PackageNotFoundError:
        return dict(available=False, reason="Install agent-work-kit[claude] in this controller's environment.")
    return dict(available=version == SDK_VERSION, sdk_version=version,
                reason="" if version == SDK_VERSION else f"This integration requires claude-agent-sdk=={SDK_VERSION}.")


def executable(cli_path):
    if cli_path:
        path = Path(shutil.which(str(cli_path)) or cli_path)
    else:
        distribution = importlib.metadata.distribution("claude-agent-sdk")
        path = Path(distribution.locate_file("claude_agent_sdk/_bundled/" + ("claude.exe" if os.name == "nt" else "claude")))
    if not path.is_file():
        raise ProviderError("Claude executable is unavailable. Select an unmodified native binary or reinstall the optional SDK.")
    path = path.resolve()
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return path, digest


def recover_local_results(store):
    """A recorded correlated terminal result survives a crash before reply commit."""
    with store.channel.transaction(write=False) as conn:
        events = [(row["generation"], json.loads(row["payload"])) for row in conn.execute(
            "SELECT generation,payload FROM awkit_events WHERE method='claude/result' ORDER BY seq")]
    for attempt in store.snapshot()["attempts"]:
        if attempt["state"] in ("returned", "failed", "no-reply") or not attempt["input_echoed"]:
            continue
        for generation, result in events:
            if (generation != attempt["generation"] or result.get("matched_input") != attempt["provider_input_id"]
                    or result.get("session_id") != store.metadata().get("native_id")
                    or (result.get("origin") or {}).get("kind") != "human"):
                continue
            outcome = result_outcome(result.get("terminal_reason"), result.get("is_error"))
            store.claude_finish(generation, attempt["provider_input_id"], result.get("uuid"), outcome,
                                result.get("result") or "", result.get("errors"))
            break


class ClaudeSession:
    def __init__(self, store, *, cli_path=None, resume=False):
        runtime = availability()
        if not runtime["available"]:
            raise ProviderError(runtime["reason"])
        self.store = store
        self.generation = store.metadata()["generation"]
        self.cli_path = cli_path
        self.resuming = resume
        self.alive = False
        self.error = None
        self.initialization = {}
        self._ready = threading.Event()
        self._pending = {}
        self._current = None
        self._echo = False
        self._ambiguous = False
        self._context_input = None
        self._idle_observed = False
        self._state_sequence = 0
        self._reader_task = None
        self._loop = None
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        if not self._ready.wait(70):
            self.close()
            raise ProviderError("Claude SDK initialization timed out; admission remains uncertain.")
        if not self.alive:
            raise ProviderError(self.error or "Claude SDK connection unavailable.")

    def _thread_main(self):
        try:
            asyncio.run(self._run())
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.store.uncertain(self.generation, self.error)
        finally:
            self.alive = False
            self._ready.set()

    async def _run(self):
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, get_session_info

        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        meta = self.store.metadata()
        selected_cli, digest = executable(self.cli_path)
        if self.resuming:
            from claude_agent_sdk import get_session_messages

            native_id = meta.get("native_id")
            info = get_session_info(native_id, directory=meta["project"]) if native_id else None
            if info is None or info.session_id != native_id:
                raise ProviderError("The exact owned Claude session is unavailable. No replacement or resend was made.")
            unresolved = [row for row in self.store.snapshot()["attempts"] if row["state"] == "unresolved"]
            if unresolved:
                history = get_session_messages(native_id, directory=meta["project"], limit=1000)
                self.store.update(recovery_evidence=dict(source="known-ID public SDK history; no result/origin guarantee",
                    observed_at=now(), native_id=native_id, returned_messages=len(history), returned_limit=1000,
                    inputs=[dict(provider_input_id=row["provider_input_id"],
                                 visible_occurrences=sum(item.uuid == row["provider_input_id"] for item in history)) for row in unresolved],
                    terminal_recovery="unresolved; input presence or absence cannot authorize a reply or resend"))
        options = ClaudeAgentOptions(
            cwd=meta["project"], cli_path=selected_cli,
            session_id=None if self.resuming else meta["requested_native_id"],
            resume=meta["native_id"] if self.resuming else None,
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": meta["startup_context"]["developer_instructions"]},
            setting_sources=["user", "project", "local"], permission_mode="default",
            extra_args={"replay-user-messages": None}, can_use_tool=self._permission,
            env={"CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS": "1"},
            **claude_options(meta),
        )
        self._client = ClaudeSDKClient(options)
        try:
            await self._client.connect()
            info = await self._client.get_server_info() or {}
            # Never retain account metadata, credential-bearing environment or private command descriptions.
            self.initialization = {key: info[key] for key in
                                   ("claude_code_version", "current_permission_mode", "session_state", "pid") if key in info}
            prior = meta["permissions"].get("observed", {})
            mode = info.get("current_permission_mode")
            if mode != "default":
                self.store.update(returned_scope=self.initialization)
                raise ProviderError("Claude did not report the submitted default permission mode; queued work remains held.")
            if self.resuming and prior.get("permissionMode", "default") != mode:
                self.store.update(returned_scope=self.initialization)
                raise ProviderError("Claude resumed permission mode differs or is unreported; queued work remains held.")
            permissions = dict(meta["permissions"], observed=dict(prior, permissionMode=mode),
                               source="SDK initialize; partial native policy receipt",
                               effective_rules="unverified", windows_sandbox="not established")
            self.alive = True
            claude_submitted(self.store)
            self.store.update(permissions=permissions, client=dict(sdk_version=SDK_VERSION, executable=str(selected_cli),
                              executable_sha256=digest, **self.initialization),
                              state="idle" if info.get("session_state") == "idle" else "unknown",
                              source="SDK initialize session_state", observed_at=now(), error=None,
                              startup_context=dict(meta["startup_context"], admission="native connection initialized; identity awaits a provider frame"))
            self._reader_task = asyncio.create_task(self._read())
            self._ready.set()
            await self._stop.wait()
        finally:
            if self._reader_task:
                self._reader_task.cancel()
                await asyncio.gather(self._reader_task, return_exceptions=True)
            # Same task/context that connected also disconnects the SDK's AnyIO scopes.
            await self._client.disconnect()
            for decision in self.store.snapshot()["decisions"]:
                if decision["generation"] == self.generation and decision["state"] in ("pending", "sending", "sent"):
                    self.store.decision_state(decision["id"], "route unavailable")

    async def _read(self):
        try:
            async for message in self._client.receive_messages():
                self._message(message)
            raise ProviderError("Claude SDK message stream ended.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.alive = False
            self.store.uncertain(self.generation, self.error)
            self._stop.set()

    def _identity(self, ident):
        meta = self.store.metadata()
        expected = meta.get("native_id") or meta["requested_native_id"]
        if ident != expected:
            self.store.update(returned_native_id=ident)
            raise ProviderError("Claude returned a different native session identity; no replacement was bound.")
        self.store.update(native_id=ident, returned_native_id=ident,
                          startup_context=dict(meta["startup_context"], admission="native identity observed"))

    def _message(self, message):
        name = type(message).__name__
        origin = getattr(message, "origin", None)
        ident = getattr(message, "uuid", None)
        if name == "SystemMessage":
            data = message.data
            if message.subtype == "session_state_changed":
                if data.get("session_id"):
                    self._identity(data["session_id"])
                state = data.get("state")
                self._idle_observed = state == "idle" and (self._current is None or self._echo)
                self._state_sequence += 1
                self.store.event(self.generation, "claude/state", dict(frame=data, observation_index=self._state_sequence))
                fields = dict(native_state=state, observed_at=now(), source="Claude session_state_changed")
                if state == "idle":
                    if self._current is None and self.store.metadata()["state"] != "unknown":
                        fields["state"] = "idle"
                elif state == "running":
                    fields["state"] = "running" if self._current else "waiting for idle"
                elif state == "requires_action":
                    fields["state"] = "decision needed"
                else:
                    fields.update(state="unknown", error="Claude reported an unknown native activity state.")
                self.store.update(**fields)
                return
            if message.subtype == "init":
                self._identity(data.get("session_id"))
                observed = {key: data[key] for key in ("permissionMode", "cwd", "model", "claude_code_version", "tools") if key in data}
                if data.get("cwd") and Path(data["cwd"]).resolve() != Path(self.store.metadata()["project"]).resolve():
                    self.store.update(returned_scope=observed)
                    raise ProviderError("Claude init returned a different project.")
                if data.get("permissionMode") != "default":
                    self.store.update(returned_scope=observed)
                    raise ProviderError("Claude init changed the submitted permission mode; no reply was assigned.")
                meta = self.store.metadata()
                self.store.update(permissions=dict(meta["permissions"], observed=observed,
                                  source="native system/init; partial policy receipt"), model=data.get("model"), returned_scope=None)
                claude_observe(self.store, data.get("model"))
            return
        if name == "UserMessage":
            matched = self._current and ident == self._current["id"] and origin and origin.get("kind") == "human"
            if matched:
                self._echo = self.store.claude_echo(self.generation, ident, self.store.metadata()["native_id"])
            elif origin and origin.get("kind") == "human" and not getattr(message, "parent_tool_use_id", None):
                self._ambiguous = True
            if not getattr(message, "parent_tool_use_id", None):
                self._context_input = ident if matched else None
            self.store.event(self.generation, "claude/input", dict(uuid=ident, origin=origin, matched=bool(matched)))
        elif name == "ResultMessage":
            self._identity(message.session_id)
            payload = asdict(message) if is_dataclass(message) else vars(message).copy()
            payload["matched_input"] = self._current["id"] if self._current and self._echo and not self._ambiguous and isinstance(ident, str) and ident and origin and origin.get("kind") == "human" else None
            self.store.event(self.generation, "claude/result", payload)
            if origin and origin.get("kind") == "human":
                if payload["matched_input"]:
                    outcome = result_outcome(message.terminal_reason, message.is_error)
                    finished = self.store.claude_finish(self.generation, payload["matched_input"], ident, outcome,
                                                        message.result or "", message.errors if message.is_error else None,
                                                        idle_observed=self._idle_observed)
                    if not finished:
                        self.store.uncertain(self.generation, "Claude result is already bound or not correlated; no new reply was assigned.")
                elif self._current:
                    self.store.uncertain(self.generation, "Claude result lacks unique input/result correlation; no reply was assigned.")
                self._current = None
                self._echo = False
                self._ambiguous = False
                self._context_input = None
            elif self._current and (not origin or origin.get("kind") not in
                                     ("peer", "channel", "task-notification", "coordinator", "observer", "auto-continuation", "observer-activity")):
                self._ambiguous = True
                self.store.uncertain(self.generation, "Unattributed Claude result; delivery remains unresolved without replay.")
            # Other origins remain visible provider events, never application replies.

    async def _permission(self, tool_name, tool_input, context):
        from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

        callback_id = "sdk-callback-" + str(uuid.uuid4())
        agent_id = getattr(context, "agent_id", None)
        params = dict(tool=tool_name, input=tool_input, tool_use_id=context.tool_use_id,
                      provider_input_id=self._context_input if agent_id is None else None, agent_id=agent_id,
                      threadId=self.store.metadata().get("native_id"), callback_route_id=callback_id,
                      native_request_id=None, route_kind="SDK callback; native control request ID is not exposed")
        choices = ["deny"] if tool_name == "AskUserQuestion" else ["allow", "deny"]
        ident = self.store.add_decision(self.generation, callback_id, "claude/permission", params, choices)
        future = asyncio.get_running_loop().create_future()
        self._pending[ident] = future
        try:
            answer = await future
            if isinstance(answer, dict):
                return PermissionResultAllow(updated_input=dict(tool_input, answers=answer["answers"]))
            return PermissionResultAllow() if answer == "allow" else PermissionResultDeny(message="Declined through the originating awkit decision.")
        finally:
            self._pending.pop(ident, None)
            if not future.done() or future.cancelled():
                self.store.decision_state(ident, "route unavailable")

    async def _query(self, claim):
        if self._current is not None:
            raise ProviderError("Another application input is still in flight.")
        self._current, self._echo, self._ambiguous, self._idle_observed = claim, False, False, False

        async def frames():
            yield dict(type="user", uuid=claim["id"], origin={"kind": "human"},
                       message=dict(role="user", content=claim["request"]["body"]), parent_tool_use_id=None)

        await self._client.query(frames())

    def submit(self, claim):
        self._call(self._query(claim))

    def _call(self, coroutine):
        if not self.alive or self._loop is None:
            coroutine.close()
            raise ProviderError(self.error or "Claude connection is unavailable.")
        try:
            return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(timeout=15)
        except (TimeoutError, concurrent.futures.CancelledError) as exc:
            raise ProviderError("Claude operation outcome is uncertain; it was not resent.") from exc
        except (ValueError, ProviderError):
            raise
        except Exception as exc:
            raise ProviderError(f"Claude SDK operation failed ({type(exc).__name__}): {exc}") from exc

    def decide(self, ident, answer):
        async def respond():
            future = self._pending.get(ident)
            if future is None or future.done():
                raise ValueError("The original Claude callback is no longer pending.")
            row = next(row for row in self.store.snapshot()["decisions"] if row["id"] == ident)
            if isinstance(answer, dict):
                questions = row["params"]["input"].get("questions", [])
                if row["params"]["tool"] != "AskUserQuestion" or set(answer) != {"answers"} or not isinstance(answer["answers"], dict):
                    raise ValueError("Provide answers for the original AskUserQuestion invocation.")
                if set(answer["answers"]) != {item["question"] for item in questions} or not all(
                        isinstance(value, str) or isinstance(value, list) and all(isinstance(item, str) for item in value)
                        for value in answer["answers"].values()):
                    raise ValueError("Answer every original question by its exact text.")
            elif answer not in row["choices"]:
                raise ValueError("Select a choice from the original Claude callback.")
            self.store.answer_intent(self.generation, ident, answer)
            future.set_result(answer)
            return dict(state="submitted to SDK callback", decision=ident, native_resolution="unverified")

        return self._call(respond())

    def interrupt(self):
        self._call(self._client.interrupt())

    def close(self):
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(timeout=15)
        if self._thread.is_alive():
            raise ProviderError("The owned Claude SDK connection did not finish stopping; shutdown is unverified.")
