"""Commands behind the default rules that read the session instead of one tool call: `awkit hook reply` and
`awkit hook kit-version`. Each reads the hook event on stdin, prints what the rule should say and exits 1, or
prints nothing and exits 0. When it cannot tell, it exits 0: a rule that fires wrongly costs more than one
that misses.

Writing is the one situation that can end in the chat with no tool call, so no rule that reads tool calls
sees it. `reply` reads the result instead: the final reply, from the event's `last_assistant_message` (Claude
Code and Codex both send it on Stop) or the session's transcript, and the transcript for the turn's request
and for correlated evidence that the writing guide was returned. Transcripts are JSON lines: Claude Code writes `user` and
`assistant` records whose `message.content` holds `text` and `tool_use` blocks; Codex writes `response_item`
records (`message`, `function_call`, `custom_tool_call`, `local_shell_call`) and `event_msg` records
(`user_message`, `agent_message`). Both are only read.
"""

import ast
import json
import re
import shlex
import sys
import tomllib
from pathlib import Path

HANGUL = re.compile(r"[가-힣]")
HEADING = re.compile(r"^#{1,6}\s+\S")
FENCE = re.compile(r"^\s*(```|~~~)")
# The turn asked for text that will be used elsewhere: an instruction or prompt for another session, a document.
DOCUMENT_REQUEST = re.compile(r"(지시문|프롬프트|문서|보고서|안내문|prompt|instructions|document|report)"
                              r".{0,40}?(써|쓰|작성|만들|정리|write|draft)"
                              r"|(써|작성|write|draft).{0,40}?(지시문|프롬프트|문서|보고서|prompt|instructions|document)",
                              re.I | re.S)
# Mentions identify potentially relevant unsupported operations, never successful access.
GUIDE = re.compile(r"(?:korean-)?writing\.md|awkit-writing|kit\s+guide\s+(?:korean-)?writing", re.I)
EXEC_WRAPPER = re.compile(r"\s*text\(await tools\.exec_command\((\{.*\})\)\);\s*", re.S)

# The failure catalogue entries (kit/failures.md) these commands guard: Korean written for others without the
# guide that the agent itself was given (F14), and guidance followed for another version of the kit (F25).
PREVENTS = {"awkit hook reply": ("F14",), "awkit hook kit-version": ("F25",)}


# Transcripts


def read_transcript(path):
    """The complete transcript records, or None for unreadable, malformed or partial input."""
    if not isinstance(path, str) or not path:
        return None
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if text and not text.endswith("\n"):
        return None  # a final record may still be in flight
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            return None
        if not isinstance(record, dict):
            return None
        records.append(record)
    return records


def _blocks(record):
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _payload(record):
    payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def _tool_events(records):
    """Only the two supported call/result envelopes, retaining transcript order."""
    for position, record in enumerate(records):
        kind, payload = record.get("type"), _payload(record)
        if kind == "assistant":
            for block in _blocks(record):
                if block.get("type") == "tool_use":
                    yield position, "call", ("claude", block.get("id")), block.get("name"), block.get("input")
        elif kind == "user":
            for block in _blocks(record):
                if block.get("type") == "tool_result":
                    yield position, "result", ("claude", block.get("tool_use_id")), "claude", block
                elif isinstance(block.get("text"), str) and "<command-name>" in block["text"] and GUIDE.search(block["text"]):
                    yield position, "call", ("claude", None), "slash_skill", block["text"]
        elif payload.get("type") in ("function_call", "custom_tool_call", "local_shell_call"):
            yield position, "call", ("codex", payload.get("call_id")), payload.get("name") or "local_shell_call", \
                payload.get("arguments", payload.get("input", payload.get("action")))
        elif payload.get("type") in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
            yield position, "result", ("codex", payload.get("call_id")), "codex", payload.get("output")


