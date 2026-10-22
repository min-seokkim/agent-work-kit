import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit.usage import collect


def write_jsonl(path, records, tail=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n" + tail, encoding="utf-8")


def claude_turn(message_id, model="claude-sonnet", usage=None, **extra):
    usage = usage or {"input_tokens": 3, "cache_creation_input_tokens": 100,
                      "cache_read_input_tokens": 1000, "output_tokens": 20}
    return {"type": "assistant", "effort": "medium", **extra,
            "message": {"id": message_id, "model": model, "usage": usage, "content": []}}


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_claude_counts_each_response_once_and_splits_subagents(self):
        session = self.root / "claude" / "session.jsonl"
        write_jsonl(session, [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            claude_turn("m1"), claude_turn("m1"),  # one response written as two content blocks
            claude_turn("m2", model="claude-opus"),
            claude_turn("s1", model="claude-haiku", isSidechain=True, agentId="a7"),
            {"type": "assistant", "message": {"id": "x", "model": "<synthetic>", "usage": {"input_tokens": 9}}},
        ], tail='{"type": "assistant", "mess')  # log still being written
        sub = self.root / "claude" / "session" / "subagents" / "agent-b2.jsonl"
        write_jsonl(sub, [claude_turn("s2", model="claude-haiku", isSidechain=True, agentId="b2")])
        result = collect([self.root / "claude"])
        threads = {row["thread"]: row for row in result["threads"]}
        self.assertEqual(threads["main"]["calls"], 2)
        self.assertEqual(threads["main"]["models"], {"claude-sonnet": 1, "claude-opus": 1})
        self.assertEqual(threads["main"]["fresh_input"], 6)
        self.assertEqual(threads["main"]["cache_read"], 2000)
        self.assertEqual(threads["subagent a7"]["models"], {"claude-haiku": 1})
        self.assertEqual(threads["subagent b2"]["calls"], 1)
        self.assertEqual(result["total"]["output"], 80)
        self.assertEqual(result["models"]["claude-haiku"], {"threads": 2, "calls": 2})

    def test_codex_uses_last_cumulative_total_and_turn_context(self):
        rollout = self.root / "codex" / "rollout-1.jsonl"
        write_jsonl(rollout, [
            {"type": "session_meta", "payload": {"id": "t1"}},
            {"type": "turn_context", "payload": {"model": "gpt-luna", "effort": "medium"}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": 500, "cached_input_tokens": 300, "output_tokens": 10}}}},
            {"type": "turn_context", "payload": {"model": "gpt-luna", "effort": "medium"}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {
                "input_tokens": 1200, "cached_input_tokens": 900, "cache_write_input_tokens": 0,
                "output_tokens": 40}}}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": None}},
        ])
        older = self.root / "codex" / "rollout-2.jsonl"
        write_jsonl(older, [
            {"type": "turn_context", "payload": {"model": "gpt-sol", "reasoning_effort": "high"}},
            {"type": "token_count", "payload": {"info": {"total_token_usage": {
                "input_tokens": 50, "cached_input_tokens": 0, "output_tokens": 5}}}},
        ])
        result = collect([self.root / "codex"])
        first, second = result["threads"]
        self.assertEqual((first["models"], first["effort"], first["calls"]), ({"gpt-luna": 2}, "medium", 2))
        self.assertEqual((first["fresh_input"], first["cache_read"], first["output"]), (300, 900, 40))
        self.assertEqual((second["models"], second["effort"], second["fresh_input"]), ({"gpt-sol": 1}, "high", 50))

    def test_user_messages_and_wall_time_are_counted_per_thread(self):
        session = self.root / "claude" / "session.jsonl"
        write_jsonl(session, [
            {"type": "user", "timestamp": "2026-10-22T09:00:00.000Z",
             "message": {"role": "user", "content": "please fix the link"}},
            {**claude_turn("m1"), "timestamp": "2026-10-22T09:00:05.000Z"},
            {"type": "user", "timestamp": "2026-10-22T09:00:06.000Z",  # a tool result, not a person
             "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}},
            {**claude_turn("m2"), "timestamp": "2026-10-22T09:01:00.000Z"},
            {"type": "user", "timestamp": "2026-10-22T09:02:30.000Z",
             "message": {"role": "user", "content": [{"type": "text", "text": "no, the other one"}]}},
            {"type": "user", "isSidechain": True, "agentId": "a1",
             "message": {"role": "user", "content": "handoff prompt to a subagent"}},
            {**claude_turn("s1", isSidechain=True, agentId="a1"), "timestamp": "2026-10-22T09:03:00.000Z"},
        ])
        result = collect([session])
        threads = {row["thread"]: row for row in result["threads"]}
        self.assertEqual(threads["main"]["user_messages"], 2)
        self.assertEqual(threads["main"]["minutes"], 2.5)
        self.assertEqual(threads["main"]["started_at"], "2026-10-22T09:00:00+00:00")
        self.assertEqual(threads["subagent a1"]["user_messages"], 0)
        self.assertEqual(threads["subagent a1"]["minutes"], 0.0)
        self.assertEqual(result["total"]["user_messages"], 2)
        rollout = self.root / "codex" / "rollout.jsonl"
        write_jsonl(rollout, [
            {"type": "event_msg", "timestamp": "2026-10-22T10:00:00Z", "payload": {"type": "user_message", "message": "go"}},
            {"type": "turn_context", "timestamp": "2026-10-22T10:00:01Z", "payload": {"model": "gpt-luna"}},
            {"type": "event_msg", "timestamp": "2026-10-22T10:12:00Z", "payload": {"type": "user_message", "message": "again"}},
        ])
        (thread,) = collect([rollout])["threads"]
        self.assertEqual((thread["user_messages"], thread["minutes"]), (2, 12.0))

    def test_missing_and_invalid_token_fields_are_not_reported_as_zero(self):
        session = self.root / "claude" / "session.jsonl"
        write_jsonl(session, [
            claude_turn("m1", usage={"input_tokens": 5, "output_tokens": 7}),  # no cache fields
            claude_turn("m2", usage={"input_tokens": 5, "cache_creation_input_tokens": 1,
                                     "cache_read_input_tokens": 2, "output_tokens": "many"}),
            {"type": "assistant", "message": {"id": "m3", "model": "claude-sonnet"}},  # no usage at all
        ])
        result = collect([session])
        (thread,) = result["threads"]
        self.assertEqual(thread["calls"], 3)
        self.assertEqual(thread["counted"], "responses")
        self.assertIsNone(thread["fresh_input"])  # m3 carried no usage at all
        self.assertIsNone(thread["cache_write"])
        self.assertIsNone(thread["cache_read"])
        self.assertIsNone(thread["output"])
        self.assertEqual(thread["missing"], {"fresh_input": 1, "cache_write": 2, "cache_read": 2, "output": 1})
        self.assertEqual(thread["invalid"], {"output": 1})
        self.assertEqual(result["total"]["complete"], False)
        self.assertEqual(result["total"]["incomplete_threads"], 1)
        self.assertEqual(result["format"], 2)

    def test_codex_without_token_counts_reports_unmeasured_tokens(self):
        rollout = self.root / "codex" / "rollout.jsonl"
        write_jsonl(rollout, [{"type": "turn_context", "payload": {"model": "gpt-luna"}}])
        (thread,) = collect([rollout])["threads"]
        self.assertEqual((thread["models"], thread["calls"], thread["counted"]), ({"gpt-luna": 1}, 1, "turns"))
        self.assertEqual([thread[f] for f in ("fresh_input", "cache_write", "cache_read", "output")], [None] * 4)
        partial = self.root / "codex" / "partial.jsonl"
        write_jsonl(partial, [
            {"type": "turn_context", "payload": {"model": "gpt-luna"}},
            {"type": "token_count", "payload": {"info": {"total_token_usage": {"input_tokens": 40, "output_tokens": 3}}}},
        ])
        (thread,) = collect([partial])["threads"]
        self.assertEqual((thread["output"], thread["fresh_input"], thread["cache_read"]), (3, None, None))
        self.assertEqual(thread["missing"], {"fresh_input": 1, "cache_read": 1, "cache_write": 1})

    def test_damaged_and_partial_lines_are_counted_separately(self):
        session = self.root / "session.jsonl"
        write_jsonl(session, [claude_turn("m1")], tail="{broken json}\n" + '{"type": "assistant", "mess')
        result = collect([session])
        self.assertEqual(result["skipped_lines"], {str(session): {"damaged_lines": 1, "partial_line": True}})
        self.assertEqual(result["threads"][0]["calls"], 1)
        self.assertFalse(result["total"]["complete"])
        clean = self.root / "clean.jsonl"
        write_jsonl(clean, [claude_turn("m1")])
        self.assertTrue(collect([clean])["total"]["complete"])

    def test_unknown_files_are_reported_and_missing_paths_fail(self):
        write_jsonl(self.root / "other.jsonl", [{"hello": "world"}])
        self.assertEqual(len(collect([self.root])["unrecognized_files"]), 1)
        with self.assertRaises(ValueError):
            collect([self.root / "missing.jsonl"])

    def test_cli_json_and_table(self):
        write_jsonl(self.root / "s.jsonl", [claude_turn("m1")])
        command = [sys.executable, "-m", "awkit", "usage", str(self.root)]
        env = {**os.environ, "PYTHONUTF8": "1"}
        table = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(table.returncode, 0, table.stderr)
        self.assertIn("claude-sonnet", table.stdout)
        self.assertIn("total", table.stdout)
        self.assertNotIn("?", table.stdout)
        data = json.loads(subprocess.run(command + ["--json"], capture_output=True, text=True,
                                         encoding="utf-8", env=env).stdout)
        self.assertEqual(data["total"]["cache_write"], 100)
        future = subprocess.run(command + ["--since", "2999-01-01", "--json"], capture_output=True,
                                text=True, encoding="utf-8", env=env)
        self.assertEqual(json.loads(future.stdout)["threads"], [])
        write_jsonl(self.root / "gap.jsonl", [claude_turn("m2", usage={"input_tokens": 1})])
        table = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertIn("?", table.stdout)
        self.assertIn("known", table.stdout)
        self.assertIn("unmeasured", table.stdout)


if __name__ == "__main__":
    unittest.main()
