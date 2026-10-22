"""The kit's default rules as `awkit kit hooks` writes them, and the runner's contract around them.

Each default rule has two tests: it catches the case it is for, and it prints nothing when there is no problem.
The writing-reply rule has three: a long Korean reply with a heading from a session that never read the writing
guide is blocked, a plain explanation of the same length passes, and a session that read the guide passes. The
runner's failure paths (a broken input, a command that runs too long, no rules file) allow the call.
"""

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from awkit import __version__, hooks, kit_hooks
from awkit.review import git
from support import child_env

AGENT_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"
# A reply of about 650 Hangul syllables: long by the default rule's measure (500).
BODY = "이 세션은 훅 실행기를 만들고 규칙 파일을 읽습니다. " * 50
DOCUMENT = "# 작업 지시\n\n## 배경\n\n" + BODY
EXPLANATION = "테스트가 실패한 이유를 설명합니다.\n\n" + BODY


class Project(unittest.TestCase):
    """A repository with the owner's history and the default rules in rules.toml."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        git(self.root, "init", "-q")
        git(self.root, "config", "core.autocrlf", "false")
        git(self.root, "config", "user.name", "owner")
        git(self.root, "config", "user.email", "owner@example.com")
        (self.root / "app.py").write_text("print(1)\n", encoding="utf-8")
        git(self.root, "add", "app.py")
        git(self.root, "commit", "-q", "-m", "First")
        (self.root / "rules.toml").write_text(kit_hooks.draft_rules(self.root), encoding="utf-8")
        git(self.root, "add", "rules.toml")
        git(self.root, "commit", "-q", "-m", "Add the rules")
        patcher = mock.patch.dict("os.environ", child_env())
        patcher.start()
        self.addCleanup(patcher.stop)

    def event(self, name, session="s1", **fields):
        payload = {"hook_event_name": name, "session_id": session, "cwd": str(self.root), "transcript_path": None,
                   **fields}
        output = hooks.run(json.dumps(payload, ensure_ascii=False))
        return json.loads(output) if output else None

    def tool(self, name, tool_input, event="PreToolUse", session="s1"):
        return self.event(event, session, tool_name=name, tool_input=tool_input)

    def bash(self, command, session="s1"):
        return self.tool("Bash", {"command": command}, session=session)

    def context(self, output):
        return output["hookSpecificOutput"]["additionalContext"]

    def log(self):
        path = self.root / ".awkit" / "hooks.ndjson"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


class CommitIdentity(Project):
    def test_an_agent_commit_is_refused_and_the_reason_ends_with_its_entry(self):
        output = self.bash(f'git commit -m "Fix" -m "{AGENT_TRAILER}"')["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertTrue(output["permissionDecisionReason"].endswith("failures.md: F9)"))

    def test_the_owners_commit_prints_nothing(self):
        self.assertIsNone(self.bash('git commit -m "Fix the parser"'))
        self.assertEqual(self.log(), [])


class DoneCheck(Project):
    def test_stopping_with_unchecked_changes_blocks_once_per_session(self):
        self.assertIsNone(self.event("SessionStart", source="startup"))
        (self.root / "app.py").write_text("print(2)\n", encoding="utf-8")
        output = self.event("Stop", stop_hook_active=False)
        self.assertEqual(output["decision"], "block")
        self.assertIn("app.py", output["reason"])
        self.assertTrue(output["reason"].endswith("failures.md: F1)"))
        # A later turn ends with the same and other changes: the check has had its one block in this session.
        (self.root / "more.py").write_text("x = 1\n", encoding="utf-8")
        self.assertIsNone(self.event("Stop", stop_hook_active=False))
        self.assertIsNotNone(self.event("Stop", session="s2", stop_hook_active=False))

    def test_stopping_without_changes_prints_nothing(self):
        self.assertIsNone(self.event("SessionStart", source="startup"))
        self.assertIsNone(self.event("Stop", stop_hook_active=False))
        self.assertEqual(self.log(), [])


class MarkdownEdits(Project):
    def write(self, name, content, event):
        (self.root / name).write_text(content, encoding="utf-8")
        return self.tool("Write", {"file_path": str(self.root / name), "content": content}, event=event)

    def test_an_edited_document_is_checked_and_korean_gets_the_guide_line(self):
        output = self.write("guide.md", "Agent Work Kit — a kit.\n", "PostToolUse")
        self.assertEqual(output["decision"], "block")
        self.assertIn("em-dash", output["reason"])
        line = self.context(self.write("안내.md", "전원을 확인하세요.\n", "PreToolUse"))
        self.assertTrue(line.startswith("awkit korean-writing (F14): "))
        self.assertIn("korean-writing.md", line)

    def test_a_clean_english_document_prints_nothing(self):
        self.assertIsNone(self.write("guide.md", "A kit for agents.\n", "PreToolUse"))
        self.assertIsNone(self.write("guide.md", "A kit for agents.\n", "PostToolUse"))


class WritingRequest(Project):
    def test_the_first_request_for_a_document_gets_the_guide_line_once(self):
        line = self.context(self.event("UserPromptSubmit", prompt="다른 세션에 붙일 지시문을 써 줘."))
        self.assertTrue(line.startswith("awkit writing-request (F14): "))
        self.assertIn("writing.md", line)
        self.assertIsNone(self.event("UserPromptSubmit", prompt="보고서도 작성해 줘."))
        self.assertIsNotNone(self.event("UserPromptSubmit", session="s2", prompt="Write a prompt for the reviewer."))

    def test_other_requests_and_pasted_material_print_nothing(self):
        self.assertIsNone(self.event("UserPromptSubmit", prompt="테스트를 돌리고 결과를 알려 줘."))
        pasted = "이 로그를 봐 줘.\n<pasted_content id=\"1\">\n보고서 문서 작성\n</pasted_content id=\"1\">"
        self.assertIsNone(self.event("UserPromptSubmit", prompt=pasted))


class WritingReply(Project):
    """The case this rule exists for: a planning session wrote a long Korean instruction for another session in
    the chat without calling the writing skill. No tool call was made, so only the result shows it."""

    def transcript(self, request, *tool_uses):
        records = [{"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": request}}]
        for name, tool_input in tool_uses:
            records.append({"type": "assistant", "message": {"role": "assistant", "model": "m", "content": [
                {"type": "tool_use", "id": "t", "name": name, "input": tool_input}]}})
        path = self.base / f"transcript-{len(list(self.base.glob('transcript-*')))}.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        return str(path)

    def stop(self, reply, transcript, session="s1"):
        return self.event("Stop", session, stop_hook_active=False, transcript_path=transcript,
                          last_assistant_message=reply)

    def test_a_document_from_a_session_that_never_read_the_guide_is_blocked(self):
        transcript = self.transcript("구현 세션에 붙일 지시문을 써 줘.", ("Bash", {"command": "git status"}))
        output = self.stop(DOCUMENT + "\n최종 결과 — 완료.\n", transcript)
        self.assertEqual(output["decision"], "block")
        self.assertIn("답글이 다른 곳에 쓰일 한국어 문서인데 작성 가이드를 읽지 않았다.", output["reason"])
        self.assertIn("em-dash", output["reason"])
        self.assertTrue(output["reason"].endswith("failures.md: F14)"))
        # Once per session: the rewritten reply is not judged again.
        self.assertIsNone(self.stop(DOCUMENT, transcript))

    def test_a_plain_explanation_of_the_same_length_passes(self):
        transcript = self.transcript("테스트가 왜 실패했는지 설명해 줘.", ("Bash", {"command": "git status"}))
        self.assertGreaterEqual(len(EXPLANATION), len(DOCUMENT))
        self.assertIsNone(self.stop(EXPLANATION, transcript))
        # Short Korean with a heading, and a reply without a transcript to judge by, pass too.
        self.assertIsNone(self.stop("# 결과\n\n완료했습니다.", transcript, session="s2"))
        self.assertIsNone(self.stop(DOCUMENT, None, session="s3"))
        self.assertEqual(self.log(), [])

    def test_a_session_that_read_the_guide_passes(self):
        for tool_use in (("Skill", {"skill": "awkit-writing"}), ("Read", {"file_path": "/x/kit/korean-writing.md"}),
                         ("Bash", {"command": "cat agent-work-kit/writing.md"})):
            transcript = self.transcript("구현 세션에 붙일 지시문을 써 줘.", tool_use)
            self.assertIsNone(self.stop(DOCUMENT, transcript, session=tool_use[0]), tool_use)
        # Codex writes its transcript as response items; a shell call that reads the guide counts the same.
        codex = self.base / "codex.jsonl"
        codex.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in [
            {"type": "event_msg", "payload": {"type": "user_message", "message": "보고서를 작성해 줘."}},
            {"type": "response_item", "payload": {"type": "function_call", "name": "shell",
                                                  "arguments": "{\"command\": [\"cat\", \"kit/writing.md\"]}"}},
        ]), encoding="utf-8")
        self.assertIsNone(self.stop(DOCUMENT, str(codex), session="codex"))
        self.assertEqual(self.log(), [])


class Research(Project):
    def test_the_first_search_gets_the_guide_line(self):
        self.assertIn("work-types.md", self.context(self.tool("WebSearch", {"query": "hook contract"})))
        self.assertIsNone(self.tool("WebFetch", {"url": "https://example.com"}))

    def test_other_tools_print_nothing(self):
        self.assertIsNone(self.tool("Read", {"file_path": str(self.root / "app.py")}))


class Delivery(Project):
    def test_a_push_gets_the_guide_line(self):
        self.assertIn("awkit delivery (F24)", self.context(self.bash("git push -u origin dev")))

    def test_local_commands_print_nothing(self):
        self.assertIsNone(self.bash("git stash push -m wip && git status"))
        # Seen in this session: a document mentioning `git push`, written with cat and a heredoc, got the line.
        self.assertIsNone(self.bash("cat > notes.md <<'EOF'\n| delivery | `git push`, a release |\nEOF\n"))


class Delegation(Project):
    def test_starting_a_subagent_gets_the_guide_line(self):
        self.assertIn("delegation.md", self.context(self.tool("Agent", {"prompt": "review"})))

    def test_other_tools_print_nothing(self):
        self.assertIsNone(self.tool("TodoWrite", {"todos": []}))


class KitVersion(Project):
    def test_another_recorded_kit_version_is_said_once(self):
        (self.root / "checks.toml").write_text('schema = 1\n[kit]\nversion = "0.0.1"\n', encoding="utf-8")
        line = self.context(self.event("SessionStart", source="startup"))
        self.assertIn(f"checks.toml records kit 0.0.1 but awkit {__version__}", line)
        self.assertIsNone(self.event("SessionStart", source="resume"))

    def test_the_same_version_or_no_key_prints_nothing(self):
        self.assertIsNone(self.event("SessionStart", source="startup"))
        (self.root / "checks.toml").write_text(f'schema = 1\n[kit]\nversion = "{__version__}"\n', encoding="utf-8")
        self.assertIsNone(self.event("SessionStart", session="s2", source="startup"))


class Contract(Project):
    def test_the_event_argument_names_an_event_the_input_leaves_out(self):
        payload = {"session_id": "s1", "cwd": str(self.root), "tool_name": "WebSearch", "tool_input": {}}
        result = subprocess.run([sys.executable, "-m", "awkit", "hook", "PreToolUse", "--kit-hooks"],
                                input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                                env=child_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("awkit research", json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_messages_fit_the_limit_however_long_the_kit_path(self):
        # With awkit installed by pipx, {kit} expanded to an 85-character path and three inject rules exceeded
        # the 200-character limit, so they were dropped as broken. The limit applies to the rule's own text.
        long_kit = "/home/someone/.local/share/pipx/venvs/agent-work-kit/lib/python3.13/site-packages/awkit/kit"
        rules, problems = hooks.load_rules([kit_hooks.Path(p) for p in hooks.default_rules(self.root)[0]], long_kit)
        self.assertEqual(problems, [])
        self.assertEqual(len(rules), 10)
        for rule in rules:
            self.assertTrue(rule.prevents, rule.name)
            if rule.message:
                self.assertTrue(rule.message.rstrip().endswith((".", "라.")), rule.name)

    def test_prompt_conditions_are_for_inject_rules_only(self):
        (self.root / "rules.toml").write_text('schema = 1\n[[rules]]\nname = "no"\nkind = "block"\n'
                                              'prompt = "x"\nmessage = "No."\n', encoding="utf-8")
        rules, problems = hooks.load_rules(self.root / "rules.toml")
        self.assertEqual(rules, [])
        self.assertIn("inject rules only", problems[0])


class FailurePaths(Project):
    def test_a_broken_input_is_allowed_with_one_log_line(self):
        self.assertEqual(hooks.run("{not json", self.root), "")
        self.assertEqual([e["decision"] for e in self.log()], ["error"])

    def test_a_command_that_runs_too_long_is_allowed_with_one_log_line(self):
        (self.root / "rules.toml").write_text(
            'schema = 1\n[[rules]]\nname = "slow"\nkind = "verify"\nevents = ["Stop"]\ntimeout = 0.5\n'
            'command = ["{python}", "-c", "import time; time.sleep(30)"]\n', encoding="utf-8")
        started = time.monotonic()
        self.assertIsNone(self.event("Stop", stop_hook_active=False))
        self.assertLess(time.monotonic() - started, 20)
        [entry] = self.log()
        self.assertEqual((entry["rule"], entry["decision"]), ("slow", "error"))

    def test_without_rules_file_the_call_is_allowed_with_one_log_line_per_session(self):
        (self.root / "rules.toml").unlink()
        self.assertIsNone(self.bash(f'git commit -m "x" -m "{AGENT_TRAILER}"'))
        self.assertFalse((self.root / ".awkit").exists())  # a folder that never used awkit gets nothing
        (self.root / ".awkit").mkdir()
        self.assertIsNone(self.bash(f'git commit -m "x" -m "{AGENT_TRAILER}"'))
        self.assertIsNone(self.tool("WebSearch", {"query": "x"}))
        [entry] = self.log()
        self.assertEqual(entry["decision"], "error")
        self.assertIn("no rules.toml", entry["reason"])


if __name__ == "__main__":
    unittest.main()
