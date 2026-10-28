"""Bounded metadata discovery on an existing, verified owned Codex connection."""

from __future__ import annotations

import os
import secrets
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

from .codex_enrollment import EXECUTABLE_SHA256, VERSION, local_path
from .codex_session import ProviderError, ProviderRejected

PREVENTS = {"awkit session discover": ("F24", "F25", "F29")}
SOURCES = ("cli", "vscode", "exec", "appServer")
UNAVAILABLE = "Conversation discovery requires an existing initialized supported Codex connection in this project and home. Manual exact-ID enrollment remains available."
FAILED = "Indexed conversation listing failed. Refresh or use manual exact-ID enrollment."
UNSUPPORTED = "This initialized Codex connection does not support indexed conversation listing. Manual exact-ID enrollment remains available."
INVALID_CURSOR = "This conversation page expired. Refresh to start again."


def project_response(message, project, limit=50):
    """Strip native bodies/errors before a discovery response enters a request queue."""
    try:
        if "error" in message:
            error = message["error"]
            code = error.get("code") if isinstance(error, dict) else None
            if type(code) is int and code in (-32601, -32602):
                return dict(error=dict(code=code))
            return dict(error="Conversation discovery is unavailable.")
        result = message["result"]
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise ValueError
        if len(result["data"]) > limit:
            raise ValueError
        rows = []
        expected = local_path(project)
        for thread in result["data"]:
            if not isinstance(thread, dict):
                raise ValueError
            ident = thread.get("id")
            if not isinstance(ident, str) or str(uuid.UUID(ident)) != ident:
                raise ValueError
            if local_path(thread["cwd"]) != expected or thread.get("source") not in SOURCES:
                raise ValueError
            name = thread.get("name")
            if name is not None and not isinstance(name, str):
                raise ValueError
            times = [thread.get(key) for key in ("createdAt", "updatedAt")]
            if any(value is not None and type(value) is not int for value in times):
                raise ValueError
            rows.append(dict(id=ident, name=name, project=str(expected), source=thread["source"],
                             created_at=times[0], updated_at=times[1]))
        cursor = result.get("nextCursor")
        if cursor is not None and (not isinstance(cursor, str) or not cursor or len(cursor) > 8192):
            raise ValueError
        return dict(result=dict(conversations=rows, next_cursor=cursor))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        return dict(error="Conversation discovery is unavailable.")


def _eligible(controller, client, generation, evidence):
    """Validate recorded launch/initialization facts without inspecting or starting a runtime."""
    try:
        if (client is None or not client.alive or not callable(getattr(client, "discover_threads", None))
                or evidence.get("version") != VERSION or evidence.get("executable_sha256") != EXECUTABLE_SHA256
                or local_path(client.project) != controller.project or len(controller.command) != 1
                or len(client.command) != 1):
            return False
        executable = local_path(shutil.which(controller.command[0]) or controller.command[0])
        launched = local_path(shutil.which(client.command[0]) or client.command[0])
        if executable != launched or (evidence.get("executable") and local_path(evidence["executable"]) != launched):
            return False
        home = local_path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        if local_path(client.initialization["codexHome"]) != home:
            return False
        if evidence.get("codex_home") and local_path(evidence["codex_home"]) != home:
            return False
        return bool(generation)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError):
        return False


def _capture(controller):
    if controller._closed or controller._stop.is_set():
        return None
    for ident, client in controller.enrolled_clients.items():
        store = controller._stores.get(ident)
        if store is None:
            continue
        meta = store.metadata()
        evidence = (meta.get("enrollment") or {}).get("runtime") or {}
        generation = getattr(client, "generation", None)
        if (meta.get("provider") == "codex" and meta.get("generation") == generation
                and local_path(meta["project"]) == controller.project
                and _eligible(controller, client, generation, evidence)):
            return client, generation, ident, (str(local_path(client.initialization["codexHome"])), tuple(client.command))
    client = controller.provider
    if _eligible(controller, client, controller.generation, controller.client):
        return client, controller.generation, None, (str(local_path(client.initialization["codexHome"])), tuple(client.command))
    return None


def discover(controller, *, cursor=None, limit=20):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("Conversation page limit must be an integer from 1 to 50.")
    if cursor is not None and (not isinstance(cursor, str) or not cursor or len(cursor) > 200):
        raise ValueError("Conversation cursor must be a nonempty page token.")

    def unavailable(reason):
        return dict(available=False, reason=reason, project=str(controller.project), conversations=[], next_cursor=None)

    with controller._mutex:
        try:
            captured = _capture(controller)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, sqlite3.Error):
            captured = None
        if captured is None:
            return unavailable(UNAVAILABLE)
        client, generation, owner, launch_scope = captured
        pages = getattr(controller, "_discovery_pages", None)
        if pages is None:
            pages = controller._discovery_pages = {}
        # Readers have independent sequences; retain only bounded, expiring cursor metadata.
        scope = (client, generation, owner, (str(controller.project), launch_scope), limit)
        instant = time.monotonic()
        for token, entry in list(pages.items()):
            if entry["expires"] <= instant or entry["scope"][:4] != scope[:4]:
                del pages[token]
        if cursor is None:
            native_cursor = None
            seen = ()
        else:
            entry = pages.get(cursor)
            if entry is None or entry["scope"] != scope:
                return unavailable(INVALID_CURSOR)
            native_cursor, seen = entry["cursor"], entry["seen"]
        params = dict(cwd=str(controller.project), useStateDbOnly=True, archived=False, limit=limit,
                      sortKey="updated_at", sortDirection="desc", modelProviders=[], sourceKinds=list(SOURCES))
        if native_cursor is not None:
            params["cursor"] = native_cursor
    try:
        result = client.discover_threads(params)
    except ProviderRejected as exc:
        return unavailable(UNSUPPORTED if exc.code in (-32601, -32602) else FAILED)
    except (OSError, ValueError, KeyError, TypeError, ProviderError):
        return unavailable(FAILED)
    with controller._mutex:
        try:
            current = _capture(controller)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, sqlite3.Error):
            current = None
        if current != captured:
            return unavailable(INVALID_CURSOR)
        registered = set()
        for store in controller._stores.values():
            meta = store.metadata()
            if meta.get("provider") == "codex":
                registered.add((meta.get("enrollment") or {}).get("thread_id") or meta.get("native_id"))
        rows = [dict(row, registered=row["id"] in registered) for row in result["conversations"]]
        token = None
        if result["next_cursor"] is not None:
            if result["next_cursor"] in (*seen, native_cursor) or len(seen) >= 100:
                return unavailable(INVALID_CURSOR)
            token = secrets.token_urlsafe(24)
            while len(pages) >= 128:
                del pages[next(iter(pages))]
            pages[token] = dict(scope=scope, cursor=result["next_cursor"],
                                seen=(*seen, result["next_cursor"]), expires=time.monotonic() + 300)
        return dict(available=True, reason=None, project=str(controller.project), conversations=rows, next_cursor=token)
