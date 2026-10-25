"""Loopback human controls and agent client for the same project controller."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from .sessions import SessionController


class SessionServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, controller, *, port=0, token=None):
        self.controller = controller
        self.token = token or secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), SessionHandler)
        self.url = f"http://127.0.0.1:{self.server_port}"


class SessionHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # No bearer tokens, prompts or task bodies in an access log.

    def _reply(self, status, data, content_type="application/json; charset=utf-8"):
        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self):
        expected_host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != expected_host:
            self._reply(403, dict(schema=1, error="Unrecognized local controller host."))
            return False
        origin = self.headers.get("Origin")
        if origin and origin != self.server.url:
            self._reply(403, dict(schema=1, error="Cross-origin control is unavailable."))
            return False
        supplied = self.headers.get("Authorization", "")
        if not secrets.compare_digest(supplied, "Bearer " + self.server.token):
            self._reply(403, dict(schema=1, error="Open the controller's capability URL to access this project."))
            return False
        return True

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/":
            self._reply(200, files("awkit").joinpath("session_ui.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/status" and self._authorized():
            try:
                self._reply(200, dict(schema=1, result=self.server.controller.status()))
            except (OSError, ValueError, sqlite3.Error) as exc:
                self._reply(503, dict(schema=1, error=str(exc)))
        elif path != "/api/status":
            self._reply(404, dict(schema=1, error="Unknown controller route."))

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/command":
            self._reply(404, dict(schema=1, error="Unknown controller route."))
            return
        if not self._authorized():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2 * 1024 * 1024:
                raise ValueError("Controller commands require a JSON body of at most 2 MiB.")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Controller commands use application/json.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or not isinstance(data.get("args", {}), dict):
                raise ValueError("Invalid controller command.")
            action, args = data.get("action"), data.get("args", {})
            controller = self.server.controller
            if action == "create":
                result = controller.create(**args)
            elif action == "send":
                result = controller.send(**args)
            elif action == "register":
                result = controller.register_history(**args)
            elif action == "decide":
                result = controller.decide(**args)
            elif action == "interrupt":
                result = controller.interrupt(**args)
            elif action == "resume":
                result = controller.resume(**args)
            elif action == "cancel":
                result = controller.cancel(**args)
            elif action == "stop" and not args:
                result = dict(state="controller stopping", recovery="History and unfinished work remain. Stopping does not establish task cancellation or success.")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                raise ValueError("Unsupported controller action.")
            self._reply(200, dict(schema=1, result=result))
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, RuntimeError) as exc:
            self._reply(400, dict(schema=1, error=str(exc)))


def endpoint(project):
    project = Path(project).resolve()
    path = project / ".awkit/sessions/controller.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    url = urllib.parse.urlsplit(data["url"])
    if (data.get("schema") != 1 or Path(data.get("project", "")).resolve() != project
            or url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port
            or url.username or url.password or url.path or url.query or url.fragment
            or not isinstance(data.get("token"), str) or len(data["token"]) < 32):
        raise ValueError("Invalid local controller endpoint; no request was sent.")
    return data


def request(project, action="status", args=None):
    data = endpoint(project)
    headers = dict(Authorization="Bearer " + data["token"])
    body = None
    route = "/api/status"
    if action != "status":
        route = "/api/command"
        headers["Content-Type"] = "application/json"
        body = json.dumps(dict(action=action, args=args or {}), ensure_ascii=False).encode("utf-8")
    call = urllib.request.Request(data["url"] + route, data=body, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(call, timeout=45) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        with exc:
            error = json.loads(exc.read()).get("error", str(exc))
        raise ValueError(error) from exc
    except (OSError, ValueError, urllib.error.URLError) as exc:
        key = (args or {}).get("key")
        detail = f" Client key: {key}." if key else ""
        raise ValueError("Controller response unavailable; admission may be uncertain. Inspect state before repeating."
                         + detail) from exc
    if result.get("schema") != 1 or "result" not in result:
        raise ValueError("Unsupported controller response; do not repeat an uncertain action automatically.")
    return result["result"]


def serve(project, command, *, port=0, record=None):
    if not 0 <= port <= 65535:
        raise ValueError("The loopback port must be between 0 and 65535.")
    controller = SessionController(project, command, record=record)
    server = None
    path = controller.directory / "controller.json"
    try:
        server = SessionServer(controller, port=port)
        data = dict(schema=1, project=str(controller.project), generation=controller.generation,
                    url=server.url, token=server.token, pid=os.getpid())
        temporary = path.with_name("endpoint-" + uuid.uuid4().hex + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        print(json.dumps(dict(schema=1, project=str(controller.project),
                              url=server.url + "/#token=" + server.token, generation=controller.generation)), flush=True)
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.server_close()
        controller.close()
        try:
            if server and json.loads(path.read_text())["token"] == server.token:
                path.unlink()
        except (OSError, ValueError, KeyError):
            pass
    return 0
