"""Discovery fixtures contain fictional metadata and no provider processes."""

import io
import json
import os
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from awkit.codex_enrollment import EXECUTABLE_SHA256, VERSION
from awkit.codex_session import CodexSession, ProviderError, ProviderRejected
from awkit.session_discovery import INVALID_CURSOR, UNSUPPORTED, discover, project_response

NATIVE = "01234567-89ab-4cde-8fab-0123456789ab"
SECRET = "FICTIONAL_PREVIEW_MUST_NOT_ESCAPE"


def native(project, *, cursor=None, **overrides):
    row = dict(id=NATIVE, name="Fictional review", cwd=str(project), source="cli", createdAt=10, updatedAt=20,
               preview=SECRET, turns=[{"text": SECRET}], **overrides)
    return dict(result=dict(data=[row], nextCursor=cursor, extra=SECRET))


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()
        self.executable = self.project / "codex.exe"
        self.executable.write_bytes(b"fictional executable; never launched")
        self.home = self.project / "home"
        self.home.mkdir()
        self.environment = patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.calls = []
        self.client = SimpleNamespace(alive=True, command=(str(self.executable),), project=self.project,
                                      initialization={"codexHome": str(self.home)})

        def listing(params):
            self.calls.append(params)
            return project_response(native(self.project, cursor="native-next"), str(self.project))["result"]

        self.client.discover_threads = listing
        self.controller = SimpleNamespace(project=self.project, command=[str(self.executable)], _closed=False,
            _stop=threading.Event(), _mutex=threading.RLock(), enrolled_clients={}, _stores={},
            provider=self.client, generation="generation-1", client=dict(version=VERSION, executable_sha256=EXECUTABLE_SHA256))

    def test_allowlist_and_database_only_filters_and_registration(self):
        self.controller._stores["registered"] = SimpleNamespace(metadata=lambda: dict(provider="codex", native_id=NATIVE))
        result = discover(self.controller)
        self.assertTrue(result["available"])
        row = result["conversations"][0]
        self.assertEqual(set(row), {"id", "name", "project", "source", "created_at", "updated_at", "registered"})
        self.assertTrue(row["registered"])
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(self.calls, [dict(cwd=str(self.project), useStateDbOnly=True, archived=False, limit=20,
            sortKey="updated_at", sortDirection="desc", modelProviders=[], sourceKinds=["cli", "vscode", "exec", "appServer"])])

    def test_missing_and_duplicate_names_are_retained_without_preview_titles(self):
        message = native(self.project)
        message["result"]["data"][0]["name"] = None
        message["result"]["data"].append(dict(message["result"]["data"][0], id="11234567-89ab-4cde-8fab-0123456789ab"))
        rows = project_response(message, self.project)["result"]["conversations"]
        self.assertEqual([row["name"] for row in rows], [None, None])

    def test_cursor_is_local_and_bound_to_limit_generation(self):
        first = discover(self.controller)
        token = first["next_cursor"]
        self.assertNotEqual(token, "native-next")
        self.assertEqual(discover(self.controller, cursor=token, limit=21)["reason"], INVALID_CURSOR)
        second = discover(self.controller, cursor=token)
        self.assertFalse(second["available"])  # Native repeated cursor cannot advance forever.
        self.assertEqual(self.calls[-1]["cursor"], "native-next")
        self.controller.generation = "generation-2"
        self.assertEqual(discover(self.controller, cursor=token)["reason"], INVALID_CURSOR)
        discover(self.controller)
        self.assertEqual(discover(self.controller, cursor=token)["reason"], INVALID_CURSOR)

    def test_forward_page_preserves_scope_and_native_cursor_without_retaining_rows(self):
        first = discover(self.controller, limit=1)
        self.client.discover_threads = lambda params: project_response(native(self.project), self.project)["result"]
        second = discover(self.controller, cursor=first["next_cursor"], limit=1)
        self.assertTrue(second["available"])
        self.assertIsNone(second["next_cursor"])
        self.assertNotIn("Fictional review", repr(self.controller._discovery_pages))

    def test_independent_readers_and_refresh_keep_existing_page_tokens(self):
        barrier = threading.Barrier(2)
        results = []

        def listing(params):
            barrier.wait(timeout=2)
            return project_response(native(self.project, cursor="native-next"), self.project)["result"]

        self.client.discover_threads = listing
        readers = [threading.Thread(target=lambda: results.append(discover(self.controller))) for _ in range(2)]
        for reader in readers:
            reader.start()
        for reader in readers:
            reader.join(timeout=3)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["available"] for result in results))
        self.client.discover_threads = lambda params: project_response(native(self.project), self.project)["result"]
        self.assertTrue(discover(self.controller)["available"])  # A refresh starts an independent sequence.
        for result in results:
            self.assertTrue(discover(self.controller, cursor=result["next_cursor"])["available"])

    def test_page_tokens_expire_with_fixed_refresh_reason(self):
        with patch("awkit.session_discovery.time.monotonic", return_value=100):
            first = discover(self.controller)
        with patch("awkit.session_discovery.time.monotonic", return_value=401):
            self.assertEqual(discover(self.controller, cursor=first["next_cursor"])["reason"], INVALID_CURSOR)

    def test_cursor_and_inflight_result_are_bound_to_canonical_home(self):
        first = discover(self.controller)
        other = self.project / "other-home"
        other.mkdir()
        self.client.initialization["codexHome"] = str(other)
        with patch.dict(os.environ, {"CODEX_HOME": str(other)}):
            self.assertEqual(discover(self.controller, cursor=first["next_cursor"])["reason"], INVALID_CURSOR)

        self.client.initialization["codexHome"] = str(self.home)

        def listing(params):
            self.client.initialization["codexHome"] = str(other)
            os.environ["CODEX_HOME"] = str(other)
            return project_response(native(self.project), self.project)["result"]

        self.client.discover_threads = listing
        self.assertEqual(discover(self.controller)["reason"], INVALID_CURSOR)

    def test_projection_rejects_a_native_page_larger_than_requested(self):
        message = native(self.project)
        message["result"]["data"].append(dict(message["result"]["data"][0]))
        self.assertIn("error", project_response(message, self.project, limit=1))

    def test_no_client_or_incomplete_evidence_never_launches(self):
        for mutate in (lambda: setattr(self.controller, "provider", None),
                       lambda: self.controller.client.update(version="unsupported"),
                       lambda: self.client.initialization.update(codexHome=str(self.project))):
            with self.subTest(mutate=mutate):
                self.controller.provider = self.client
                self.controller.client["version"] = VERSION
                self.client.initialization["codexHome"] = str(self.home)
                mutate()
                self.assertFalse(discover(self.controller)["available"])
        self.assertEqual(self.calls, [])

    def test_enrolled_client_requires_matching_generation_and_runtime_home(self):
        self.controller.provider = None
        self.client.generation = "enrolled-generation"
        meta = dict(provider="codex", generation=self.client.generation, project=str(self.project),
                    enrollment=dict(runtime=dict(version=VERSION, executable_sha256=EXECUTABLE_SHA256,
                                                 executable=str(self.executable), codex_home=str(self.home))))
        self.controller._stores["enrolled"] = SimpleNamespace(metadata=lambda: meta)
        self.controller.enrolled_clients["enrolled"] = self.client
        self.assertTrue(discover(self.controller)["available"])
        meta["generation"] = "old-generation"
        self.assertFalse(discover(self.controller)["available"])

    def test_wait_releases_controller_lock_and_discards_replaced_client(self):
        def listing(params):
            acquired = []

            def replace():
                with self.controller._mutex:
                    acquired.append(True)
                    self.controller.provider = None

            thread = threading.Thread(target=replace)
            thread.start()
            thread.join(timeout=2)
            self.assertEqual(acquired, [True])
            return project_response(native(self.project), self.project)["result"]

        self.client.discover_threads = listing
        self.assertEqual(discover(self.controller)["reason"], INVALID_CURSOR)

    def test_errors_do_not_include_native_details_or_retry(self):
        def listing(params):
            self.calls.append(params)
            raise ProviderRejected(SECRET, {"code": -32601, "data": SECRET})

        self.client.discover_threads = listing
        result = discover(self.controller)
        self.assertEqual(result["reason"], UNSUPPORTED)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(len(self.calls), 1)

    def test_projection_fails_closed_on_wrong_project_source_or_types(self):
        for field, value in (("cwd", str(self.home)), ("source", "subAgent"), ("id", "invalid"),
                             ("name", {"text": SECRET}), ("createdAt", True)):
            message = native(self.project)
            message["result"]["data"][0][field] = value
            projected = project_response(message, self.project)
            self.assertIn("error", projected)
            self.assertNotIn(SECRET, json.dumps(projected))

    def test_limits_and_cursor_shape_are_validated_without_rpc(self):
        for value in (True, 0, 51, "20", None):
            with self.assertRaises(ValueError):
                discover(self.controller, limit=value)
        for value in (False, "", "x" * 201):
            with self.assertRaises(ValueError):
                discover(self.controller, cursor=value)
        self.assertEqual(self.calls, [])


