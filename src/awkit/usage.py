"""Read Claude Code and Codex session logs and total the real models and tokens per thread.

The log formats are not public contracts. Claude Code parsing was checked against real
transcripts; Codex parsing follows field names recorded from real rollout files
(`turn_context`, `token_count` with `info.total_token_usage`) and should be re-checked
against a current file before relying on it.

Result format 2: a token field is an integer only when every counted record carried it.
A field that any record lacked, or carried with an invalid value, is null, and the thread's
`missing` and `invalid` maps say how many records were affected. `total` sums the known
values and `total.complete` says whether every thread was fully measured.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

FORMAT = 2
FIELDS = ("fresh_input", "cache_write", "cache_read", "output")
CLAUDE_FIELDS = {"fresh_input": "input_tokens", "cache_write": "cache_creation_input_tokens",
                 "cache_read": "cache_read_input_tokens", "output": "output_tokens"}


def _files(paths, since=None):
    for raw in paths:
        path = Path(raw).expanduser()
        candidates = sorted(path.rglob("*.jsonl")) if path.is_dir() else [path]
        for item in candidates:
            if not item.is_file():
                raise ValueError(f"Session log file not found: {item}")
            if since and datetime.fromtimestamp(item.stat().st_mtime, UTC) < since:
                continue
            yield item


def _records(path, problems=None):
    """Yield the JSON objects in a .jsonl file; count lines that do not parse.

    A final line without a newline is a record still being written and is reported as
    `partial_line`; any other unparsable line is counted under `damaged_lines`.
    """
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            complete = line.endswith("\n")
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                if problems is not None:
                    if complete:
                        problems["damaged_lines"] += 1
                    else:
                        problems["partial_line"] = True
                continue
            if isinstance(record, dict):
                yield record


def _count(value):
    """An integer token count, or None for an absent or invalid value."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _thread(provider, path, label, counted):
    return {"provider": provider, "file": str(path), "thread": label, "models": Counter(),
            "effort": None, "calls": 0, "counted": counted,
            **{field: 0 for field in FIELDS}, "missing": Counter(), "invalid": Counter()}


def _add(thread, field, raw, present):
    if not present:
        thread["missing"][field] += 1
        return
    value = _count(raw)
    if value is None:
        thread["invalid"][field] += 1
    else:
        thread[field] += value


def _finish(thread):
    """Replace a field by null when any counted record failed to supply it."""
    for field in FIELDS:
        if thread["missing"][field] or thread["invalid"][field]:
            thread[field] = None
    thread["models"] = dict(thread["models"])
    thread["missing"] = dict(thread["missing"])
    thread["invalid"] = dict(thread["invalid"])
    return thread


def _claude(path, problems):
    threads, seen = {}, set()
    for record in _records(path, problems):
        message = record.get("message")
        if record.get("type") != "assistant" or not isinstance(message, dict):
            continue
        usage, model = message.get("usage"), message.get("model")
        if not model or model == "<synthetic>":
            continue
        # One API response is written as several transcript lines that repeat the same usage.
        key = message.get("id") or record.get("requestId") or record.get("uuid")
        if key in seen:
            continue
        seen.add(key)
        if record.get("isSidechain") or record.get("agentId"):
            label = f"subagent {record.get('agentId') or path.stem}"
        else:
            label = "main"
        thread = threads.setdefault(label, _thread("claude", path, label, "responses"))
        thread["models"][model] += 1
        thread["calls"] += 1
        usage = usage if isinstance(usage, dict) else {}
        for field, key in CLAUDE_FIELDS.items():
            _add(thread, field, usage.get(key), key in usage)
        if record.get("effort"):
            thread["effort"] = record["effort"]
    return [_finish(thread) for thread in threads.values()]


