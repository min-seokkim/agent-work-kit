"""The hook runner and the kit's example rules.

Each example rule has two tests: it catches the tool call it is for, and it stays silent on an ordinary
one. The runner's failure paths (a broken input, a command that runs too long, no rules file) allow the
call and say so in the log, because a hook that fires wrongly costs more trust than a rule that misses.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from awkit import hooks
from awkit.checks import install_hooks
from awkit.review import git
from support import child_env

ROOT = Path(__file__).resolve().parents[1]
AGENT_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"


class Project(unittest.TestCase):
    """A repository with the owner's history and the kit's example rules at its root."""

    rules = ROOT / "kit" / "rules.toml"

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "project"
        self.root.mkdir()
        git(self.root, "init", "-q")
        git(self.root, "config", "core.autocrlf", "false")
        git(self.root, "config", "user.name", "owner")
        git(self.root, "config", "user.email", "owner@example.com")
        (self.root / "app.py").write_text("print(1)\n", encoding="utf-8")
        git(self.root, "add", "app.py")
        git(self.root, "commit", "-q", "-m", "First")
        if self.rules:
            shutil.copyfile(self.rules, self.root / "rules.toml")
        # Rule commands run `{python} -m awkit` from the project folder; they must import this source tree.
        patcher = mock.patch.dict("os.environ", child_env())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.session = "s1"

    def event(self, name, session=None, **fields):
        payload = {"hook_event_name": name, "session_id": session or self.session, "cwd": str(self.root),
                   "transcript_path": None, **fields}
        output = hooks.run(json.dumps(payload))
        return json.loads(output) if output else None

    def tool(self, name, tool_input, event="PreToolUse", session=None):
        return self.event(event, session, tool_name=name, tool_input=tool_input)

    def bash(self, command, **kwargs):
        return self.tool("Bash", {"command": command}, **kwargs)

    def write(self, name, content, event="PreToolUse", tool="Write", session=None):
        return self.tool(tool, {"file_path": str(self.root / name), "content": content}, event, session)

    def context(self, output):
        return output["hookSpecificOutput"]["additionalContext"]

    def log(self):
        path = self.root / ".awkit" / "hooks.ndjson"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


class CommitIdentityRule(Project):
    def test_agent_trailer_and_identity_are_refused_before_the_commit(self):
        # F9: commits authored as the agent with Co-Authored-By lines, in a repository whose history has
        # only the owner's commits without trailers. The message comes in a heredoc, as agents write it.
        command = ("git add app.py && git commit -m \"$(cat <<'EOF'\nFix the parser\n\nBody.\n\n"
                   f"{AGENT_TRAILER}\nEOF\n)\"")
        output = self.bash(command)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertTrue(output["permissionDecisionReason"].startswith("awkit commit-identity (F9): "))
        self.assertIn("Co-Authored-By", output["permissionDecisionReason"])
        agent = self.bash("GIT_AUTHOR_NAME=Claude GIT_AUTHOR_EMAIL=noreply@anthropic.com git commit -m Fix")
        self.assertIn("noreply@anthropic.com", agent["hookSpecificOutput"]["permissionDecisionReason"])
        flag = self.bash('git commit --author="Claude <noreply@anthropic.com>" -m Fix')
        self.assertEqual(flag["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual([e["decision"] for e in self.log()], ["deny", "deny", "deny"])

    def test_the_owners_commit_and_other_commands_pass_silently(self):
        self.assertIsNone(self.bash('git commit -m "Fix the parser" -m "Body text."'))
        self.assertIsNone(self.bash("git status && git log --oneline -3"))
        self.assertEqual(self.log(), [])
        self.assertIsNone(self.bash('git commit -m "unclosed'))  # allowed, with unavailable-check evidence
        self.assertEqual(self.log()[-1]["decision"], "error")
        self.assertIn("No closing quotation", self.log()[-1]["reason"])

    def test_a_commit_after_cd_is_judged_by_that_repository(self):
        # Seen in this repository: `cd` into another repository and committing there was refused with this
        # repository's history. The other repository has another person's history, so their commit passes.
        other = self.root.parent / "other"
        other.mkdir()
        git(other, "init", "-q")
        git(other, "config", "user.name", "someone")
        git(other, "config", "user.email", "someone@example.com")
        (other / "a.txt").write_text("a", encoding="utf-8")
        git(other, "add", "a.txt")
        git(other, "commit", "-q", "-m", "First")
        author = "GIT_AUTHOR_NAME=someone GIT_AUTHOR_EMAIL=someone@example.com"
        self.assertIsNone(self.bash(f'cd "{other}" && {author} git commit -m "Next"'))
        self.assertIsNone(self.bash(f'cd ../other && {author} git commit -m "Next"'))
        self.assertIsNotNone(self.bash(f'{author} git commit -m "Next"'))  # here they have no history
        # The same commit in this repository is still refused.
        refused = self.bash('cd . && GIT_AUTHOR_NAME=Claude GIT_AUTHOR_EMAIL=noreply@anthropic.com git commit -m Fix')
        self.assertEqual(refused["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_text_fed_to_a_program_is_not_a_command(self):
        # Seen in this repository: a script passed to python on a heredoc held a test string with an agent's
        # commit, and the script's triple quotes unbalanced the shell's, so the string read as a command.
        script = ("python3 - <<'EOF'\nt = '\'\'\n"
                  "run('cd . && GIT_AUTHOR_NAME=Claude GIT_AUTHOR_EMAIL=noreply@anthropic.com git commit -m Fix')\n"
                  "'\'\'\nEOF\n")
        self.assertIsNone(self.bash(script))
        self.assertIsNone(self.bash("cat > notes.txt <<EOF\ngit commit -m x -m '" + AGENT_TRAILER + "'\nEOF"))


class DoneCheckRule(Project):
    def test_stop_with_unchecked_changes_is_blocked_once(self):
        # F1: the agent stops with changed files that no check has seen.
        self.assertIsNone(self.event("SessionStart", source="startup"))
        (self.root / "app.py").write_text("print(2)\n", encoding="utf-8")
        output = self.event("Stop", stop_hook_active=False)
        self.assertEqual(output["decision"], "block")
        self.assertTrue(output["reason"].startswith("awkit done-check (F1): "))
        self.assertIn("app.py", output["reason"])
        # The second stop in the same turn passes, so the agent can report what it could not check.
        self.assertIsNone(self.event("Stop", stop_hook_active=True))

    def test_stop_without_changes_is_silent(self):
        self.assertIsNone(self.event("SessionStart", source="startup"))
        self.assertIsNone(self.event("Stop", stop_hook_active=False))
        self.assertEqual(self.log(), [])


class WritingCheckRule(Project):
    def test_an_edited_document_with_errors_blocks_once(self):
        # F13, F14: an em dash, and -세요 mixed with -시오, in a document the agent just wrote.
        (self.root / "guide.md").write_text("Agent Work Kit — a kit.\n\n켜세요.\n백업하십시오.\n", encoding="utf-8")
        output = self.write("guide.md", "x", event="PostToolUse")
        self.assertEqual(output["decision"], "block")
        self.assertIn("em-dash", output["reason"])
        self.assertIn("mixed-endings", output["reason"])
        # The same failure is not repeated on the next edit; a different one is.
        self.assertIsNone(self.write("guide.md", "x", event="PostToolUse"))
        (self.root / "guide.md").write_text("Agent Work Kit — a kit.\n", encoding="utf-8")
        self.assertEqual(self.write("guide.md", "x", event="PostToolUse")["decision"], "block")

    def test_clean_documents_and_other_files_are_silent(self):
        (self.root / "guide.md").write_text("A kit for agents.\n", encoding="utf-8")
        self.assertIsNone(self.write("guide.md", "x", event="PostToolUse"))
        (self.root / "notes.py").write_text("# a — b\n", encoding="utf-8")
        self.assertIsNone(self.write("notes.py", "x", event="PostToolUse"))
        # A deleted document has nothing to check.
        self.assertIsNone(self.write("gone.md", "x", event="PostToolUse"))


class KoreanWritingRule(Project):
    def test_first_korean_markdown_edit_gets_the_guide_once(self):
        output = self.write("안내.md", "서버를 켜기 전에 전원을 확인하세요.")
        text = self.context(output)
        self.assertTrue(text.startswith("awkit korean-writing (F14): "))
        self.assertIn("agent-work-kit/korean-writing.md", text)
        self.assertIsNone(self.tool("Edit", {"file_path": str(self.root / "b.md"), "old_string": "a",
                                             "new_string": "한국어 문장"}))
        # Once per session: another session hears it again.
        self.assertIsNotNone(self.write("안내.md", "확인하세요.", session="s2"))

    def test_english_markdown_and_korean_code_are_silent(self):
        self.assertIsNone(self.write("guide.md", "Check the power first."))
        self.assertIsNone(self.write("app.py", "print('안녕하세요')"))


class ResearchRule(Project):
    def test_first_web_search_or_fetch_gets_the_guide_once(self):
        text = self.context(self.tool("WebSearch", {"query": "hook contract"}))
        self.assertTrue(text.startswith("awkit research (F23, F37): "))
        self.assertLessEqual(len(text.split(": ", 1)[1]), hooks.MESSAGE_LIMIT)
        self.assertIsNone(self.tool("WebFetch", {"url": "https://example.com"}))
        self.assertEqual([(e["rule"], e["decision"]) for e in self.log()], [("research", "context")])

    def test_other_tools_are_silent(self):
        self.assertIsNone(self.tool("Read", {"file_path": str(self.root / "app.py")}))
        self.assertIsNone(self.tool("Grep", {"pattern": "search"}))


class DeliveryRule(Project):
    def test_push_and_upload_commands_get_the_guide(self):
        self.assertIn("awkit delivery (F24)", self.context(self.bash("git push -u origin dev")))
        self.assertIsNotNone(self.bash("twine upload dist/*", session="s2"))
        self.assertIsNotNone(self.bash("rsync -a site/ host:/srv/site", session="s3"))

    def test_local_commands_are_silent(self):
        self.assertIsNone(self.bash("git status && git stash push -m wip"))
        self.assertIsNone(self.bash("echo 'push the button'"))


class DelegationRule(Project):
    def test_starting_a_subagent_gets_the_guide(self):
        self.assertIn("awkit delegation (F19, F21)", self.context(self.tool("Agent", {"prompt": "review"})))
        # Codex calls the tool spawn_agent; it matches rules written for Agent.
        self.assertIsNotNone(self.tool("spawn_agent", {"message": "review"}, session="codex"))

    def test_other_tools_are_silent(self):
        self.assertIsNone(self.bash("ls"))
        self.assertIsNone(self.tool("TodoWrite", {"todos": []}))


class CodexEvents(Project):
    def test_apply_patch_edits_match_rules_for_edit_and_write(self):
        patch = "*** Begin Patch\n*** Add File: docs/안내.md\n+전원을 확인하세요.\n*** End Patch\n"
        self.assertIn("korean-writing", self.context(self.tool("apply_patch", {"command": patch})))
        (self.root / "docs").mkdir()
        (self.root / "docs" / "안내.md").write_text("확인하세요.\n백업하시오.\n", encoding="utf-8")
        output = self.tool("apply_patch", {"command": patch}, event="PostToolUse")
        self.assertIn("mixed-endings", output["reason"])

    def test_snake_case_event_names_are_read(self):
        self.assertIsNotNone(self.event("pre_tool_use", tool_name="WebSearch", tool_input={"query": "x"}))


class FailurePaths(Project):
    def test_broken_input_is_allowed_and_logged(self):
        for text in ("{not json", "[1, 2]", ""):
            self.assertEqual(hooks.run(text, self.root), "")
        self.assertEqual([e["decision"] for e in self.log()], ["error"] * 3)
        result = subprocess.run([sys.executable, "-m", "awkit", "hook"], cwd=self.root, input="{", capture_output=True,
                                text=True, encoding="utf-8", env=child_env())
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_a_command_that_runs_too_long_is_allowed_and_logged(self):
        (self.root / "rules.toml").write_text(
            'schema = 1\n[[rules]]\nname = "slow"\nkind = "block"\ntools = ["Bash"]\ntimeout = 0.5\n'
            'command = ["{python}", "-c", "import time; time.sleep(30)"]\n', encoding="utf-8")
        started = time.monotonic()
        self.assertIsNone(self.bash("ls"))
        self.assertLess(time.monotonic() - started, 20)
        [entry] = self.log()
        self.assertEqual((entry["rule"], entry["decision"]), ("slow", "error"))
        self.assertIn("timed out", entry["reason"])

    def test_a_broken_rule_is_reported_once_and_the_others_still_run(self):
        text = (self.root / "rules.toml").read_text(encoding="utf-8")
        (self.root / "rules.toml").write_text(text + '\n[[rules]]\nname = "bad"\nkind = "inject"\nevents = ["Stop"]\n'
                                              'message = "x"\n', encoding="utf-8")
        self.assertIsNotNone(self.tool("WebSearch", {"query": "x"}))
        self.assertIsNone(self.tool("WebSearch", {"query": "y"}))
        errors = [e for e in self.log() if e["decision"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot run on Stop", errors[0]["reason"])

    def test_a_missing_command_is_allowed_and_logged(self):
        (self.root / "rules.toml").write_text('schema = 1\n[[rules]]\nname = "gone"\nkind = "verify"\n'
                                              'command = ["no-such-program-awkit"]\n', encoding="utf-8")
        self.assertIsNone(self.event("Stop", stop_hook_active=False))
        self.assertIn("could not run", self.log()[0]["reason"])


class UnexpectedErrorContext(Project):
    def unexpected(self, **fields):
        payload = {"hook_event_name": "Stop", "session_id": self.session,
                   "cwd": str(self.root), **fields}
        with mock.patch.object(hooks, "_run", side_effect=ModuleNotFoundError("invented missing module")):
            return hooks.run(json.dumps(payload))

    def test_process_context_is_useful_without_payload_argv_environment_or_locals(self):
        sentinels = ("PAYLOAD_SECRET", "ENV_SECRET", "ARGV_SECRET", "LOCAL_SECRET")

        def broken(*args):
            local_value = sentinels[3]
            self.assertEqual(local_value, "LOCAL_SECRET")
            raise ModuleNotFoundError("invented missing module")

        payload = {"hook_event_name": "Stop", "session_id": self.session, "cwd": str(self.root),
                   "prompt": sentinels[0], "tool_input": {"secret": sentinels[0]},
                   "client": "claimed-client", "permissions": "claimed-permission"}
        stdout = io.StringIO()
        with (mock.patch.object(hooks, "_run", side_effect=broken),
              mock.patch.dict(os.environ, {"AWKIT_TEST_SECRET": sentinels[1]}),
              mock.patch.object(sys, "argv", [sentinels[2]]), redirect_stdout(stdout)):
            output = hooks.run(json.dumps(payload))
        self.assertEqual((output, stdout.getvalue()), ("", ""))
        [entry] = self.log()
        self.assertEqual(set(entry), {"time", "session", "event", "rule", "decision", "reason", "context"})
        self.assertEqual((entry["rule"], entry["decision"]), (None, "error"))
        self.assertEqual(entry["reason"], repr(ModuleNotFoundError("invented missing module")))
        context = entry["context"]
        self.assertEqual(set(context), {"schema", "executable", "python_version", "cwd", "awkit_file",
                                        "hooks_file", "exception_type", "frames"})
        self.assertEqual(context["schema"], 1)
        self.assertEqual(context["executable"], sys.executable[:512])
        self.assertEqual(context["python_version"], sys.version[:256])
        self.assertEqual(context["cwd"], os.getcwd()[:512])
        self.assertNotEqual(context["cwd"], payload["cwd"])
        self.assertEqual(context["hooks_file"], hooks.__file__[:512])
        self.assertEqual(context["awkit_file"], sys.modules["awkit"].__file__[:512])
        self.assertEqual(context["exception_type"], "builtins.ModuleNotFoundError")
        self.assertTrue(any(frame["function"] == "run" and frame["line"] > 0
                            for frame in context["frames"]))
        for value in (*sentinels, "claimed-client", "claimed-permission", payload["cwd"]):
            self.assertNotIn(value, json.dumps(context))

    def test_nonstring_exception_metadata_is_not_stringified(self):
        conversions = []

        class SensitiveMetadata:
            def __str__(self):
                conversions.append("str")
                return "DIAGNOSTIC_SECRET"

            def __repr__(self):
                conversions.append("repr")
                return "DIAGNOSTIC_SECRET"

        error_type = type("MetadataError", (RuntimeError,), {"__module__": SensitiveMetadata()})
        with mock.patch.object(hooks, "_run", side_effect=error_type("invented")):
            self.assertEqual(hooks.run('{"session_id":"s1"}', self.root), "")
        self.assertEqual(conversions, [])
        context = self.log()[0]["context"]
        self.assertIsNone(context["exception_type"])
        self.assertNotIn("DIAGNOSTIC_SECRET", json.dumps(context))
        self.assertTrue(context["frames"])

    def test_unavailable_observations_do_not_replace_error_or_frames(self):
        with (mock.patch.object(hooks, "os", mock.Mock(wraps=os)),
              mock.patch.object(hooks.os, "getcwd", side_effect=OSError("unavailable")),
              mock.patch.object(hooks, "find_root", return_value=self.root),
              mock.patch.object(sys, "executable", None), mock.patch.object(sys, "version", 42),
              mock.patch.object(sys.modules["awkit"], "__file__", None),
              mock.patch.object(hooks, "__file__", None),
              mock.patch.object(hooks, "_run", side_effect=ModuleNotFoundError("invented"))):
            # Hold the selected root fixed: isolate collection from existing root resolution.
            self.assertEqual(hooks.run('{"session_id":"s1","hook_event_name":"Stop"}', self.root), "")
        [entry] = self.log()
        for key in ("cwd", "executable", "python_version", "awkit_file", "hooks_file"):
            self.assertIsNone(entry["context"][key])
        self.assertEqual(entry["context"]["exception_type"], "builtins.ModuleNotFoundError")
        self.assertTrue(entry["context"]["frames"])

    def test_collector_failure_retains_one_legacy_reason_and_unavailable_context(self):
        with mock.patch.object(hooks, "_collect_error_context", side_effect=RuntimeError("collector failed")):
            self.assertEqual(self.unexpected(), "")
        [entry] = self.log()
        self.assertEqual(entry["reason"], repr(ModuleNotFoundError("invented missing module")))
        self.assertEqual(entry["context"]["schema"], 1)
        self.assertEqual(entry["context"]["frames"], [])
        self.assertTrue(all(value is None for key, value in entry["context"].items()
                            if key not in ("schema", "frames")))

    def test_strings_and_deep_awkit_tracebacks_are_bounded_without_source_reading(self):
        name = "frame_" + "f" * 200
        filename = "/synthetic/" + "x" * 1024 + ".py"
        namespace = {"__name__": "awkit.synthetic_context_test",
                     "Failure": type("Error" + "e" * 200, (ModuleNotFoundError,),
                                     {"__module__": "awkit.synthetic_context_test"})}
        code = (f"def {name}(depth):\n"
                f"    if depth: return {name}(depth - 1)\n"
                "    raise Failure('invented')\n")
        exec(compile(code, filename, "exec"), namespace)

        def broken(*args):
            namespace[name](80)

        with (mock.patch.object(hooks, "_run", side_effect=broken),
              mock.patch.object(sys, "executable", "e" * 1024),
              mock.patch.object(sys, "version", "v" * 1024),
              mock.patch.object(hooks, "__file__", "h" * 1024),
              mock.patch.object(sys.modules["awkit"], "__file__", "a" * 1024)):
            self.assertEqual(hooks.run('{"session_id":"s1"}', self.root), "")
        context = self.log()[0]["context"]
        for key in ("executable", "awkit_file", "hooks_file"):
            self.assertEqual(len(context[key]), 512)
        self.assertEqual(len(context["python_version"]), 256)
        self.assertEqual(len(context["exception_type"]), 128)
        self.assertEqual(len(context["frames"]), 8)
        for frame in context["frames"]:
            self.assertEqual(set(frame), {"file", "function", "line"})
            self.assertEqual((len(frame["file"]), len(frame["function"])), (512, 128))
            self.assertIs(type(frame["line"]), int)
            self.assertGreater(frame["line"], 0)
        self.assertLess(len(json.dumps(context)), 10_000)

    def test_traceback_scan_stops_even_with_a_custom_endless_chain(self):
        class EndlessTrace:
            reads = 0
            tb_frame = mock.Mock(f_globals={"__name__": "awkit.synthetic_context_test"})
            tb_frame.f_code.co_filename = "synthetic.py"
            tb_frame.f_code.co_name = "synthetic"

            @property
            def tb_lineno(self):
                return self.reads + 1

            @property
            def tb_next(self):
                self.reads += 1
                return self

        trace = EndlessTrace()

        class CustomTraceError(RuntimeError):
            def __getattribute__(self, name):
                return trace if name == "__traceback__" else super().__getattribute__(name)

        with mock.patch.object(hooks, "_run", side_effect=CustomTraceError("invented")):
            self.assertEqual(hooks.run('{"session_id":"s1"}', self.root), "")
        self.assertEqual(trace.reads, 64)
        self.assertEqual([frame["line"] for frame in self.log()[0]["context"]["frames"]], list(range(57, 65)))
        for invalid in (0, -1, True, "LINE_SECRET", 2**63):
            with self.subTest(line=invalid):
                trace = mock.Mock(tb_frame=EndlessTrace.tb_frame, tb_lineno=invalid, tb_next=None)
                with mock.patch.object(hooks, "_run", side_effect=CustomTraceError("invented")):
                    self.assertEqual(hooks.run('{"session_id":"s1"}', self.root), "")
                context = self.log()[-1]["context"]
                self.assertEqual(context["frames"], [])
                self.assertNotIn("LINE_SECRET", json.dumps(context))

    def test_unavailable_traceback_keeps_other_observations(self):
        class UntraceableError(RuntimeError):
            def __getattribute__(self, name):
                if name == "__traceback__":
                    raise OSError("trace unavailable")
                return super().__getattribute__(name)

        with mock.patch.object(hooks, "_run", side_effect=UntraceableError("invented")):
            self.assertEqual(hooks.run('{"session_id":"s1"}', self.root), "")
        context = self.log()[0]["context"]
        self.assertEqual(context["frames"], [])
        self.assertEqual(context["executable"], sys.executable[:512])
        self.assertTrue(context["exception_type"])

    def test_unwritable_log_and_logger_failure_still_allow_without_stdout(self):
        (self.root / ".awkit").write_text("owned fixture file", encoding="utf-8")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(self.unexpected(), "")
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual((self.root / ".awkit").read_text(encoding="utf-8"), "owned fixture file")
        with (mock.patch.object(hooks, "log", side_effect=RuntimeError("logger failed")) as logger,
              redirect_stdout(stdout)):
            self.assertEqual(self.unexpected(), "")
        self.assertEqual(logger.call_count, 1)
        self.assertEqual(stdout.getvalue(), "")

    def test_legacy_and_augmented_rows_have_identical_report_semantics(self):
        hooks.log(self.root, {"session": self.session, "event": "Stop", "rule": None,
                              "decision": "error", "reason": "legacy"})
        self.unexpected()
        self.tool("WebSearch", {"query": "hook contract"})
        before = hooks.report(self.root)
        [session] = before["sessions"]
        self.assertEqual((session["errors"], session["fired"], session["injected"]), (2, 1, 1))
        entries = self.log()
        self.assertNotIn("context", entries[0])
        self.assertIn("context", entries[1])
        self.assertNotIn("context", entries[2])
        entries[1].pop("context")
        (self.root / hooks.LOG_FILE).write_text(
            "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")
        self.assertEqual(hooks.report(self.root), before)

    def test_handled_rule_and_input_errors_keep_their_existing_shapes(self):
        self.assertEqual(hooks.run("{broken", self.root), "")
        (self.root / "rules.toml").write_text(
            'schema = 1\n[[rules]]\nname = "gone"\nkind = "verify"\n'
            'command = ["no-such-program-awkit"]\n', encoding="utf-8")
        self.assertIsNone(self.event("Stop"))
        self.assertEqual(len(self.log()), 2)
        self.assertTrue(all("context" not in entry for entry in self.log()))


class NoRules(Project):
    rules = None

    def test_without_rules_file_the_runner_does_nothing(self):
        self.assertIsNone(self.bash('git commit -m "x" -m "' + AGENT_TRAILER + '"'))
        self.assertIsNone(self.tool("WebSearch", {"query": "x"}))
        self.assertEqual(hooks.run("{broken", self.root), "")
        self.assertFalse((self.root / ".awkit").exists())
        self.assertIn("does nothing here", hooks.render_report(hooks.report(self.root)))


class RulesFormat(unittest.TestCase):
    def test_example_messages_are_short_and_end_with_what_to_do(self):
        rules, problems = hooks.load_rules(ROOT / "kit" / "rules.toml")
        self.assertEqual(problems, [])
        self.assertEqual(len(rules), 7)
        for rule in rules:
            self.assertTrue(rule.prevents, rule.name)
            if rule.message:
                self.assertLessEqual(len(rule.message), hooks.MESSAGE_LIMIT, rule.name)
                self.assertTrue(rule.message.endswith("."), rule.name)

    def test_wrong_rules_are_described(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rules.toml"
            path.write_text('schema = 1\n[[rules]]\nname = "a"\nkind = "inject"\nmessage = "' + "x" * 201 + '"\n'
                            '[[rules]]\nname = "b"\nkind = "verify"\n[[rules]]\nname = "c"\nkind = "block"\n'
                            'shell = "("\nmessage = "x"\n[[rules]]\nname = "d"\nkind = "block"\nmessage = "x"\n'
                            'colour = 1\n', encoding="utf-8")
            rules, problems = hooks.load_rules(path)
            self.assertEqual(rules, [])
            self.assertEqual([p.split(":")[0] for p in problems], ["rule a", "rule b", "rule c", "rule d"])
            path.write_text("schema = 2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                hooks.load_rules(path)


class Report(Project):
    def test_report_counts_firings_and_blocks_per_session(self):
        self.bash('git commit -m "x" -m "' + AGENT_TRAILER + '"')
        self.tool("WebSearch", {"query": "x"})
        self.tool("WebSearch", {"query": "x"}, session="s2")
        hooks.run("{broken", self.root)
        result = hooks.report(self.root)
        sessions = {s["session"]: s for s in result["sessions"]}
        self.assertEqual((sessions["s1"]["fired"], sessions["s1"]["blocked"], sessions["s1"]["injected"]), (2, 1, 1))
        self.assertEqual(sessions["s1"]["rules"], {"commit-identity": 1, "research": 1})
        self.assertEqual(sessions["s2"]["fired"], 1)
        self.assertEqual(sessions["(none)"]["errors"], 1)
        cli = subprocess.run([sys.executable, "-m", "awkit", "hook", "report", str(self.root)], capture_output=True,
                             text=True, encoding="utf-8", env=child_env())
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertIn("s1  fired 2, blocked 1", cli.stdout)


class Install(Project):
    rules = None

    def test_codex_settings_point_at_the_runner_with_the_kit_rules(self):
        (self.root / "kit").mkdir()
        (self.root / "kit" / "workflow.md").write_text("# Workflow\n", encoding="utf-8")
        result = install_hooks(self.root, use_git=False, use_codex=True)
        settings = json.loads((self.root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(settings["hooks"]), sorted(hooks.HOOK_EVENTS))
        entry = settings["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual((entry["type"], entry["command"]), ("command", "awkit hook --kit-rules"))
        self.assertFalse((self.root / "rules.toml").exists())
        self.assertEqual(len(result["installed"]), 1)
        again = install_hooks(self.root, use_git=False, use_codex=True)
        self.assertEqual((again["installed"], again["kept"]), ([], result["installed"]))
        # With --kit-rules the kit's rules apply, and the kit folder found in the project is what messages name.
        payload = {"hook_event_name": "PreToolUse", "session_id": "s", "cwd": str(self.root),
                   "tool_name": "WebSearch", "tool_input": {"query": "x"}}
        fired = json.loads(hooks.run(json.dumps(payload), kit_rules=True))
        self.assertIn("kit/work-types.md", fired["hookSpecificOutput"]["additionalContext"])

    def test_kit_rules_name_the_installed_kit_when_the_project_has_none(self):
        payload = {"hook_event_name": "PreToolUse", "session_id": "s", "cwd": str(self.root),
                   "tool_name": "WebSearch", "tool_input": {"query": "x"}}
        self.assertEqual(hooks.run(json.dumps(payload)), "")
        fired = json.loads(hooks.run(json.dumps(payload), kit_rules=True))
        from awkit.kit_install import kit_root
        self.assertIn(str(kit_root()), fired["hookSpecificOutput"]["additionalContext"])
        self.assertTrue(Path(str(kit_root()), "work-types.md").is_file())
        # A rule a project leaves out with --skip does not run.
        skipped = hooks.run(json.dumps({**payload, "session_id": "t"}), kit_rules=True, skip=["research"])
        self.assertEqual(skipped, "")

class InstalledResources(unittest.TestCase):
    def test_installed_namespace_guides_survive_the_hook_process(self):
        # A wheel puts kit/ below awkit without an __init__.py. Source-checkout
        # tests instead use the top-level kit/ fallback and missed this failure.
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            packages = base / "packages"
            shutil.copytree(ROOT / "src" / "awkit", packages / "awkit",
                            ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "kit", packages / "awkit" / "kit")
            script = '''
import json
import sys
from importlib.resources import files
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from awkit import hooks
from awkit.kit_hooks import draft_rules
root = Path(sys.argv[2])
folder = hooks.kit_folder(root)
payload = {"hook_event_name": "PreToolUse", "session_id": "bundled",
           "cwd": str(root), "tool_name": "WebSearch", "tool_input": {"query": "fictional"}}
bundled = json.loads(hooks.run(json.dumps(payload), kit_rules=True))
(root / "rules.toml").write_text(draft_rules(root), encoding="utf-8")
payload["session_id"] = "generated"
generated = json.loads(hooks.run(json.dumps(payload), kit_rules=True))
print(json.dumps({"namespace_type": type(files("awkit.kit")).__name__, "folder": folder,
                  "bundled": bundled, "generated": generated}))
'''
            for local in ((), ("kit",), ("agent-work-kit", "kit")):
                with self.subTest(local=local):
                    project = base / (local[0] if local else "installed")
                    project.mkdir()
                    git(project, "init", "-q")
                    for name in local:
                        folder = project / name
                        folder.mkdir()
                        for guide in ("workflow.md", "work-types.md"):
                            shutil.copyfile(ROOT / "kit" / guide, folder / guide)
                    result = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", script,
                                             str(packages), str(project)], capture_output=True,
                                            text=True, encoding="utf-8")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    data = json.loads(result.stdout)
                    self.assertEqual(data["namespace_type"], "MultiplexedPath")
                    expected = local[0] if local else str(packages / "awkit" / "kit")
                    self.assertEqual(data["folder"], expected)
                    context = data["bundled"]["hookSpecificOutput"]["additionalContext"]
                    self.assertEqual(context, data["generated"]["hookSpecificOutput"]["additionalContext"])
                    self.assertIn(f"{expected}/work-types.md", context)
                    self.assertNotIn("MultiplexedPath(", context)
                    # Inspect after the process exits, ruling out a temporary
                    # resource extraction whose lifetime ended with the hook.
                    self.assertEqual((project / expected / "work-types.md").read_bytes(),
                                     (ROOT / "kit" / "work-types.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