class DiscoveryTransportTests(unittest.TestCase):
    def transport(self, frames):
        client = CodexSession.__new__(CodexSession)
        client._lock = threading.RLock()
        client._serial = 0
        client._pending = {}
        client._discovery = {}
        client._events = queue.Queue()
        client._closed = True  # Fixture EOF is deliberate, not a live connection failure.
        client.failure = None
        client.timeout = 0.01
        client.process = SimpleNamespace(stdout=io.BytesIO(b"".join(
            (json.dumps(frame) + "\n").encode() for frame in frames)))
        return client

    def test_success_is_projected_before_pending_queue_and_late_reply_is_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            response = native(directory)
            response["id"] = "awkit-discovery-1"
            client = self.transport([response, dict(response, id="awkit-discovery-2"),
                                     dict(id="awkit-ordinary", error={"data": SECRET})])
            pending = queue.Queue()
            client._pending[response["id"]] = pending
            client._discovery[response["id"]] = (directory, 20)
            client._read()
            self.assertNotIn(SECRET, json.dumps(pending.get_nowait()))
            event = client._events.get_nowait()
            self.assertEqual(event["method"], "awkit/lateResponse")
            self.assertIn(SECRET, json.dumps(event))  # Ordinary diagnostics retain their contract.
            self.assertTrue(client._events.empty())

    def test_native_error_is_sanitized_before_pending_queue(self):
        client = self.transport([dict(id="awkit-discovery-1", error=dict(code=-32601, message=SECRET, data=SECRET)),
                                 dict(id="awkit-discovery-late", method="unexpected", params=dict(body=SECRET))])
        pending = queue.Queue()
        client._pending["awkit-discovery-1"] = pending
        client._discovery["awkit-discovery-1"] = (".", 20)
        client._read()
        self.assertEqual(pending.get_nowait(), dict(error=dict(code=-32601)))
        self.assertTrue(client._events.empty())

    def test_discovery_error_and_timeout_are_fixed_ordinary_error_is_unchanged(self):
        client = self.transport([])

        def write(message):
            client._pending[message["id"]].put(dict(error={"code": -1, "message": SECRET}))

        client._write = write
        with self.assertRaises(ProviderError) as discovery:
            client.discover_threads({"cwd": "."})
        self.assertNotIn(SECRET, str(discovery.exception))
        with self.assertRaises(ProviderRejected) as ordinary:
            client.call("thread/read", {})
        self.assertIn(SECRET, str(ordinary.exception))
        client._write = lambda message: None
        with self.assertRaises(ProviderError) as timeout:
            client.discover_threads({"cwd": "."})
        self.assertEqual(str(timeout.exception), "Conversation discovery is unavailable.")
        self.assertEqual(client._discovery, {})


if __name__ == "__main__":
    unittest.main()
