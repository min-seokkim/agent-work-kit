"""Expected counts were tallied from source logs without awkit; see expected.json."""

import hashlib
import json
import re
import unittest
from pathlib import Path

from awkit.usage import collect

FIXTURES = Path(__file__).parent / "data/usage"


class RealLogUsageTests(unittest.TestCase):
    def test_real_provider_logs_match_independent_source_tallies(self):
        expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
        for name, fixture in expected.items():
            with self.subTest(client=name):
                path = FIXTURES / (name + ".jsonl")
                raw = path.read_bytes().replace(b"\r\n", b"\n")
                self.assertEqual(hashlib.sha256(raw).hexdigest(), fixture["fixture_sha256"])
                self.assertEqual(len(raw.splitlines()), fixture["records"])
                result = collect([path])
                (thread,) = result["threads"]
                for field, value in fixture["expected"].items():
                    self.assertEqual(thread[field], value, field)
                self.assertTrue(thread["call_coverage"]["complete"])
                self.assertTrue(thread["user_message_coverage"]["complete"])
                self.assertFalse(re.search(r"minseok|min-seokkim|raptor210|snu\.ac\.kr|김민석|민석|OneDrive|[ED]:[\\/]", raw.decode(), re.I))

    def test_fixture_identities_remain_distinct_when_read_together(self):
        expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
        result = collect([FIXTURES])
        self.assertEqual(len(result["threads"]), len(expected))
        self.assertEqual(result["total"]["calls"], sum(item["expected"]["calls"] for item in expected.values()))
        self.assertEqual(result["total"]["user_messages"], sum(item["expected"]["user_messages"] for item in expected.values()))

    def test_cli_and_app_sources_are_distinguished_by_native_metadata(self):
        for name, originator, source in (("codex-cli", "codex_exec", "exec"),
                                         ("codex-app", "codex_work_desktop", "vscode")):
            record = json.loads((FIXTURES / (name + ".jsonl")).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["payload"]["originator"], originator)
            self.assertEqual(record["payload"]["source"], source)