def _shell_access(command):
    """Recognize single reads and known mentions; unfamiliar candidate commands stay unknown."""
    if isinstance(command, str):
        try:
            words = shlex.split(command, comments=True, posix=False)
        except ValueError:
            return "unknown" if GUIDE.search(command) else "none"
        if not words:
            return "none"
    elif isinstance(command, list) and all(isinstance(word, str) for word in command):
        words = command
    else:
        return "unknown"
    words = [word.strip("\"'") for word in words]
    if not words:
        return "none"
    raw = command if isinstance(command, str) else " ".join(command)
    if isinstance(command, str) and GUIDE.search(raw) and re.search(r"[;|&<>`\n]", command):
        return "unknown"
    program = words[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    # A filename mentioned as an argument of these operations is not a file read.
    if program in {"echo", "write-output", "printf", "rg", "grep", "select-string", "findstr"}:
        return "none"
    if program in {"python", "python3", "python.exe", "py"} and len(words) == 3 and words[1] == "-c":
        try:
            body = ast.parse(words[2]).body
            if all(isinstance(node, ast.Expr) and (isinstance(node.value, ast.Constant)
                   or isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                   and node.value.func.id == "print" and not node.value.keywords
                   and all(isinstance(arg, ast.Constant) for arg in node.value.args)) for node in body):
                return "none"
        except (SyntaxError, ValueError):
            pass
    if not GUIDE.search(raw):
        return "none"
    if program in {"awkit", "awkit.exe"} and words[1:] == ["kit", "guide", "writing"]:
        return "read"
    if program in {"cat", "get-content"}:
        paths = words[1:]
        if program == "get-content":
            paths = [word for word in paths if word.lower() not in {"-raw", "-literalpath", "-path"}]
        if len(paths) == 1 and not paths[0].startswith("-"):
            path = paths[0].replace("\\", "/").lower()
            if path.endswith("/writing.md") or path == "writing.md" or path.endswith("/awkit-writing/skill.md"):
                return "read"
    return "unknown"


def _access_operation(name, arguments):
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    name = str(name).rsplit(".", 1)[-1].lower()
    if name == "exec":
        match = EXEC_WRAPPER.fullmatch(raw)
        if not match:
            return "unknown" if GUIDE.search(raw) else "none"
        arguments = match.group(1)
        name = "exec_command"
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return "unknown" if GUIDE.search(raw) else "none"
    if not isinstance(arguments, dict):
        return "unknown" if GUIDE.search(raw) else "none"
    if name == "skill":
        return "read" if str(arguments.get("skill", "")).rsplit(":", 1)[-1] == "awkit-writing" else \
            "unknown" if GUIDE.search(raw) else "none"
    if name == "read":
        path = str(arguments.get("file_path", "")).replace("\\", "/").lower()
        if GUIDE.search(path):
            if any(key in arguments for key in ("offset", "limit", "pages")) or path.endswith("korean-writing.md"):
                return "unknown"
            return "read" if path.endswith("/writing.md") or path == "writing.md" or path.endswith("/awkit-writing/skill.md") else "unknown"
        return "none"
    if name in {"bash", "exec_command", "shell", "shell_command", "local_shell_call"}:
        return _shell_access(arguments.get("cmd", arguments.get("command")))
    return "unknown" if GUIDE.search(raw) else "none"


def _text_content(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, dict) and item.get("type") == "text"
                                       and isinstance(item.get("text"), str) for item in value):
        return "\n".join(item["text"] for item in value)
    return None


def _access_result(provider, value):
    if provider == "claude":
        failed = value.get("is_error", False)
        return (not failed if isinstance(failed, bool) else None), _text_content(value.get("content"))
    # Current exec output separates its completion banner from the child's JSON.
    # The banner alone says nothing about the child's exit status.
    if (isinstance(value, list) and len(value) == 2
            and all(isinstance(item, dict) and item.get("type") == "input_text"
                    and isinstance(item.get("text"), str) for item in value)
            and re.fullmatch(r"Script completed\nWall time [0-9.]+ seconds\nOutput:\s*", value[0]["text"])):
        text = value[1]["text"]
    else:
        text = _text_content(value)
    try:
        result = json.loads(text) if text is not None else value
    except ValueError:
        return None, None
    if not isinstance(result, dict) or type(result.get("exit_code")) is not int:
        return None, None
    return result["exit_code"] == 0, _text_content(result.get("output"))


def _returned_guide(text):
    """Small content heuristic, not proof of comprehension or authentic provenance."""
    if not isinstance(text, str) or re.search(r"\b(?:(?:output|tokens?|characters?|lines?) (?:was |were )?truncated|truncated (?:output|tokens?|characters?|lines?))\b", text, re.I):
        return False
    headings = re.findall(r"^\s*(?:\d+\s*[→:|]\s*)?#{1,6}\s+(.+?)\s*$", text.lstrip("\ufeff"), re.M)
    normalized = {" ".join(heading.strip("#* ").lower().split()) for heading in headings}
    return {"writing guide", "before writing", "completion check"} <= normalized


