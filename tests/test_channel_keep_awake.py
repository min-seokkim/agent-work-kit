import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, call, patch

from awkit import cli
from awkit.channel import Channel
from awkit.keep_awake import ES_CONTINUOUS, ES_SYSTEM_REQUIRED, keep_awake


class KeepAwakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "channel.sqlite3"
        self.channel = Channel(self.path, project=Path(temporary.name))

    def invoke(self, *args, enabled=True):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["channel", "--db", str(self.path), "wait", *args, "--max", "0", "--json"]
        if enabled:
            argv.append("--keep-awake")
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_found_message_json_and_cursor_are_preserved(self):
        self.channel.post("reviewer", "main", "notice", "ready")
        request = Mock(side_effect=[ES_CONTINUOUS, ES_CONTINUOUS | ES_SYSTEM_REQUIRED])
        with patch("awkit.keep_awake.sys.platform", "win32"), \
                patch("awkit.keep_awake._execution_state", return_value=request):
            code, stdout, stderr = self.invoke("main", "new")
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout), self.channel.export())
        self.assertEqual(self.channel.find("main", "new"), (1, []))
        self.assertEqual(request.call_args_list,
                         [call(ES_CONTINUOUS | ES_SYSTEM_REQUIRED), call(ES_CONTINUOUS)])

    def test_timeout_and_close_release_the_request(self):
        for closed in (False, True):
            with self.subTest(closed=closed):
                if closed:
                    self.channel.post("main", "reviewer", "close", "done")
                request = Mock(return_value=ES_CONTINUOUS)
                with patch("awkit.keep_awake.sys.platform", "win32"), \
                        patch("awkit.keep_awake._execution_state", return_value=request):
                    code, stdout, stderr = self.invoke("reviewer", "request")
                self.assertEqual(code, 3 if closed else 1)
                self.assertEqual(stdout, "main closed the channel.\n" if closed else "")
                self.assertEqual(stderr, "")
                self.assertEqual(request.call_count, 2)

    def test_zero_seconds_reads_once_and_restores_prior_requirements(self):
        previous = ES_CONTINUOUS | 0x2
        request = Mock(side_effect=[previous, ES_CONTINUOUS | ES_SYSTEM_REQUIRED])
        with patch("awkit.keep_awake.sys.platform", "win32"), \
                patch("awkit.keep_awake._execution_state", return_value=request), \
                patch.object(Channel, "find", return_value=(1, [])) as find:
            self.assertEqual(self.invoke("main", "new"), (1, "", ""))
        find.assert_called_once_with("main", "new", None)
        self.assertEqual(request.call_args_list,
                         [call(ES_CONTINUOUS | ES_SYSTEM_REQUIRED), call(previous)])

    def test_default_wait_does_not_request_power_or_warn(self):
        with patch("awkit.keep_awake._execution_state") as load:
            self.assertEqual(self.invoke("main", "new", enabled=False), (1, "", ""))
        load.assert_not_called()

    def test_unsupported_platform_warns_and_delivers_normal_message(self):
        self.channel.post("reviewer", "main", "notice", "ready")
        with patch("awkit.keep_awake.sys.platform", "linux"), \
                patch("awkit.keep_awake._execution_state") as load:
            code, stdout, stderr = self.invoke("main", "new")
        load.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)[0]["body"], "ready")
        self.assertEqual(self.channel.find("main", "new"), (1, []))
        self.assertEqual(stderr.count("warning:"), 1)
        self.assertIn("only on Windows", stderr)
        self.assertIn("system may sleep", stderr)

    def test_acquisition_failure_warns_once_and_preserves_normal_wait(self):
        for failure in (0, OSError("unavailable")):
            with self.subTest(failure=failure):
                request = Mock(side_effect=[failure])
                with patch("awkit.keep_awake.sys.platform", "win32"), \
                        patch("awkit.keep_awake._execution_state", return_value=request):
                    code, stdout, stderr = self.invoke("main", "new")
                self.assertEqual((code, stdout), (1, ""))
                self.assertEqual(request.call_count, 1)
                self.assertEqual(stderr.count("warning:"), 1)
                self.assertIn("system may sleep", stderr)

    def test_missing_native_api_warns_and_runs_wait(self):
        with patch("awkit.keep_awake.sys.platform", "win32"), \
                patch("awkit.keep_awake._execution_state", side_effect=AttributeError("missing")):
            code, stdout, stderr = self.invoke("main", "new")
        self.assertEqual((code, stdout), (1, ""))
        self.assertEqual(stderr.count("warning:"), 1)
        self.assertIn("missing", stderr)

    def test_release_failure_preserves_message_and_cursor(self):
        self.channel.post("reviewer", "main", "notice", "ready")
        request = Mock(side_effect=[ES_CONTINUOUS, 0])
        with patch("awkit.keep_awake.sys.platform", "win32"), \
                patch("awkit.keep_awake._execution_state", return_value=request):
            code, stdout, stderr = self.invoke("main", "new")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), self.channel.export())
        self.assertEqual(self.channel.find("main", "new"), (1, []))
        self.assertEqual(stderr.count("warning:"), 1)
        self.assertIn("restore the previous thread state", stderr)

    def test_wait_errors_and_interrupts_release_without_replacing_exit(self):
        for failure, expected in ((OSError("wait failed"), 2), (KeyboardInterrupt(), 130)):
            for release in (ES_CONTINUOUS, 0, OSError("release failed")):
                with self.subTest(failure=type(failure).__name__, release=release):
                    request = Mock(side_effect=[ES_CONTINUOUS, release])
                    with patch("awkit.keep_awake.sys.platform", "win32"), \
                            patch("awkit.keep_awake._execution_state", return_value=request), \
                            patch.object(Channel, "wait", side_effect=failure):
                        code, stdout, stderr = self.invoke("main", "new")
                    self.assertEqual((code, stdout), (expected, ""))
                    self.assertEqual(request.call_count, 2)
                    self.assertIn("Interrupted." if expected == 130 else "wait failed", stderr)
                    self.assertEqual("warning:" in stderr, release != ES_CONTINUOUS)

    def test_original_exception_survives_failed_release_and_diagnostic(self):
        failure = RuntimeError("original wait failure")
        request = Mock(side_effect=[ES_CONTINUOUS, OSError("release failed")])
        stderr = Mock()
        stderr.write.side_effect = OSError("stream closed")
        with patch("awkit.keep_awake.sys.platform", "win32"), \
                patch("awkit.keep_awake._execution_state", return_value=request), \
                patch("awkit.keep_awake.sys.stderr", stderr):
            with self.assertRaises(RuntimeError) as caught:
                with keep_awake():
                    raise failure
        self.assertIs(caught.exception, failure)
        self.assertEqual(request.call_count, 2)
