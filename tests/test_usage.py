import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from awkit.usage import collect, render
from support import child_env


def write_jsonl(path, records, tail=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n" + tail, encoding="utf-8")


def claude_turn(message_id, model="claude-sonnet", usage=None, **extra):
    usage = usage or {"input_tokens": 3, "cache_creation_input_tokens": 100,
                      "cache_read_input_tokens": 1000, "output_tokens": 20}
    return {"type": "assistant", "effort": "medium", **extra,
            "message": {"id": message_id, "model": model, "usage": usage, "content": []}}


def codex_message(message_id="message-a", text="please check", markers=("user.text",)):
    payload = {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}],
               "internal_chat_message_metadata_passthrough": {"content_item_kinds": list(markers)}}
    if message_id is not None:
        payload["id"] = message_id
    return {"type": "response_item", "timestamp": "2026-10-22T10:00:00Z", "payload": payload}


def codex_tokens(**values):
    return {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {
        "input_tokens": 100, "cached_input_tokens": 20, "cache_write_input_tokens": 0, "output_tokens": 10,
        **values}}}}


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
            # Typed while the turn was running: Claude Code keeps it only as a queued_command attachment.
            {"type": "attachment", "timestamp": "2026-10-22T09:02:40.000Z",
             "attachment": {"type": "queued_command", "prompt": "and keep the old name", "commandMode": "prompt",
                            "origin": {"kind": "human"}, "humanTurn": True}},
            {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "from a hook",
                                                  "origin": {"kind": "hook"}}},
            {"type": "attachment", "attachment": {"type": "task_reminder", "content": "x"}},
            {"type": "user", "isSidechain": True, "agentId": "a1",
             "message": {"role": "user", "content": "handoff prompt to a subagent"}},
            # Written by Claude Code, not typed: notices, command output, interruptions, hook feedback.
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": "<system-reminder>x</system-reminder>"}},
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": "Stop hook feedback: commit"}},
            {"type": "user", "message": {"role": "user", "content": "<local-command-stdout>Set model</local-command-stdout>"}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]}},
            {"type": "user", "origin": {"kind": "hook"}, "message": {"role": "user", "content": "from a hook"}},
            {"type": "user", "isCompactSummary": True, "message": {"role": "user", "content": "summary of earlier turns"}},
            # A slash command the person ran is counted, but apart from messages.
            {"type": "user", "message": {"role": "user", "content": "<command-name>/model</command-name>"}},
            {"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": "<command-name>/review</command-name>"}},
            {**claude_turn("s1", isSidechain=True, agentId="a1"), "timestamp": "2026-10-22T09:03:00.000Z"},
        ])
        result = collect([session])
        threads = {row["thread"]: row for row in result["threads"]}
        self.assertEqual((threads["main"]["user_messages"], threads["main"]["commands"]), (3, 2))
        self.assertEqual(threads["main"]["minutes"], 2.7)  # the queued message at 09:02:40 is activity too
        self.assertEqual(threads["main"]["started_at"], "2026-10-22T09:00:00+00:00")
        self.assertEqual(threads["subagent a1"]["user_messages"], 0)
        self.assertEqual(threads["subagent a1"]["minutes"], 0.0)
        self.assertEqual((result["total"]["user_messages"], result["total"]["commands"]), (3, 2))
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
        self.assertEqual(result["format"], 3)

    def test_codex_without_token_counts_reports_unmeasured_tokens(self):
        rollout = self.root / "codex" / "rollout.jsonl"
        write_jsonl(rollout, [{"type": "turn_context", "payload": {"model": "gpt-luna"}}])
        (thread,) = collect([rollout])["threads"]
        self.assertEqual((thread["models"], thread["calls"], thread["counted"]), ({"gpt-luna": 1}, 1, "model_context_rows"))
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

    def test_modern_messages_have_exact_ids_and_separate_token_coverage(self):
        path = self.root / "modern.jsonl"
        write_jsonl(path, [codex_message(), codex_tokens()])
        result = collect([path])
        (thread,) = result["threads"]
        self.assertEqual(result["format"], 3)
        self.assertEqual(thread["user_messages"], 1)
        self.assertEqual(thread["user_message_coverage"], {
            "complete": True, "observations": {"legacy": 0, "modern": 1}, "unclassified": 0, "reasons": []})
        self.assertEqual(result["total"]["user_messages"], 1)
        self.assertTrue(result["total"]["complete"])
        self.assertEqual((thread["fresh_input"], thread["cache_read"], thread["cache_write"], thread["output"]),
                         (80, 20, 0, 10))

    def test_original_modern_shape_without_id_keeps_the_human_observation(self):
        path = self.root / "modern.jsonl"
        write_jsonl(path, [codex_message(None), codex_tokens()])
        result = collect([path])
        (thread,) = result["threads"]
        self.assertIsNone(thread["user_messages"])
        self.assertEqual(thread["user_message_coverage"]["observations"]["modern"], 1)
        self.assertEqual(thread["user_message_coverage"]["reasons"], ["missing_message_id"])
        self.assertTrue(result["total"]["complete"])  # tokens remain fully measured
        self.assertFalse(result["total"]["user_message_coverage"]["complete"])
        self.assertIsNone(result["total"]["user_messages"])
        table = render(result)
        self.assertIn("modern=1", table)
        self.assertIn("missing_message_id", table)
        self.assertIn("token/log coverage: complete; human-input coverage: incomplete", table)
        self.assertIn("?", table)

    def test_messages_survive_without_model_or_tokens(self):
        legacy = {"type": "event_msg", "payload": {"type": "user_message", "message": "go"}}
        for name, record, expected in (("modern", codex_message(), 1), ("legacy", legacy, 1),
                                        ("unknown", codex_message(markers=("future.wrapper",)), None)):
            with self.subTest(name=name):
                path = self.root / f"{name}.jsonl"
                write_jsonl(path, [record])
                result = collect([path])
                (thread,) = result["threads"]
                self.assertEqual(thread["user_messages"], expected)
                self.assertEqual(thread["calls"], 0)
                self.assertEqual(thread["models"], {})
                self.assertEqual([thread[field] for field in ("fresh_input", "cache_read", "cache_write", "output")],
                                 [None] * 4)
                self.assertFalse(result["total"]["complete"])

    def test_known_scaffolds_are_excluded_and_uncertain_origins_are_visible(self):
        cases = [
            (("agents_md.instructions",), 0, None),
            (("agents_md.instructions", "environments.environment_context"), 0, None),
            (("additional_content.codex_apps_open_page",), 0, None),
            (("hook.feedback",), None, "unknown_origin"),
            (("ui.answer",), None, "unknown_origin"),
            (("user.text", "agents_md.instructions"), None, "mixed_origin"),
            (("user.text", "future.marker"), None, "mixed_origin"),
            ((), None, "malformed_metadata"),
            ((None,), None, "malformed_metadata"),
        ]
        for markers, expected, reason in cases:
            with self.subTest(markers=markers):
                path = self.root / "origins.jsonl"
                write_jsonl(path, [codex_message(markers=markers), codex_tokens()])
                result = collect([path])
                (thread,) = result["threads"]
                self.assertEqual(thread["user_messages"], expected)
                coverage = thread["user_message_coverage"]
                self.assertEqual(coverage["complete"], reason is None)
                self.assertEqual(coverage["unclassified"], int(reason is not None))
                self.assertEqual(coverage["reasons"], [reason] if reason else [])
                self.assertTrue(result["total"]["complete"])
        for value in (None, [], "user.text", {"content_item_kinds": "user.text"}):
            with self.subTest(metadata=value):
                record = codex_message()
                record["payload"]["internal_chat_message_metadata_passthrough"] = value
                write_jsonl(path, [record, codex_tokens()])
                (thread,) = collect([path])["threads"]
                self.assertIsNone(thread["user_messages"])
                self.assertEqual(thread["user_message_coverage"]["unclassified"], 1)

    def test_modern_replay_distinct_ids_and_conflicts_do_not_use_text_identity(self):
        path = self.root / "identities.jsonl"
        a = codex_message("a", "same text")
        b = codex_message("b", "same text")
        write_jsonl(path, [a, a, b, codex_tokens()])
        (thread,) = collect([path])["threads"]
        self.assertEqual(thread["user_messages"], 2)
        self.assertEqual(thread["user_message_coverage"]["observations"]["modern"], 3)
        for conflicting in (codex_message("a", "changed text"), codex_message("a", markers=("agents_md.instructions",))):
            with self.subTest(payload=conflicting["payload"]):
                write_jsonl(path, [a, conflicting, codex_tokens()])
                result = collect([path])
                self.assertIsNone(result["total"]["user_messages"])
                self.assertIn("conflicting_message_id", result["threads"][0]["user_message_coverage"]["reasons"])
        for message_id in (None, "", 7, False, []):
            with self.subTest(message_id=message_id):
                write_jsonl(path, [codex_message(message_id), codex_tokens()])
                (thread,) = collect([path])["threads"]
                self.assertIsNone(thread["user_messages"])
                self.assertIn("missing_message_id", thread["user_message_coverage"]["reasons"])

    def test_mixed_streams_never_guess_correspondence(self):
        path = self.root / "mixed.jsonl"
        modern = codex_message(text="same text")
        legacy = {"type": "event_msg", "timestamp": modern["timestamp"],
                  "payload": {"type": "user_message", "message": "same text"}}
        write_jsonl(path, [modern, legacy, codex_tokens()])
        result = collect([path])
        (thread,) = result["threads"]
        self.assertIsNone(thread["user_messages"])
        coverage = thread["user_message_coverage"]
        self.assertEqual(coverage["observations"], {"legacy": 1, "modern": 1})
        self.assertEqual(coverage["reasons"], ["ambiguous_representations"])
        table = render(result)
        self.assertIn("legacy=1, modern=1", table)
        self.assertIn("ambiguous_representations", table)
        self.assertIn("?", table)
        self.assertIsNone(result["total"]["user_messages"])

    def test_same_ids_in_separate_files_remain_separate_per_file_counts(self):
        for name in ("one", "two"):
            write_jsonl(self.root / f"{name}.jsonl", [codex_message(), codex_tokens()])
        result = collect([self.root])
        self.assertEqual(len(result["threads"]), 2)
        self.assertEqual(result["total"]["user_messages"], 2)
        self.assertEqual(result["total"]["user_message_coverage"]["observations"]["modern"], 2)

    def test_unknown_threads_and_files_do_not_become_exact_aggregate_zeroes(self):
        write_jsonl(self.root / "known.jsonl", [codex_message(), codex_tokens()])
        write_jsonl(self.root / "unknown.jsonl", [codex_message(markers=("future.marker",)), codex_tokens()])
        result = collect([self.root])
        self.assertIsNone(result["total"]["user_messages"])
        self.assertTrue(result["total"]["complete"])
        self.assertEqual(result["total"]["user_message_coverage"]["unclassified"], 1)
        write_jsonl(self.root / "other.jsonl", [{"unrecognized": "format"}])
        result = collect([self.root])
        self.assertIsNone(result["total"]["user_messages"])
        self.assertIn("unrecognized_files", result["total"]["user_message_coverage"]["reasons"])

    def test_damaged_and_partial_logs_invalidate_human_coverage(self):
        for tail, reason in (("{bad}\n", "damaged_lines"), ('{"type":', "partial_line")):
            with self.subTest(reason=reason):
                path = self.root / "partial.jsonl"
                write_jsonl(path, [codex_message(), codex_tokens()], tail=tail)
                result = collect([path])
                self.assertIsNone(result["total"]["user_messages"])
                self.assertFalse(result["total"]["complete"])
                self.assertIn(reason, result["threads"][0]["user_message_coverage"]["reasons"])
                self.assertEqual(result["total"]["user_message_coverage"]["observations"]["modern"], 1)

    def test_repeated_contexts_keep_existing_call_and_model_totals(self):
        path = self.root / "contexts.jsonl"
        context = {"type": "turn_context", "payload": {"model": "gpt-luna", "turn_id": "turn-a", "root_turn_id": "root-a"}}
        write_jsonl(path, [context, context, {"type": "turn_context", "payload": {"model": "gpt-sol", "turn_id": "turn-a"}},
                           {"type": "turn_context", "payload": {"turn_id": "turn-b"}}, codex_tokens()])
        result = collect([path])
        (thread,) = result["threads"]
        self.assertEqual(thread["calls"], 3)
        self.assertEqual(thread["models"], {"gpt-luna": 2, "gpt-sol": 1})
        self.assertEqual(result["models"]["gpt-luna"]["calls"], 2)
        self.assertEqual(thread["counted"], "model_context_rows")
        self.assertIn("model_context_rows", render(result))

    def test_marked_malformed_content_does_not_claim_an_exact_count(self):
        path = self.root / "content.jsonl"
        for content in (None, [], "text", [None], [{"type": "input_text", "text": 42}]):
            with self.subTest(content=content):
                record = codex_message()
                record["payload"]["content"] = content
                write_jsonl(path, [record, codex_tokens()])
                (thread,) = collect([path])["threads"]
                self.assertIsNone(thread["user_messages"])
                self.assertEqual(thread["user_message_coverage"]["observations"]["modern"], 1)
                self.assertIn("malformed_content", thread["user_message_coverage"]["reasons"])

    def test_cumulative_counter_reset_policy_is_unchanged(self):
        path = self.root / "reset.jsonl"
        write_jsonl(path, [codex_message(), codex_tokens(input_tokens=500, output_tokens=50),
                           codex_tokens(input_tokens=40, cached_input_tokens=5, output_tokens=3)])
        (thread,) = collect([path])["threads"]
        self.assertEqual((thread["fresh_input"], thread["cache_read"], thread["output"]), (35, 5, 3))
        self.assertEqual(thread["user_messages"], 1)

    def test_cli_json_and_table(self):
        write_jsonl(self.root / "s.jsonl", [claude_turn("m1")])
        command = [sys.executable, "-m", "awkit", "usage", str(self.root)]
        env = child_env()
        table = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(table.returncode, 0, table.stderr)
        self.assertIn("claude-sonnet", table.stdout)
        self.assertIn("total", table.stdout)
        self.assertNotIn("?", table.stdout)
        data = json.loads(subprocess.run(command + ["--json"], capture_output=True, text=True,
                                         encoding="utf-8", env=env).stdout)
        self.assertEqual(data["format"], 3)
        self.assertEqual(data["total"]["cache_write"], 100)
        future = subprocess.run(command + ["--since", "2999-01-01", "--json"], capture_output=True,
                                text=True, encoding="utf-8", env=env)
        self.assertEqual(json.loads(future.stdout)["threads"], [])
        write_jsonl(self.root / "gap.jsonl", [claude_turn("m2", usage={"input_tokens": 1})])
        table = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertIn("?", table.stdout)
        self.assertIn("known", table.stdout)
        self.assertIn("unmeasured", table.stdout)
        modern = self.root / "modern.jsonl"
        write_jsonl(modern, [codex_message(None), codex_tokens()])
        modern_command = [sys.executable, "-m", "awkit", "usage", str(modern)]
        uncertain_json = subprocess.run(modern_command + ["--json"], capture_output=True, text=True,
                                        encoding="utf-8", env=env)
        uncertain_table = subprocess.run(modern_command, capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(uncertain_json.returncode, 0, uncertain_json.stderr)
        self.assertEqual(uncertain_table.returncode, 0, uncertain_table.stderr)
        uncertain = json.loads(uncertain_json.stdout)
        self.assertIsNone(uncertain["total"]["user_messages"])
        self.assertEqual(uncertain["total"]["user_message_coverage"]["observations"]["modern"], 1)
        self.assertIn("modern=1", uncertain_table.stdout)
        self.assertIn("missing_message_id", uncertain_table.stdout)
        self.assertIn("human-input coverage: incomplete", uncertain_table.stdout)


if __name__ == "__main__":
    unittest.main()
