"""Real loopback control and CLI, with an offline provider only."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from awkit.channel import Channel
from awkit.session_http import SessionServer, request
from awkit.sessions import SessionController


class SessionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        fixture = Path(__file__).with_name("session_provider_fixture.py")
        self.controller = SessionController(self.project, [sys.executable, str(fixture)])
        self.addCleanup(self.controller.close)
        self.server = SessionServer(self.controller)
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.endpoint_path = self.controller.directory / "controller.json"
        self.endpoint_path.write_text(json.dumps(dict(schema=1, project=str(self.project), url=self.server.url,
                                                       token=self.server.token)), encoding="utf-8")

    def call(self, action, **args):
        return request(self.project, action, args)

    def test_history_preserves_complete_bodies_relationships_bytes_and_cursors(self):
        path = self.project / "existing.sqlite3"
        channel = Channel(path)
        original = "Original complete request\nSecond paragraph with <literal markup> & a source link."
        first = channel.post("main", "reviewer", "question", original)
        reply = channel.post("reviewer", "main", "re", "Complete returned result", reply_to=first)
        channel.find("reviewer", "new")
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        registration = self.call("register", channel=str(path), main_name="Planning", reviewer_name="Implementation")
        for _ in range(2):
            view = self.call("status")["sessions"][0]
            self.assertEqual(view["session"]["id"], registration["id"])
            self.assertTrue(view["session"]["history"])
            self.assertIsNone(view["session"]["native_id"])
            self.assertFalse(view["can_send"])
            self.assertEqual(view["parties"], {"main": "Planning", "reviewer": "Implementation"})
            self.assertEqual(view["messages"][0]["body"], original)
            self.assertEqual(view["messages"][1]["reply_to"], first)
            self.assertEqual(view["messages"][1]["id"], reply)
        with self.assertRaises(ValueError):
            self.call("send", ident=registration["id"], key="bad-send", body="No mutation")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertEqual(channel.find("reviewer", "new")[0], 1)
        self.assertIsNone(self.controller.provider)

    def test_alias_registration_cannot_silently_change_party_mapping(self):
        path = self.project / "existing.sqlite3"
        Channel(path).post("main", "reviewer", "notice", "Notice")
        alias = self.project / "alias.sqlite3"
        try:
            os.link(path, alias)
        except OSError as exc:
            self.skipTest(str(exc))
        first = self.call("register", channel=str(path), main_name="A", reviewer_name="B")
        same = self.call("register", channel=str(alias), main_name="A", reviewer_name="B")
        self.assertEqual(first["id"], same["id"])
        with self.assertRaises(ValueError):
            self.call("register", channel=str(alias), main_name="B", reviewer_name="A")

    def test_mutations_require_token_same_origin_and_local_host(self):
        body = json.dumps(dict(action="create", args=dict(name="Unauthorized", responsibility="No"))).encode()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for headers in ({"Authorization": "Bearer wrong"},
                        {"Authorization": "Bearer " + self.server.token, "Origin": "https://unrelated.example"},
                        {"Authorization": "Bearer " + self.server.token, "Host": "unrelated.example"}):
            headers["Content-Type"] = "application/json"
            call = urllib.request.Request(self.server.url + "/api/command", data=body, headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as raised:
                opener.open(call, timeout=3)
            self.assertEqual(raised.exception.code, 403)
            raised.exception.close()
        self.assertEqual(self.controller.status()["sessions"], [])
        self.assertIsNone(self.controller.provider)

    def test_agent_cli_uses_the_same_owner_and_native_context(self):
        session = self.call("create", name="Research", responsibility="Invented context")["session"]
        self.call("send", ident=session["id"], key="human-first", body="The invented boat is called Willow.", entry="human")
        self.wait_for_replies(1)
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"), PYTHONUTF8="1")
        result = subprocess.run([sys.executable, "-m", "awkit", "session", "--project", str(self.project),
                                 "send", "Research", "--key", "agent-second", "--body", "recall"],
                                env=env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        stored = json.loads(result.stdout)
        self.assertEqual(stored["state"], "stored")
        view = self.wait_for_replies(2)
        self.assertEqual(view["session"]["native_id"], session["native_id"])
        self.assertIn("Willow", view["messages"][-1]["body"])
        self.assertEqual(len(view["attempts"]), 2)

    def test_endpoint_cannot_redirect_capability_to_an_external_service(self):
        self.endpoint_path.write_text(json.dumps(dict(schema=1, project=str(self.project), url="https://external.example",
                                                       token="x" * 40)), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Invalid local controller endpoint"):
            self.call("status")

    def test_static_screen_is_packaged_and_contains_no_capability_secret(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(self.server.url + "/", timeout=3) as response:
            html = response.read().decode()
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("Create an independent session", html)
        self.assertNotIn(self.server.token, html)

    def wait_for_replies(self, count):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            view = self.call("status")["sessions"][0]
            if sum(message["kind"] == "re" for message in view["messages"]) == count:
                return view
            time.sleep(0.03)
        self.fail(str(self.call("status")))

    def test_pending_declaration_and_returned_reply_remain_distinct_and_read_only(self):
        path = self.project / "declared.sqlite3"
        channel = Channel(path)
        first = channel.post("main", "reviewer", "question", "Review the invented result")
        reply = channel.post("reviewer", "main", "re", "Returned result", reply_to=first)
        registered = self.call("register", channel=str(path), main_name="Planning", reviewer_name="Implementation")
        record = self.project / "task.json"
        record.write_text(json.dumps(dict(schema=1, session="Planning", relationships=[dict(
            id="implementation", channel=str(path), local_role="main", counterpart="Implementation")],
            obligations=[dict(id="handle-result", source=dict(relationship="implementation", message=first),
                              responsible_session="Planning", action="integrate returned result", state="pending",
                              evidence=[dict(relationship="implementation", message=reply)])])), encoding="utf-8")
        self.controller.record = record
        before = {file: file.read_bytes() for file in (record, path)}
        state = self.call("status")
        self.assertEqual(state["declarations"]["report"]["obligations"][0]["state"], "pending")
        self.assertEqual(state["declarations"]["view_links"]["implementation"], registered["id"])
        self.assertEqual(state["sessions"][0]["unanswered"], [])
        self.assertEqual(state["sessions"][0]["messages"][1]["body"], "Returned result")
        self.assertEqual({file: file.read_bytes() for file in (record, path)}, before)
