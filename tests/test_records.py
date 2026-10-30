"""Replacing JSON records while another process holds the target open."""

import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (checks that the tests import awkit from src)
from awkit import records


class ReplaceRetry(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.path = self.folder / "result.json"
        self.path.write_text('{"status": "running"}\n', encoding="utf-8")

    def failing_replace(self, failures):
        calls = []
        real = os.replace
        def fake(source, target):
            calls.append(target)
            if len(calls) <= failures:
                raise PermissionError(5, "Access is denied")
            return real(source, target)
        return fake, calls

    def test_transient_permission_error_is_retried(self):
        fake, calls = self.failing_replace(2)
        with mock.patch.object(records, "REPLACE_DELAYS", (0.01, 0.02, 0.04)), \
             mock.patch.object(records.os, "replace", fake), \
             mock.patch.object(records.time, "sleep") as sleep:
            records.atomic_json(self.path, {"status": "passed"})
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"status": "passed"})
        self.assertEqual(len(calls), 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [0.01, 0.02])
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["result.json"])

    def test_persistent_error_is_raised_and_keeps_the_previous_record(self):
        fake, calls = self.failing_replace(10)
        with mock.patch.object(records, "REPLACE_DELAYS", (0.01, 0.02)), \
             mock.patch.object(records.os, "replace", fake), \
             mock.patch.object(records.time, "sleep"):
            with self.assertRaises(PermissionError):
                records.atomic_json(self.path, {"status": "passed"})
        self.assertEqual(len(calls), 3)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"status": "running"})
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["result.json"])

    def test_without_delays_an_error_is_raised_at_once(self):
        fake, calls = self.failing_replace(1)
        with mock.patch.object(records, "REPLACE_DELAYS", ()), mock.patch.object(records.os, "replace", fake):
            with self.assertRaises(PermissionError):
                records.replace(self.folder / "missing.tmp", self.path)
        self.assertEqual(len(calls), 1)

    @unittest.skipUnless(os.name == "nt", "Windows refuses to replace a file another handle holds open")
    def test_windows_open_reader_delays_but_does_not_fail_the_write(self):
        # Python opens files without delete sharing, which is how a scanner's read blocks the replacement.
        reader = self.path.open("rb")
        self.addCleanup(reader.close)
        with mock.patch.object(records, "REPLACE_DELAYS", ()):
            with self.assertRaises(PermissionError):
                records.atomic_json(self.path, {"status": "blocked"})
        release = threading.Timer(0.3, reader.close)
        release.start()
        self.addCleanup(release.cancel)
        records.atomic_json(self.path, {"status": "passed"})
        self.assertTrue(reader.closed)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"status": "passed"})


if __name__ == "__main__":
    unittest.main()
