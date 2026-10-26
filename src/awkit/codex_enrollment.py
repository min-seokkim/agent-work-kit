"""Explicit local enrollment on one verified native runtime; no task or instruction injection."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from .session_recovery import reconcile, recover_completed
from .session_store import now

PREVENTS = {"awkit session enroll": ("F24", "F25", "F29")}
VERSION = "codex-cli 0.164.0-alpha.11.1"
EXECUTABLE_SHA256 = "4fd2f057bad603bf53dc202457ffd0c3591de62e867a8b01e73816e3fbce5a73"
POLICY_FIELDS = ("cwd", "sandbox", "approvalPolicy", "approvalsReviewer", "runtimeWorkspaceRoots", "activePermissionProfile")
REQUIRED_POLICY_FIELDS = POLICY_FIELDS[:4]


def local_path(value):
    """Normalize the native Windows extended-drive spelling, retaining local-only scope."""
    value = os.fspath(value)
    if os.name == "nt" and value.startswith("\\\\?\\"):
        value = value[4:]
    if not Path(value).is_absolute() or value.startswith("\\\\"):
        raise ValueError("Enrollment requires an absolute local path.")
    return Path(value).resolve(strict=True)


def runtime(command):
    if len(command) != 1:
        raise ValueError("Enrollment requires the supported unmodified native executable, without wrapper/config arguments.")
    executable = Path(shutil.which(command[0]) or command[0]).resolve(strict=True)
    with executable.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != EXECUTABLE_SHA256:
        raise ValueError("This executable is outside the verified Codex enrollment runtime; no connection was opened.")
    result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode or result.stdout.strip() != VERSION:
        raise ValueError("Codex enrollment runtime version is unsupported.")
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve(strict=True)
    return dict(executable=str(executable), executable_sha256=digest, version=VERSION, codex_home=str(home))


def policy(result, project, native_id, home):
    if not isinstance(result, dict) or not isinstance(result.get("thread"), dict):
        raise ValueError("Native enrollment response has no known thread structure.")
    thread = result["thread"]
    if (thread.get("id") != native_id or local_path(thread["cwd"]) != project
            or local_path(result["cwd"]) != project):
        raise ValueError("Enrollment returned a different conversation or project; no task was sent.")
    if thread.get("canAcceptDirectInput") is not True:
        raise ValueError("Provider direct input is restricted or unreported for this conversation.")
    if not isinstance(thread.get("status"), dict) or thread["status"].get("type") != "idle":
        raise ValueError("The selected conversation is not idle; active or unknown ownership is not taken over.")
    path = thread.get("path")
    if (thread.get("ephemeral") is not False or not isinstance(path, str) or not Path(path).is_absolute()
            or not local_path(path).is_relative_to(local_path(home) / "sessions")):
        raise ValueError("The selected conversation's same-home local store was not established.")
    for key in REQUIRED_POLICY_FIELDS:
        if key not in result:
            raise ValueError(f"Native required policy field {key} is missing.")
    scope = {key: result[key] for key in POLICY_FIELDS if key in result}
    sandbox = scope["sandbox"]
    if (not isinstance(sandbox, dict) or sandbox.get("type") not in ("readOnly", "workspaceWrite")
            or not isinstance(sandbox.get("networkAccess"), bool)
            or scope["approvalPolicy"] not in ("on-request", "on-failure", "untrusted", "never")
            or scope["approvalsReviewer"] not in ("user", "auto_review")):
        raise ValueError("Native permission scope is unknown or unsupported; no task was sent.")
    if sandbox["type"] == "workspaceWrite":
        roots = sandbox.get("writableRoots")
        if (not isinstance(roots, list) or any(not isinstance(p, str) or not Path(p).is_absolute() for p in roots)
                or not isinstance(sandbox.get("excludeTmpdirEnvVar"), bool)
                or not isinstance(sandbox.get("excludeSlashTmp"), bool)):
            raise ValueError("Native workspace permission details are incomplete.")
    allowed = {"type", "networkAccess"}
    if sandbox["type"] == "workspaceWrite":
        allowed |= {"writableRoots", "excludeTmpdirEnvVar", "excludeSlashTmp"}
    if set(sandbox) - allowed:
        raise ValueError("Native sandbox contains unsupported permission details.")
    if "runtimeWorkspaceRoots" in scope:
        roots = scope["runtimeWorkspaceRoots"]
        if not isinstance(roots, list) or any(not isinstance(p, str) or not Path(p).is_absolute() for p in roots):
            raise ValueError("Native returned runtime workspace roots are uninterpretable.")
    if "activePermissionProfile" in scope and scope["activePermissionProfile"] is not None:
        profile = scope["activePermissionProfile"]
        if (not isinstance(profile, dict) or not isinstance(profile.get("id"), str) or not profile["id"]
                or set(profile) - {"id", "extends"}
                or (profile.get("extends") is not None and not isinstance(profile["extends"], str))):
            raise ValueError("Native returned profile provenance is uninterpretable.")
    return scope


def observe(controller, store, client):
    meta = store.metadata()
    selected = meta["enrollment"]["thread_id"]
    # Resume acquires the native writer lock. This private process has no other clients.
    # No project, policy, history, role or base-instruction override is submitted.
    result = client.call("thread/resume", {"threadId": selected, "excludeTurns": True})
    if not isinstance(result, dict) or not isinstance(result.get("thread"), dict):
        raise ValueError("Native enrollment response has no known thread structure.")
    thread = result.get("thread", {})
    store.update(admission_observation=dict(
        thread={key: thread.get(key) for key in ("id", "cwd", "path", "ephemeral", "status", "canAcceptDirectInput")},
        scope={key: result[key] for key in POLICY_FIELDS if key in result},
        unexposed_fields=[key for key in POLICY_FIELDS if key not in result]))
    scope = policy(result, controller.project, selected, meta["enrollment"]["runtime"]["codex_home"])
    prior = meta["enrollment"].get("policy")
    if prior is not None and scope != prior:
        store.update(returned_scope=scope)
        raise ValueError("Enrolled native policy changed; saved and returned scopes are retained without dispatch.")
    return result, scope


def resume(controller, store):
    meta = store.metadata()
    selected = meta["enrollment"]["thread_id"]
    if not isinstance(selected, str) or str(uuid.UUID(selected)) != selected or meta["native_id"] not in (None, selected):
        raise ValueError("Saved enrolled identity is invalid or conflicts with the selected native identity.")
    with controller._mutex:
        for other in controller._stores.values():
            data = other.metadata()
            target = (data.get("enrollment") or {}).get("thread_id") or data.get("native_id")
            if data["id"] != meta["id"] and target == selected:
                raise ValueError("Another local registration selects this native identity; no writer was opened.")
    old = controller.enrolled_clients.pop(meta["id"], None)
    if old:
        old.close()
    inspected = runtime(controller.command)
    prior_runtime = meta["enrollment"].get("runtime")
    if prior_runtime is not None and inspected != prior_runtime:
        raise ValueError("Enrolled runtime/home changed; the selected conversation was not resumed elsewhere.")
    recover_completed(store)
    generation = str(uuid.uuid4())
    store.reconnect(generation)
    enrollment = dict(meta["enrollment"], runtime=inspected, admission="native resume pending")
    store.update(generation=generation, state="reconnecting", enrollment=enrollment, error=None,
                 observed_at=now(), source="dedicated Codex enrollment connection")
    client = None
    try:
        client = controller.provider_factory([inspected["executable"]], controller.project,
            lambda message: controller._message(message, generation=generation, owned_id=meta["id"]), experimental=True)
        client.generation = generation
        home = client.initialization.get("codexHome")
        if not home or Path(home).resolve() != Path(inspected["codex_home"]).resolve():
            raise ValueError("Native Codex home differs or is unreported.")
        controller.enrolled_clients[meta["id"]] = client
        result, scope = observe(controller, store, client)
        enrollment = dict(enrollment, policy=scope, admission="native writer resume accepted")
        store.update(native_id=enrollment["thread_id"], returned_native_id=result["thread"]["id"],
                     enrollment=enrollment, permissions=dict(scope, source="native exact-ID enrollment response"),
                     client=dict(inspected, owned_pid=client.process.pid), startup_context=None, returned_scope=None)
        reconcile(controller, store, client)
    except BaseException:
        controller.enrolled_clients.pop(meta["id"], None)
        if client:
            client.close()
        raise
