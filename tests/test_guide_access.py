"""Guide access needs a recognized operation and its own successful returned content."""

import json
import tempfile
import unittest
from pathlib import Path

from awkit.session_rules import guide_access, read_transcript, reply_check

GUIDE = (Path(__file__).resolve().parents[1] / "kit/writing.md").read_text(encoding="utf-8")
DOCUMENT = "# Example\n\n" + chr(0xAC00) * 600


def call(identity="read", command="awkit kit guide writing", *, name="exec_command", arguments=None):
    return {"type": "response_item", "payload": {"type": "function_call", "call_id": identity, "name": name,
            "arguments": json.dumps({"cmd": command} if arguments is None else arguments)}}


def result(identity="read", code=0, text=GUIDE):
    return {"type": "response_item", "payload": {"type": "function_call_output", "call_id": identity,
            "output": json.dumps({"exit_code": code, "output": text})}}


class GuideAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "session.jsonl"

    def check(self, records, state):
        self.assertEqual(guide_access(records), state)
        self.path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
        finding = reply_check({"transcript_path": str(self.path), "last_assistant_message": DOCUMENT}, 500)
        self.assertEqual(finding is not None, state == "absent")

    def test_successful_cli_and_single_shell_reads_return_guide_content(self):
        for command in ("awkit kit guide writing", "Get-Content kit/writing.md", "Get-Content -Raw -LiteralPath 'kit/writing.md'",
                        "cat agent-work-kit/writing.md", ["cat", "kit/writing.md"]):
            with self.subTest(command=command):
                self.check([call(command=command), result()], "read")

    def test_custom_and_local_shell_envelopes_use_their_own_outputs(self):
        custom = call()
        custom["payload"]["type"] = "custom_tool_call"
        custom["payload"]["input"] = custom["payload"].pop("arguments")
        custom_output = result()
        custom_output["payload"]["type"] = "custom_tool_call_output"
        self.check([custom, custom_output], "read")
        local = {"type": "response_item", "payload": {"type": "local_shell_call", "call_id": "read",
                 "action": {"command": ["cat", "kit/writing.md"]}}}
        local_output = result()
        local_output["payload"]["type"] = "local_shell_call_output"
        self.check([local, local_output], "read")

    def test_claude_read_and_skill_correlate_their_results(self):
        for name, arguments in (("Read", {"file_path": "/kit/writing.md"}), ("Skill", {"skill": "awkit-writing"}),
                                 ("Read", {"file_path": "/skills/awkit-writing/SKILL.md"})):
            with self.subTest(name=name, arguments=arguments):
                use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "read", "name": name,
                                                                      "input": arguments}]}}
                output = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read",
                           "content": [{"type": "text", "text": GUIDE}]}]}}
                self.check([use, output], "read")  # absent is_error is the supported Claude success convention
                output["message"]["content"][0]["content"] = "Read kit/writing.md and follow it."
                self.check([use, output], "unknown")
                output["message"]["content"][0]["content"] = GUIDE
                output["message"]["content"][0]["is_error"] = True
                self.check([use, output], "absent")

    def test_explicit_failure_is_absent_and_a_fresh_retry_can_succeed(self):
        failed = [call(), result(code=1, text="File not found")]
        self.check(failed, "absent")
        self.check([call(), result(code=1)], "absent")
        self.check([*failed, call("retry"), result("retry")], "read")

    def test_mentions_do_not_establish_access_even_if_output_contains_the_guide(self):
        for command in ("echo kit/writing.md", 'printf "%s" "kit/writing.md"', "rg writing.md .", "# cat kit/writing.md",
                        'python -c "print(\'kit/writing.md\')"'):
            with self.subTest(command=command):
                self.check([call(command=command), result()], "absent")

    def test_wrong_interleaved_or_premature_results_do_not_supply_success(self):
        self.check([call(), result("other")], "unknown")
        self.check([result(), call()], "unknown")
        self.check([call(), call("status", "git status"), result("status"), result()], "read")
        self.check([call(), call("other", "git status"), result("other")], "unknown")

    def test_provider_id_namespaces_do_not_credit_another_providers_result(self):
        claude_call = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "read", "name": "Read", "input": {"file_path": "kit/writing.md"}}]}}
        claude_result = {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "read", "content": GUIDE}]}}
        self.check([claude_call, result()], "unknown")
        self.check([call(), claude_result], "unknown")

    def test_missing_and_reused_call_or_result_ids_are_unknown(self):
        for records in ([call()], [call(None), result(None)], [call(), call(), result()],
                        [call(), call(command="echo kit/writing.md"), result()],
                        [call(), result(), result(code=1)], [call(), result(), result()]):
            with self.subTest(records=records):
                self.check(records, "unknown")

    def test_empty_pointer_truncated_and_unfamiliar_outputs_remain_unknown(self):
        for text in ("", "Read kit/writing.md and follow it.", "# Writing Guide\n\n## Before writing\n",
                     GUIDE + "\nOutput truncated", "# A renamed guide\n\n## Different sections\n"):
            with self.subTest(text=text[:45]):
                self.check([call(), result(text=text)], "unknown")
        for command in ("head -n 5 kit/writing.md", "Get-Content kit/writing.md -TotalCount 5", "cat kit/korean-writing.md"):
            with self.subTest(command=command):
                self.check([call(command=command), result()], "unknown")
        self.check([call(command="echo kit/writing.md; cat kit/writing.md"), result()], "unknown")
        self.check([call(name="Read", arguments={"file_path": "kit/writing.md", "limit": 20}), result()], "unknown")

    def test_explicit_truncation_markers_override_present_beginning_and_end_sections(self):
        for marker in ("Warning: truncated output (original token count: 2000)", "Warning: output truncated",
                       "12 tokens truncated", "truncated lines"):
            with self.subTest(marker=marker):
                text = GUIDE.replace("## Write plainly", marker + "\n\n## Write plainly")
                self.assertIn("# Writing Guide", text)
                self.assertIn("## Before writing", text)
                self.assertIn("## Completion check", text)
                self.check([call(), result(text=text)], "unknown")

    def test_harmless_heading_variations_and_read_line_numbers_are_supported(self):
        text = GUIDE.replace("# Writing Guide", "##  Writing   Guide  ##").replace("## Before writing", "### Before Writing")
        text = "\n".join(f"{index}→{line}" for index, line in enumerate(text.splitlines(), 1))
        self.check([call(), result(text=text)], "read")

    def test_missing_malformed_or_nonfinal_child_status_is_unknown(self):
        for output in ("not JSON", json.dumps({"output": GUIDE}), json.dumps({"exit_code": None, "output": GUIDE}),
                       json.dumps({"exit_code": True, "output": GUIDE}), json.dumps([{"text": GUIDE}])):
            with self.subTest(output=output[:45]):
                record = result()
                record["payload"]["output"] = output
                self.check([call(), record], "unknown")

    def test_only_the_exact_exec_wrapper_with_correlated_child_result_is_supported(self):
        outer = {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "call_id": "read",
                 "input": 'text(await tools.exec_command({"cmd":"awkit kit guide writing"}));'}}
        output = {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "read",
                  "output": [{"type": "text", "text": json.dumps({"exit_code": 0, "output": GUIDE})}]}}
        self.check([outer, output], "read")
        output["payload"]["output"] = [
            {"type": "input_text", "text": "Script completed\nWall time 1.2 seconds\nOutput:\n"},
            {"type": "input_text", "text": json.dumps({"exit_code": 0, "output": GUIDE})}]
        self.check([outer, output], "read")
        output["payload"]["output"][1]["text"] = json.dumps({"exit_code": 1, "output": "File not found"})
        self.check([outer, output], "absent")
        output["payload"]["output"][1]["text"] = json.dumps({"exit_code": 0, "output": GUIDE})
        for source in ('text(await tools.exec_command({"cmd":"echo kit/writing.md"}));',
                       'const r = await tools.exec_command({"cmd":"cat kit/writing.md"}); text(r.output);',
                       'text(await tools.exec_command({cmd:"cat kit/writing.md"}));'):
            with self.subTest(source=source):
                outer["payload"]["input"] = source
                self.check([outer, output], "absent" if "echo" in source else "unknown")

    def test_malformed_or_partial_transcripts_are_unknown_and_fail_open(self):
        self.assertEqual(guide_access(None), "unknown")
        self.assertIsNone(read_transcript(str(self.path)))
        for text in ('{"type":', '{}\n{bad}\n', '[]\n', '{}', '\ufffd\n'):
            with self.subTest(text=text):
                self.path.write_text(text, encoding="utf-8")
                self.assertIsNone(read_transcript(str(self.path)))
                self.assertIsNone(reply_check({"transcript_path": str(self.path), "last_assistant_message": DOCUMENT}, 500))

    def test_complete_no_read_transcript_blocks_only_the_existing_long_document_case(self):
        self.check([call(command="git status"), result(text="clean")], "absent")
        for reply in ("# Short\n", chr(0xAC00) * 600):
            self.assertIsNone(reply_check({"transcript_path": str(self.path), "last_assistant_message": reply}, 500))
        self.assertIsNone(reply_check({"last_assistant_message": DOCUMENT}, 500))

    def test_a_known_success_is_independent_of_an_earlier_unfinished_call(self):
        self.check([call("unfinished"), call("retry"), result("retry")], "read")
