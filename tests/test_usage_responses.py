"""Response identity and resume replay, independent of the number of context rows."""

import tempfile
import unittest
from pathlib import Path

from awkit.usage import collect
from test_usage import claude_turn, codex_message, codex_tokens, write_jsonl


class ResponseUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_multiple_responses_in_one_codex_turn_and_repeated_resume_segment(self):
        meta = {"type": "session_meta", "payload": {"id": "native-a"}}
        context = {"type": "turn_context", "payload": {"model": "gpt-fictional", "turn_id": "same-turn"}}
        first = [meta, codex_message(), context, codex_tokens(), codex_tokens()]
        second = first + [context, codex_tokens(input_tokens=200, output_tokens=30),
                          codex_tokens(input_tokens=200, output_tokens=30)]
        write_jsonl(self.root / "a.jsonl", first)
        write_jsonl(self.root / "b.jsonl", second)
        result = collect([self.root, self.root / "a.jsonl"])
        (thread,) = result["threads"]
        self.assertEqual(thread["calls"], 2)
        self.assertEqual(thread["models"], {"gpt-fictional": 2})
        self.assertEqual(thread["user_messages"], 1)
        self.assertEqual(thread["output"], 30)
        self.assertEqual(result["total"]["calls"], 2)
        self.assertEqual(len(thread["files"]), 2)

    def test_claude_repeated_id_uses_final_usage_and_resumed_files_once(self):
        user = {"type": "user", "sessionId": "native-b", "uuid": "user-1",
                "message": {"role": "user", "content": "Fictional greeting."}}
        first = [user, claude_turn("m1", sessionId="native-b")]
        updated = claude_turn("m1", sessionId="native-b", usage={"input_tokens": 3,
            "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000, "output_tokens": 25})
        write_jsonl(self.root / "a.jsonl", first)
        write_jsonl(self.root / "b.jsonl", first + [updated, claude_turn("m2", sessionId="native-b")])
        (thread,) = collect([self.root])["threads"]
        self.assertEqual(thread["calls"], 2)
        self.assertEqual(thread["output"], 45)
        self.assertEqual(thread["user_messages"], 1)

    def test_missing_claude_identity_is_unknown_even_with_request_id(self):
        missing = claude_turn(None, requestId="not-a-response-id")
        write_jsonl(self.root / "a.jsonl", [missing, missing])
        result = collect([self.root])
        self.assertIsNone(result["total"]["calls"])
        self.assertEqual(result["total"]["call_coverage"]["observed"], 0)
        self.assertEqual(result["total"]["call_coverage"]["reasons"], ["missing_response_id"])

    def test_claude_identity_counts_without_tokens_but_codex_context_does_not(self):
        response = claude_turn("message-a")
        del response["message"]["usage"]
        write_jsonl(self.root / "a.jsonl", [response])
        (thread,) = collect([self.root])["threads"]
        self.assertEqual(thread["calls"], 1)
        self.assertIsNone(thread["output"])

    def test_codex_reply_without_context_or_tokens_is_retained_as_unknown(self):
        write_jsonl(self.root / "a.jsonl", [{"type": "response_item", "payload": {
            "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Fictional answer."}]}}])
        (thread,) = collect([self.root])["threads"]
        self.assertIsNone(thread["calls"])
        self.assertEqual(thread["call_coverage"]["reasons"], ["missing_token_observations"])

    def test_unchanged_codex_totals_under_new_model_do_not_add_calls(self):
        write_jsonl(self.root / "a.jsonl", [
            {"type": "turn_context", "payload": {"model": "gpt-first"}}, codex_tokens(),
            {"type": "turn_context", "payload": {"model": "gpt-second"}}, codex_tokens(),
            codex_tokens(input_tokens=250),
        ])
        (thread,) = collect([self.root])["threads"]
        self.assertEqual(thread["calls"], 2)
        self.assertEqual(thread["models"], {"gpt-first": 1, "gpt-second": 1})

    def test_resumed_split_totals_follow_timestamps_instead_of_path_order(self):
        meta = {"type": "session_meta", "payload": {"id": "same-native"}}
        context = {"type": "turn_context", "payload": {"model": "gpt-fictional"}}
        old = [meta, context, {**codex_tokens(), "timestamp": "2026-01-01T00:00:01Z"}]
        new = [meta, context, {**codex_tokens(input_tokens=200, output_tokens=30), "timestamp": "2026-01-01T00:00:02Z"}]
        write_jsonl(self.root / "z-old.jsonl", old)
        write_jsonl(self.root / "a-new.jsonl", new)
        (thread,) = collect([self.root])["threads"]
        self.assertEqual(thread["calls"], 2)
        self.assertEqual(thread["output"], 30)

    def test_replayed_context_still_labels_the_next_new_response(self):
        meta = {"type": "session_meta", "payload": {"id": "same-native"}}
        first = {"type": "turn_context", "payload": {"model": "gpt-first"}}
        second = {"type": "turn_context", "payload": {"model": "gpt-second"}}
        write_jsonl(self.root / "a.jsonl", [meta, first, codex_tokens(), second, codex_tokens(input_tokens=200)])
        write_jsonl(self.root / "b.jsonl", [meta, first, codex_tokens(input_tokens=300)])
        (thread,) = collect([self.root])["threads"]
        self.assertEqual(thread["models"], {"gpt-first": 2, "gpt-second": 1})
