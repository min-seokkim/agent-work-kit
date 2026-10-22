"""Read Claude Code and Codex session logs and total the real models and tokens per thread.

The log formats are not public contracts. Claude Code parsing was checked against real
transcripts; Codex parsing follows field names recorded from real rollout files
(`turn_context`, `token_count` with `info.total_token_usage`) and should be re-checked
against a current file before relying on it.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ("fresh_input", "cache_write", "cache_read", "output")


def _files(paths, since=None):
    for raw in paths:
        path = Path(raw).expanduser()
        candidates = sorted(path.rglob("*.jsonl")) if path.is_dir() else [path]
        for item in candidates:
            if not item.is_file():
                raise ValueError(f"Session log file not found: {item}")
            if since and datetime.fromtimestamp(item.stat().st_mtime, timezone.utc) < since:
                continue
            yield item


def _records(path):
    with path.open(encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # a log that is still being written can end with a partial line
            if isinstance(record, dict):
                yield record


def _thread(provider, path, label):
    return {"provider": provider, "file": str(path), "thread": label, "models": Counter(),
            "effort": None, "calls": 0, **{field: 0 for field in FIELDS}}


def _claude(path):
    threads, seen = {}, set()
    for record in _records(path):
        message = record.get("message")
        if record.get("type") != "assistant" or not isinstance(message, dict):
            continue
        usage, model = message.get("usage"), message.get("model")
        if not isinstance(usage, dict) or not model or model == "<synthetic>":
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
        thread = threads.setdefault(label, _thread("claude", path, label))
        thread["models"][model] += 1
        thread["calls"] += 1
        thread["fresh_input"] += int(usage.get("input_tokens") or 0)
        thread["cache_write"] += int(usage.get("cache_creation_input_tokens") or 0)
        thread["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)
        thread["output"] += int(usage.get("output_tokens") or 0)
        if record.get("effort"):
            thread["effort"] = record["effort"]
    return list(threads.values())


def _codex(path):
    thread = _thread("codex", path, "thread")
    total = None
    for record in _records(path):
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
    if total:
        cached = int(total.get("cached_input_tokens") or 0)
        thread["fresh_input"] = int(total.get("input_tokens") or 0) - cached
        thread["cache_read"] = cached
        thread["cache_write"] = int(total.get("cache_write_input_tokens") or 0)
        thread["output"] = int(total.get("output_tokens") or 0)
    return [thread] if thread["models"] or total else []


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
    threads, unknown = [], []
    for path in _files(paths, since):
        provider = _provider(path)
        if provider == "claude":
            threads.extend(_claude(path))
        elif provider == "codex":
            threads.extend(_codex(path))
        else:
            unknown.append(str(path))
    totals = {}
    for thread in threads:
        for model, calls in thread["models"].items():
            entry = totals.setdefault(model, {"threads": 0, "calls": 0})
            entry["threads"] += 1
            entry["calls"] += calls
    summary = {field: sum(thread[field] for thread in threads) for field in FIELDS}
    rows = [{**thread, "models": dict(thread["models"])} for thread in threads]
    return {"threads": rows, "models": totals, "total": summary, "unrecognized_files": unknown}


def render(result):
    lines = []
    header = f"{'공급자':<6} {'스레드':<24} {'모델':<28} {'호출':>5} {'새 입력':>11} {'cache 쓰기':>11} {'cache 읽기':>12} {'출력':>9}"
    lines.append(header)
    for row in result["threads"]:
        models = ", ".join(f"{name}×{count}" for name, count in row["models"].items()) or "미확인"
        if row["effort"]:
            models += f" ({row['effort']})"
        thread = row["thread"] if row["thread"] != "thread" else Path(row["file"]).stem[-24:]
        lines.append(f"{row['provider']:<6} {thread[:24]:<24} {models[:28]:<28} {row['calls']:>5} "
                     f"{row['fresh_input']:>11,} {row['cache_write']:>11,} {row['cache_read']:>12,} {row['output']:>9,}")
    total = result["total"]
    lines.append(f"{'합계':<6} {'':<24} {'':<28} {'':>5} {total['fresh_input']:>11,} {total['cache_write']:>11,} "
                 f"{total['cache_read']:>12,} {total['output']:>9,}")
    if result["unrecognized_files"]:
        lines.append(f"형식을 알 수 없어 건너뛴 파일 {len(result['unrecognized_files'])}개")
    return "\n".join(lines)
