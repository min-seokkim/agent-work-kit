"""Commands behind the default rules that read the session instead of one tool call: `awkit hook reply` and
`awkit hook kit-version`. Each reads the hook event on stdin, prints what the rule should say and exits 1, or
prints nothing and exits 0. When it cannot tell, it exits 0: a rule that fires wrongly costs more than one
that misses.

Writing is the one situation that can end in the chat with no tool call, so no rule that reads tool calls
sees it. `reply` reads the result instead: the final reply, from the event's `last_assistant_message` (Claude
Code and Codex both send it on Stop) or the session's transcript, and the transcript for the turn's request
and for any sign that the writing guide was read. Transcripts are JSON lines: Claude Code writes `user` and
`assistant` records whose `message.content` holds `text` and `tool_use` blocks; Codex writes `response_item`
records (`message`, `function_call`, `custom_tool_call`, `local_shell_call`) and `event_msg` records
(`user_message`, `agent_message`). Both are only read.
"""

import json
import re
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
# A sign in a tool call that the writing guide was read: the skill, the guide files, or a copy of them.
GUIDE = re.compile(r"(?:korean-)?writing\.md|awkit-writing|\"skill\":\s*\"[^\"]*writing")

# The failure catalogue entries (kit/failures.md) these commands guard: Korean written for others without the
# guide that the agent itself was given (F14), and guidance followed for another version of the kit (F25).
PREVENTS = {"awkit hook reply": ("F14",), "awkit hook kit-version": ("F25",)}


# Transcripts


def read_transcript(path):
    """The records of a transcript, or None when there is none or it cannot be read."""
    if not isinstance(path, str) or not path:
        return None
    try:
        lines = Path(path).expanduser().read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    records = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
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


def tool_calls(records):
    """Each tool call in the transcript as text: its name and input. Also a slash command the person ran, such as
    /awkit-writing, which loads the skill without a tool call."""
    for record in records:
        kind, payload = record.get("type"), _payload(record)
        if kind == "assistant":
            for block in _blocks(record):
                if block.get("type") == "tool_use":
                    yield json.dumps({"name": block.get("name"), "input": block.get("input")}, ensure_ascii=False)
        elif kind == "user":
            for block in _blocks(record):
                text = block.get("text")
                if isinstance(text, str) and text.lstrip().startswith("<command-name>"):
                    yield text
        elif payload.get("type") in ("function_call", "custom_tool_call", "local_shell_call"):
            yield json.dumps({key: payload.get(key) for key in ("name", "arguments", "input", "action")},
                             ensure_ascii=False)


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
    shows no sign of the writing guide."""
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
    if any(GUIDE.search(call) for call in tool_calls(records)):
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
