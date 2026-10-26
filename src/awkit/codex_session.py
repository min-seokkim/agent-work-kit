"""One owned Codex App Server connection over documented JSONL stdio."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading

from . import __version__


class ProviderError(RuntimeError):
    pass


class CodexSession:
    def __init__(self, command, project, callback, *, timeout=30, experimental=False):
        self.callback = callback
        self.timeout = timeout
        self.failure = None
        self._closed = False
        self._serial = 0
        self._pending = {}
        self._lock = threading.RLock()
        self._events = queue.Queue()
        self.stderr = ""
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen([*command, "app-server", "--stdio"], cwd=project,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        creationflags=flags)
        self._threads = [threading.Thread(target=target, daemon=True) for target in
                         (self._read, self._dispatch, self._read_stderr)]
        for thread in self._threads:
            thread.start()
        try:
            params = {"clientInfo": {"name": "awkit", "title": "Agent Work Kit", "version": __version__}}
            if experimental:
                params["capabilities"] = {"experimentalApi": True}
            self.initialization = self.call("initialize", params)
            self.notify("initialized", {})
        except BaseException:
            self.close()
            raise

    @property
    def alive(self):
        return not self._closed and self.failure is None and self.process.poll() is None

    def _write(self, message):
        with self._lock:
            if not self.alive:
                raise ProviderError(self.failure or "Owned provider connection is unavailable.")
            try:
                self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
                self.process.stdin.flush()
            except (OSError, ValueError) as exc:
                raise ProviderError("Provider write failed; admission may be uncertain.") from exc

    def notify(self, method, params):
        self._write(dict(method=method, params=params))

    def respond(self, rpc_id, result):
        self._write(dict(id=rpc_id, result=result))

    def call(self, method, params, *, on_request=None):
        response = queue.Queue(maxsize=1)
        with self._lock:
            self._serial += 1
            ident = f"awkit-{self._serial}"
            self._pending[ident] = response
        try:
            if on_request is not None:
                on_request(ident)  # Persist the request/attempt/RPC binding before any write.
            self._write(dict(id=ident, method=method, params=params))
            try:
                message = response.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise ProviderError(f"{method} timed out; admission is uncertain and will not be replayed.") from exc
            if "error" in message:
                raise ProviderError(f"{method}: {message['error']}")
            return message["result"]
        finally:
            with self._lock:
                self._pending.pop(ident, None)

    def _fail(self, reason):
        with self._lock:
            if self.failure is not None:
                return
            self.failure = reason
            for response in self._pending.values():
                try:
                    response.put_nowait(dict(error=reason))
                except queue.Full:
                    pass
        self._events.put(dict(method="awkit/connectionError", params=dict(reason=reason)))

    def _read(self):
        try:
            while True:
                raw = self.process.stdout.readline(16 * 1024 * 1024 + 1)
                if not raw:
                    break
                if len(raw) > 16 * 1024 * 1024 or not raw.endswith(b"\n"):
                    raise ValueError("Invalid or oversized provider JSONL frame")
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ValueError("Provider frame is not an object")
                if "method" in message:
                    self._events.put(message)
                elif "id" in message:
                    with self._lock:
                        response = self._pending.get(message["id"])
                        if response is not None:
                            response.put_nowait(message)
                        else:
                            self._events.put(dict(method="awkit/lateResponse", params=message))
                else:
                    raise ValueError("Provider frame has no method or response ID")
        except (OSError, ValueError, KeyError, TypeError, queue.Full) as exc:
            self._fail(f"Provider stream failed ({type(exc).__name__}); state is unknown.")
        finally:
            if not self._closed:
                self._fail("Owned provider stream ended; conversation state is unknown.")

    def _dispatch(self):
        while True:
            message = self._events.get()
            if message is None:
                return
            try:
                self.callback(message)
            except Exception as exc:
                self._fail(f"Provider event handling failed ({type(exc).__name__}); state is unknown.")

    def _read_stderr(self):
        try:
            while raw := self.process.stderr.readline(8192):
                self.stderr = (self.stderr + raw.decode("utf-8", errors="replace"))[-8192:]
        except (OSError, ValueError):
            pass

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for response in self._pending.values():
                try:
                    response.put_nowait(dict(error="Controller closed; admission may be uncertain."))
                except queue.Full:
                    pass
            try:
                self.process.stdin.close()
            except (OSError, ValueError):
                pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()  # Only the process created by this connection.
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self._events.put(None)
        for thread in self._threads:
            if thread is not threading.current_thread():
                thread.join(timeout=2)
        self.process.stdout.close()
        self.process.stderr.close()