def guide_access(records):
    """read: returned main-guide content; absent: supported evidence shows none; unknown: fail open."""
    if records is None:
        return "unknown"
    calls, results = {}, {}
    unknown = False
    for position, kind, identity, name, value in _tool_events(records):
        if not isinstance(identity[1], str) or not identity[1].strip():
            unknown |= kind == "call" and _access_operation(name, value) != "none"
            continue
        target = calls if kind == "call" else results
        target.setdefault(identity, []).append((position, name, value))
    for identity, entries in calls.items():
        operations = [_access_operation(name, value) for _, name, value in entries]
        if all(operation == "none" for operation in operations):
            continue
        outputs = results.get(identity, [])
        if len(entries) != 1 or len(outputs) != 1 or outputs[0][0] <= entries[0][0]:
            unknown = True
            continue
        operation = operations[0]
        if operation == "unknown":
            unknown = True
            continue
        _, provider, value = outputs[0]
        success, text = _access_result(provider, value)
        if success and _returned_guide(text):
            return "read"
        unknown |= success is not False
    return "unknown" if unknown else "absent"


def last_request(records):
    """The last message the person typed, or ""."""
    from .usage import _person_wrote
    found = ""
    for record in records:
        payload = _payload(record)
        if record.get("type") == "user" and _person_wrote(record) == "message":
            found = "\n".join(b["text"] for b in _blocks(record) if isinstance(b.get("text"), str))
        elif record.get("type") == "event_msg" and payload.get("type") == "user_message":
            found = str(payload.get("message") or "")
    return found


def last_reply(records):
    """The text of the last reply in the transcript, or ""."""
    found = ""
    for record in records:
        payload = _payload(record)
        if record.get("type") == "assistant" and not record.get("isSidechain"):
            text = "\n".join(b["text"] for b in _blocks(record) if b.get("type") == "text" and isinstance(b.get("text"), str))
            found = text or found
        elif record.get("type") == "event_msg" and payload.get("type") == "agent_message":
            found = str(payload.get("message") or "") or found
        elif payload.get("type") == "message" and payload.get("role") == "assistant":
            text = "\n".join(c.get("text", "") for c in payload.get("content") or []
                             if isinstance(c, dict) and c.get("type") == "output_text")
            found = text or found
    return found


# The reply rule


def has_heading(text):
    """Whether the text has a Markdown heading outside code blocks."""
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and HEADING.match(line):
            return True
    return False


def reply_check(payload, hangul):
    """What the writing-reply rule says about the reply that ends this turn, or None when the reply passes or
    the check cannot tell. A reply counts as a Korean document for use elsewhere when it has more than
    `hangul` Hangul syllables, and a heading or a turn that asked for a prompt or document, and the session
    has supported complete evidence of no successful guide access."""
    records = read_transcript(payload.get("transcript_path"))
    reply = payload.get("last_assistant_message")
    if not isinstance(reply, str) or not reply.strip():
        reply = last_reply(records or [])
    if len(HANGUL.findall(reply)) <= hangul:
        return None
    if records is None:
        return None  # without the transcript the guide's use cannot be judged
    if not (has_heading(reply) or DOCUMENT_REQUEST.search(last_request(records))):
        return None
    if guide_access(records) != "absent":
        return None
    from .checks import check_text
    findings = check_text(reply)
    if not findings:
        return "`awkit check writing` found no listed pattern in the reply; the guide covers more than the list."
    shown = "; ".join(f"line {f['line']} {f['pattern']} ({f['level']})" for f in findings[:12])
    more = f"; {len(findings) - 12} more" if len(findings) > 12 else ""
    return f"`awkit check writing` on the reply: {shown}{more}."


# The kit version rule


def kit_version_check(root):
    """A line when checks.toml records a kit version ([kit] version) other than the installed awkit's, else None."""
    from . import __version__
    try:
        data = tomllib.loads((Path(root) / "checks.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    kit = data.get("kit")
    recorded = kit.get("version") if isinstance(kit, dict) else None
    if not isinstance(recorded, str) or not recorded.strip() or recorded.strip() == __version__:
        return None
    return (f"checks.toml records kit {recorded.strip()} but awkit {__version__} is installed, so guides and rules may "
            "differ from what the project expects. Tell the user before relying on them.")


def main(action, hangul=500, stdin=None):
    """Run `awkit hook reply` or `awkit hook kit-version` on the event in `stdin`; returns the exit code."""
    stdin = sys.stdin if stdin is None else stdin
    try:
        payload = json.loads(stdin.read())
    except (ValueError, OSError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if action == "reply":
        found = reply_check(payload, hangul)
    else:
        from .hooks import find_root
        cwd = payload.get("cwd")
        found = kit_version_check(find_root(cwd if isinstance(cwd, str) and Path(cwd).is_dir() else Path.cwd()))
    if not found:
        return 0
    print(found)
    return 1
