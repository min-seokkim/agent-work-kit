import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit import __version__
from awkit.channel import Channel
from awkit.channel_delivery import Delivery
from awkit.channel_mcp import MAX_LINE_CHARS, Server, serve
from support import child_env


def request(method, request_id=1, **params):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def initialize():
    return request("initialize", protocolVersion="2025-11-25", capabilities={}, clientInfo={"name": "test", "version": "1"})


class ChannelMcpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "한글 channel.sqlite3"
        self.channel = Channel(self.path, project=self.path.parent)
        self.channel.export()
        self.server = Server(Delivery(self.path, "reviewer", "cloud"))
        self.server.handle(initialize())

    def call(self, name, **arguments):
        return self.server.handle(request("tools/call", name=name, arguments=arguments))

    def test_tool_binding_validation_and_notifications_do_not_dispatch(self):
        for arguments in ({"path": "/other"}, {"role": "main"}, {"consumer": "other"}, {"sql": "DROP TABLE messages"}):
            self.assertIn("error", self.call("channel_read", **arguments))
        self.assertIn("error", self.call("channel_message", message_id="M-001", offset=True))
        self.assertIn("error", self.call("unknown"))
        notification = request("tools/call", name="channel_post", arguments={"channel_id": self.server.delivery.instance, "key": "bad", "kind": "notice", "body": "must not send"})
        del notification["id"]
        self.assertIsNone(self.server.handle(notification))
        self.assertEqual(self.channel.export(), [])
        response = self.call("channel_post", channel_id=self.server.delivery.instance, key="close", kind="close", body="forbidden")
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(self.channel.export(), [])

    def test_missing_database_is_a_tool_error_without_creation(self):
        self.path.unlink()
        result = self.call("channel_read")["result"]
        self.assertTrue(result["isError"])
        self.assertIn("channel_id", json.loads(result["content"][0]["text"]))
        self.assertFalse(self.path.exists())

    def test_protocol_errors_and_unsupported_version(self):
        for invalid in ([], None, {"jsonrpc": "1.0", "id": 1, "method": "ping"}, request("ping", True)):
            self.assertEqual(self.server.handle(invalid)["error"]["code"], -32600)
        self.assertEqual(self.server.handle(request("unknown"))["error"]["code"], -32601)
        self.assertEqual(self.server.handle(request("initialize"))["error"]["code"], -32600)
        other = Server(self.server.delivery)
        self.assertEqual(other.handle(request("tools/list"))["error"]["code"], -32002)
        self.assertEqual(other.handle(request("ping"))["result"], {})
        init = initialize()
        init["params"]["protocolVersion"] = "future"
        self.assertEqual(other.handle(init)["result"]["protocolVersion"], "2025-11-25")

    def test_malformed_and_oversized_lines_recover_at_next_message(self):
        data = 'x' * (MAX_LINE_CHARS + 10) + '\n'
        data += '{"jsonrpc":"2.0","method":"ping","id":1,"id":2}\n'
        data += '{"jsonrpc":"2.0","method":"ping","id":NaN}\n'
        data += "\r\n\n"
        data += json.dumps(request("ping", 7)) + '\n'
        output = io.StringIO()
        serve(self.path, "reviewer", "reader", input_stream=io.StringIO(data), output_stream=output)
        results = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r["error"]["code"] for r in results[:3]], [-32700] * 3)
        self.assertEqual(results[-1], {"jsonrpc": "2.0", "id": 7, "result": {}})

    def test_actual_stdio_utf8_and_restart_receipt(self):
        self.channel.post("main", "reviewer", "question", "한글 요청과 응답 😀")
        command = [sys.executable, "-m", "awkit", "channel", "--db", str(self.path), "serve", "--role", "reviewer", "--consumer", "desktop"]
        notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        messages = [initialize(), notification, request("tools/list", 2), request("ping", 3),
                    request("tools/call", 4, name="channel_read", arguments={}),
                    request("tools/call", 5, name="channel_post", arguments={"channel_id": self.server.delivery.instance, "key": "unicode", "kind": "re", "body": "한국어 답변", "reply_to": "M-001"})]
        def run(messages):
            completed = subprocess.run(command, input="\n".join(json.dumps(m, ensure_ascii=False) for m in messages) + "\n",
                                       capture_output=True, text=True, encoding="utf-8", timeout=20, env=child_env())
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return [json.loads(line) for line in completed.stdout.splitlines()]
        results = run(messages)
        self.assertEqual(len(results), 5)
        self.assertEqual(len(results[1]["result"]["tools"]), 5)
        original = json.loads(results[3]["result"]["content"][0]["text"])
        self.assertEqual(original["segment"]["message"]["body"], "한글 요청과 응답 😀")
        resumed = run([initialize(), request("tools/call", 2, name="channel_read", arguments={})])
        self.assertEqual(json.loads(resumed[1]["result"]["content"][0]["text"]), original)
        self.assertEqual(self.channel.export()[1]["body"], "한국어 답변")

    def test_cli_requires_explicit_absolute_existing_database(self):
        base = [sys.executable, "-m", "awkit", "channel"]
        for db_args in ([], ["--db", "relative.sqlite3"], ["--db", str(self.path.with_name("missing.sqlite3"))]):
            completed = subprocess.run(base + db_args + ["serve", "--role", "reviewer", "--consumer", "test"],
                                       input="", capture_output=True, text=True, timeout=20, env=child_env())
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, "")
        self.assertFalse(self.path.with_name("missing.sqlite3").exists())

    def test_optional_nulls_and_package_version(self):
        init = Server(self.server.delivery).handle(initialize())
        self.assertEqual(init["result"]["serverInfo"]["version"], __version__)
        result = self.call("channel_post", channel_id=self.server.delivery.instance,
                           key="nulls", kind="notice", body="optional omitted", reply_to=None, snap=None)
        self.assertFalse(result["result"]["isError"])
        self.assertFalse(self.call("channel_requests", after_seq=None)["result"]["isError"])
        self.channel.post("main", "reviewer", "notice", "incoming")
        self.assertFalse(self.call("channel_message", message_id="M-001", offset=None)["result"]["isError"])