def _codex(path, problems):
    thread = _thread("codex", path, "thread", "turns")
    total = None
    for record in _records(path, problems):
        kind, payload = record.get("type"), record.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        if kind == "turn_context":
            if payload.get("model"):
                thread["models"][payload["model"]] += 1
                thread["calls"] += 1
            thread["effort"] = payload.get("effort") or payload.get("reasoning_effort") or thread["effort"]
        elif kind == "token_count" or payload.get("type") == "token_count":
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
            usage = info.get("total_token_usage")
            if isinstance(usage, dict):
                total = usage  # cumulative: the last one is the thread total
    if total is None:
        if not thread["models"]:
            return []
        for field in FIELDS:
            thread["missing"][field] += 1
        return [_finish(thread)]
    has_input, has_cached = "input_tokens" in total, "cached_input_tokens" in total
    _add(thread, "cache_read", total.get("cached_input_tokens"), has_cached)
    if not has_input or not has_cached:
        # `input_tokens` includes the cached part, so the fresh part needs both values.
        thread["missing"]["fresh_input"] += 1
    else:
        fresh, cached = _count(total["input_tokens"]), _count(total["cached_input_tokens"])
        if fresh is None or cached is None or fresh < cached:
            thread["invalid"]["fresh_input"] += 1
        else:
            thread["fresh_input"] = fresh - cached
    _add(thread, "cache_write", total.get("cache_write_input_tokens"), "cache_write_input_tokens" in total)
    _add(thread, "output", total.get("output_tokens"), "output_tokens" in total)
    return [_finish(thread)]


def _provider(path):
    for count, record in enumerate(_records(path)):
        kind = record.get("type")
        if kind in ("assistant", "user") and "message" in record:
            return "claude"
        if kind in ("turn_context", "session_meta", "event_msg", "response_item", "token_count"):
            return "codex"
        if count > 50:
            break
    return None


def collect(paths, since=None):
    threads, unknown, problems = [], [], {}
    for path in _files(paths, since):
        provider = _provider(path)
        found = {"damaged_lines": 0, "partial_line": False}
        if provider == "claude":
            threads.extend(_claude(path, found))
        elif provider == "codex":
            threads.extend(_codex(path, found))
        else:
            unknown.append(str(path))
        if found["damaged_lines"] or found["partial_line"]:
            problems[str(path)] = found
    totals = {}
    for thread in threads:
        for model, calls in thread["models"].items():
            entry = totals.setdefault(model, {"threads": 0, "calls": 0})
            entry["threads"] += 1
            entry["calls"] += calls
    incomplete = [thread for thread in threads if any(thread[field] is None for field in FIELDS)]
    summary = {field: sum(thread[field] for thread in threads if thread[field] is not None)
               for field in FIELDS}
    summary["complete"] = not incomplete and not unknown and not problems
    summary["incomplete_threads"] = len(incomplete)
    return {"format": FORMAT, "threads": threads, "models": totals, "total": summary,
            "unrecognized_files": unknown, "skipped_lines": problems}


def _cell(value, width):
    return f"{value:>{width},}" if value is not None else f"{'?':>{width}}"


def render(result):
    lines = []
    header = (f"{'provider':<8} {'thread':<24} {'model':<28} {'calls':>5} {'fresh in':>11} "
              f"{'cache write':>11} {'cache read':>12} {'output':>9}")
    lines.append(header)
    for row in result["threads"]:
        models = ", ".join(f"{name}×{count}" for name, count in row["models"].items()) or "unknown"
        if row["effort"]:
            models += f" ({row['effort']})"
        thread = row["thread"] if row["thread"] != "thread" else Path(row["file"]).stem[-24:]
        lines.append(f"{row['provider']:<8} {thread[:24]:<24} {models[:28]:<28} {row['calls']:>5} "
                     f"{_cell(row['fresh_input'], 11)} {_cell(row['cache_write'], 11)} "
                     f"{_cell(row['cache_read'], 12)} {_cell(row['output'], 9)}")
    total = result["total"]
    label = "total" if total["complete"] else "known"
    lines.append(f"{label:<8} {'':<24} {'':<28} {'':>5} {total['fresh_input']:>11,} {total['cache_write']:>11,} "
                 f"{total['cache_read']:>12,} {total['output']:>9,}")
    if total["incomplete_threads"]:
        lines.append(f"{total['incomplete_threads']} thread(s) have unmeasured fields, shown as ?; "
                     "the sums above cover known values only")
    if result["skipped_lines"]:
        damaged = sum(item["damaged_lines"] for item in result["skipped_lines"].values())
        partial = sum(1 for item in result["skipped_lines"].values() if item["partial_line"])
        lines.append(f"skipped {damaged} damaged line(s) and {partial} partial final line(s)")
    if result["unrecognized_files"]:
        lines.append(f"skipped {len(result['unrecognized_files'])} file(s) of unknown format")
    return "\n".join(lines)
