"""Public decision transport with invented callbacks; no real provider approval."""

import asyncio
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import test_claude_session
from awkit.claude_session import ClaudeSession
from awkit.cli import main
from awkit.codex_session import ProviderError
from awkit.session_http import SessionServer
from awkit.sessions import SessionController


def cli(project, arguments, stdin=b""):
    output, error = io.StringIO(), io.StringIO()
    stream = io.TextIOWrapper(io.BytesIO(stdin), encoding="ascii") if isinstance(stdin, bytes) else io.StringIO(stdin)
    with stream, patch("sys.stdin", stream), redirect_stdout(output), redirect_stderr(error):
        try:
            code = main(["session", "--project", str(project), "decide", *arguments])
        except SystemExit as exc:
            code = exc.code
    return code, output.getvalue(), error.getvalue()


class InputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.path = self.project / "decision.json"
        self.ident = 'connection-a:"sdk-callback-invented":digest'

    def test_file_and_raw_stdin_preserve_opaque_id_unicode_and_target(self):
        payload = dict(decision_id=self.ident, choice={"answers": {"어느 선착장?": ["북쪽", "서쪽"]}})
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        for bom in (b"", b"\xef\xbb\xbf"):
            for source in ("file", "stdin"):
                with self.subTest(bom=bool(bom), source=source), patch("awkit.session_http.request", return_value={"state": "sent"}) as request:
                    self.path.write_bytes(bom + encoded)
                    route = str(self.path) if source == "file" else "-"
                    code, output, error = cli(self.project, ["Research", "--input-file", route], bom + encoded)
                    self.assertEqual((code, error), (0, ""))
                    self.assertEqual(json.loads(output), dict(schema=1, state="sent"))
                    request.assert_called_once_with(self.project, "decide", dict(ident="Research", **payload))

    def test_text_stdin_and_old_arguments_remain_compatible(self):
        payload = dict(decision_id=self.ident, choice="deny")
        routes = [(["--input-file", "-"], "\ufeff" + json.dumps(payload)),
                  (["--decision", self.ident, "--choice", "deny"], b"")]
        self.path.write_text(json.dumps({"어느 선착장?": "북쪽"}), encoding="utf-8")
        routes.append((["--decision", self.ident, "--answers-file", str(self.path)], b""))
        for arguments, stdin in routes:
            with self.subTest(arguments=arguments), patch("awkit.session_http.request", return_value={"state": "sent"}) as request:
                code, _, error = cli(self.project, ["Research", *arguments], stdin)
                self.assertEqual((code, error), (0, ""))
                self.assertEqual(request.call_args.args[2]["decision_id"], self.ident)
                self.assertEqual(request.call_args.args[2]["ident"], "Research")
        self.assertEqual(request.call_args.args[2]["choice"], {"answers": {"어느 선착장?": "북쪽"}})

    def test_malformed_ambiguous_and_mixed_input_never_calls_controller(self):
        invalid = [b"", b"{", b"[]", b"null", b'"text"', b"\xff", b"\xff\xfe{\x00}\x00",
                   b'{"decision_id":"x"}', b'{"decision_id":"","choice":"deny"}',
                   b'{"decision_id":7,"choice":"deny"}', b'{"decision_id":"x","choice":true}',
                   b'{"decision_id":"x","choice":"invented"}',
                   b'{"decision_id":"x","choice":"deny","ident":"Other"}',
                   b'{"decision_id":"x","decision_id":"y","choice":"deny"}',
                   b'{"decision_id":"x","choice":{"answers":{"q":"a","q":"b"}}}',
                   b'{"decision_id":"x","choice":{"answers":{"q":3}}}',
                   b'{"decision_id":"x","choice":{"answers":{},"allow":true}}',
                   b'{"decision_id":"x","choice":NaN}',
                   b'{"decision_id":"x","choice":Infinity}', b"[" * 2000 + b"]" * 2000]
        for body in invalid:
            with self.subTest(body=body), patch("awkit.session_http.request") as request:
                self.path.write_bytes(body)
                code, output, _ = cli(self.project, ["Research", "--input-file", str(self.path)])
                self.assertEqual((code, output), (2, ""))
                request.assert_not_called()
        for extra in (["--decision", self.ident], ["--choice", "deny"], ["--answers-file", "missing.json"]):
            with self.subTest(extra=extra), patch("awkit.session_http.request") as request:
                code, output, _ = cli(self.project, ["Research", "--input-file", "missing.json", *extra])
                self.assertEqual((code, output), (2, ""))
                request.assert_not_called()
        for arguments in (["--decision", self.ident], ["--choice", "deny"], []):
            with self.subTest(arguments=arguments), patch("awkit.session_http.request") as request:
                self.assertEqual(cli(self.project, ["Research", *arguments])[0], 2)
                request.assert_not_called()


class DecisionRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.command = [sys.executable, str(Path(__file__).with_name("session_provider_fixture.py"))]
        self.controller = SessionController(self.project, self.command)
        self.addCleanup(self.controller.close)
        self.controller.create(name="Research", responsibility="Invented pending decision")
        self.controller.send("Research", key="approval", body="ASK_QUOTED_APPROVAL")
        self.decision = self.wait(lambda v: bool(v["decisions"]))["decisions"][0]
        self.assertIn('"sdk-callback-fixture"', self.decision["id"])
        self.server = SessionServer(self.controller)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        endpoint = dict(schema=1, project=str(self.project), url=self.server.url, token=self.server.token)
        (self.controller.directory / "controller.json").write_text(json.dumps(endpoint), encoding="utf-8")
        self.path = self.project / "decision.json"
        self.write("decline")

    def wait(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            view = self.controller.status()["sessions"][0]
            if predicate(view):
                return view
            time.sleep(.025)
        self.fail(str(view))

    def write(self, choice):
        self.path.write_text(json.dumps(dict(decision_id=self.decision["id"], choice=choice)), encoding="utf-8-sig")

    def test_wrong_target_or_unoffered_choice_refuses_then_exact_reply_is_once_only(self):
        self.controller.create(name="Other", responsibility="Unrelated invented target")
        self.assertEqual(cli(self.project, ["Other", "--input-file", str(self.path)])[0], 2)
        self.write("allow")  # Valid CLI value, not an offered Codex response.
        self.assertEqual(cli(self.project, ["Research", "--input-file", str(self.path)])[0], 2)
        self.assertEqual(self.controller._store("Research").snapshot()["decisions"][0]["state"], "pending")
        self.write("decline")
        code, output, error = cli(self.project, ["Research", "--input-file", str(self.path)])
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), dict(schema=1, state="sent", decision=self.decision["id"]))
        self.wait(lambda v: len(v["messages"]) == 2)
        self.assertEqual(cli(self.project, ["Research", "--input-file", str(self.path)])[0], 2)

    def test_expired_generation_stays_unavailable_without_rebinding(self):
        self.controller.close()
        self.controller = SessionController(self.project, self.command)
        self.server.controller = self.controller
        self.addCleanup(self.controller.close)
        self.wait(lambda v: v["can_send"])
        self.assertEqual(cli(self.project, ["Research", "--input-file", str(self.path)])[0], 2)
        view = self.controller._store("Research").snapshot()
        self.assertEqual(len(view["messages"]), 1)
        self.assertEqual(len(view["attempts"]), 1)
        self.assertNotEqual(view["session"]["generation"], self.decision["generation"])

    def test_uncertain_response_is_retained_without_second_native_send(self):
        with patch.object(self.controller.provider, "respond", side_effect=ProviderError("injected uncertain write")) as respond:
            for _ in range(2):
                self.assertEqual(cli(self.project, ["Research", "--input-file", str(self.path)])[0], 2)
            self.assertEqual(respond.call_count, 1)
        self.assertEqual(self.controller._store("Research").snapshot()["decisions"][0]["state"], "uncertain")

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows PowerShell5.1")
    def test_ordinary_powershell_preserves_file_id_after_legacy_argv_loses_quotes(self):
        script = self.project / "submit.ps1"
        script.write_text("""$ErrorActionPreference='Continue'
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) { exit 91 }
$decision = Get-Content -LiteralPath $env:AWKIT_TEST_INPUT -Raw | ConvertFrom-Json
& $env:AWKIT_TEST_PYTHON -m awkit session --project $env:AWKIT_TEST_PROJECT decide Research --decision $decision.decision_id --choice decline
if ($LASTEXITCODE -ne 2) { exit 92 }
$decision | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $env:AWKIT_TEST_OUTPUT -Encoding UTF8
& $env:AWKIT_TEST_PYTHON -m awkit session --project $env:AWKIT_TEST_PROJECT decide Research --input-file $env:AWKIT_TEST_OUTPUT
exit $LASTEXITCODE
""", encoding="ascii")
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"), PYTHONUTF8="1",
                   AWKIT_TEST_PYTHON=sys.executable, AWKIT_TEST_PROJECT=str(self.project), AWKIT_TEST_INPUT=str(self.path),
                   AWKIT_TEST_OUTPUT=str(self.project / "powershell-decision.json"))
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script)],
                                env=env, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"choice is unavailable", result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], self.decision["id"])
        self.assertTrue((self.project / "powershell-decision.json").read_bytes().startswith(b"\xef\xbb\xbf"))
        self.wait(lambda v: len(v["messages"]) == 2)


class QuestionRouteTests(unittest.TestCase):
    setUp = test_claude_session.ClaudeLifetimeTests.setUp
    wait_for_decision = test_claude_session.ClaudeLifetimeTests.wait_for_decision

    def test_unicode_answers_reach_original_callback_through_file_and_stdin(self):
        controller = SessionController(self.project, [sys.executable, "unused-fixture"])
        self.addCleanup(controller.close)
        client = ClaudeSession(self.store)
        controller._stores[self.store.metadata()["id"]] = self.store
        controller.claude_clients[self.store.metadata()["id"]] = client
        server = SessionServer(controller)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        (controller.directory / "controller.json").write_text(json.dumps(dict(schema=1, project=str(self.project), url=server.url, token=server.token)), encoding="utf-8")
        questions = {"questions": [{"question": "어느 선착장으로 갈까요?", "header": "선착장", "options": []}]}
        answers = {"어느 선착장으로 갈까요?": ["북쪽", "서쪽"]}
        for source in ("file", "stdin"):
            context = types.SimpleNamespace(tool_use_id="invented-question-" + source)
            callback = asyncio.run_coroutine_threadsafe(client._permission("AskUserQuestion", questions, context), client._loop)
            decision = self.wait_for_decision()
            payload = dict(decision_id=decision["id"], choice=dict(answers=answers))
            raw = b"\xef\xbb\xbf" + json.dumps(payload, ensure_ascii=False).encode("utf-8")
            path = self.project / "unicode-decision.json"
            path.write_bytes(raw)
            code, _, error = cli(self.project, ["Worker", "--input-file", str(path) if source == "file" else "-"], raw)
            self.assertEqual((code, error), (0, ""))
            response = callback.result(timeout=3)
            self.assertEqual(response["updated_input"]["questions"], questions["questions"])
            self.assertEqual(response["updated_input"]["answers"], answers)
            self.assertNotIn("updated_permissions", response)
