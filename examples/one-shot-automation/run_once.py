"""Explicit, sequential mock observations; no scheduler or crash-safety guarantee."""

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path, PureWindowsPath

PREVENTS = {"one-shot-automation/run_once.py": ("F27",)}
CASES = ("configured", "no-trigger", "fired", "failed")


def safe(root, name):
    relative = Path(name)
    if (not name or "\\" in name or relative.is_absolute() or PureWindowsPath(name).drive
            or any(part in {"..", "."} for part in name.split("/"))):
        raise ValueError("path must stay inside the job")
    current = root
    if current.is_symlink():
        raise ValueError("symlink destination")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink destination")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError("escaping destination")
    return current


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def inputs(root):
    task = tomllib.loads(safe(root, "task.toml").read_text(encoding="utf-8"))
    for key in ("signal", "effect", "failure"):
        safe(root, task[key])
    if (task["signal"] != "signal.json" or task["effect"] != "delivery/effect.txt"
            or task["failure"] != "failure.json" or task["event_id"] != "DEMO-ONE"
            or task["effect_line"] != "mock effect DEMO-ONE\n"
            or type(task["attempt_limit"]) is not int or task["attempt_limit"] != 1
            or task["stop_after"] != "success-or-failure" or task["notification"] != "local-record"):
        raise ValueError("unsupported mock task")
    if read_json(safe(root, "input/signal.json")) != {"event_id": task["event_id"]}:
        raise ValueError("invalid fixture signal")
    identities = {name: digest(safe(root, name))
                  for name in ("task.toml", "input/signal.json", "expected.json")}
    return task, identities


def job_path(root, case):
    if case not in CASES:
        raise ValueError("unknown case")
    return safe(root, f"output/{case}")


def prepare(root, case):
    task, identities = inputs(root)
    job = job_path(root, case)
    if job.exists():
        raise ValueError("job root already exists; preserve it")
    job.parent.mkdir(exist_ok=True)
    job.mkdir()
    write_json(safe(job, "configured.json"), {
        "case": case, "task": task, "inputs": identities, "observed": False, "attempts": 0,
    })
    write_json(safe(job, "state.json"), {"status": "configured", "attempts": 0, "terminal": False})
    delivery = safe(job, "delivery")
    if case == "failed":
        delivery.write_bytes(b"blocked\n")
    else:
        delivery.mkdir()
    return 0


def load_job(root, case):
    task, identities = inputs(root)
    job = job_path(root, case)
    configured = read_json(safe(job, "configured.json"))
    if configured != {"case": case, "task": task, "inputs": identities, "observed": False, "attempts": 0}:
        raise ValueError("configuration changed or incomplete")
    state = read_json(safe(job, "state.json"))
    valid = (
        {"status": "configured", "attempts": 0, "terminal": False},
        {"status": "no-trigger", "attempts": 0, "terminal": False},
        {"status": "fired", "attempts": 1, "terminal": True},
        {"status": "failed", "attempts": 1, "terminal": True},
    )
    if (state not in valid or type(state.get("attempts")) is not int
            or type(state.get("terminal")) is not bool):
        raise ValueError("invalid or uncertain state; no retry")
    history = safe(job, "observations.jsonl")
    observations = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()] \
        if history.exists() else []
    outcomes = [row["outcome"] for row in observations]
    status = state["status"]
    if status == "configured" and observations:
        raise ValueError("state contradicts observations")
    if status == "no-trigger" and (not outcomes or set(outcomes) != {"no-trigger"}):
        raise ValueError("state contradicts observations")
    if status in {"fired", "failed"} and (
            not outcomes or outcomes[0] != status or any(value != "skipped-stopped" for value in outcomes[1:])):
        raise ValueError("terminal state lacks matching history")
    return task, job, state, observations


def stage_event(root, case):
    if case not in {"fired", "failed"}:
        raise ValueError("this case has no staged event")
    task, job, state, observations = load_job(root, case)
    if state["status"] != "configured" or observations:
        raise ValueError("event must precede observations")
    with safe(job, task["signal"]).open("xb") as handle:
        handle.write(safe(root, "input/signal.json").read_bytes())
    return 0


def observe(root, case):
    task, job, state, observations = load_job(root, case)
    signal = safe(job, task["signal"])
    effect = safe(job, task["effect"])
    failure = safe(job, task["failure"])
    effect_record = safe(job, "effect.json")
    present = signal.is_file()
    if signal.exists() and (not present or signal.read_bytes() != safe(root, "input/signal.json").read_bytes()):
        raise ValueError("unexpected signal")
    signal_hash = digest(signal) if present else None
    before = effect.read_bytes() if effect.is_file() else b""
    if state["terminal"]:
        outcome, code = "skipped-stopped", 0
    elif effect.exists() or effect_record.exists() or failure.exists():
        raise ValueError("unsettled action evidence; no retry")
    elif not present:
        state = {"status": "no-trigger", "attempts": 0, "terminal": False}
        outcome, code = "no-trigger", 0
    else:
        # An incomplete attempt marker is rejected on a later invocation. This is not crash safety.
        write_json(safe(job, "state.json"), {"status": "attempting", "attempts": 1, "terminal": True})
        try:
            with effect.open("ab") as handle:
                handle.write(task["effect_line"].encode("utf-8"))
        except OSError as exc:
            write_json(failure, {"event_id": task["event_id"], "code": "effect-write-failed",
                                 "exception": type(exc).__name__, "notification": "local-record"})
            outcome, code = "failed", 1
        else:
            write_json(effect_record, {"event_id": task["event_id"], "path": task["effect"],
                                       "size": effect.stat().st_size, "sha256": digest(effect)})
            outcome, code = "fired", 0
        state = {"status": outcome, "attempts": 1, "terminal": True}
    after = effect.read_bytes() if effect.is_file() else b""
    row = {"number": len(observations) + 1, "outcome": outcome, "signal_sha256": signal_hash,
           "before_bytes": len(before), "after_bytes": len(after), "attempts": state["attempts"]}
    with safe(job, "observations.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row) + "\n")
    write_json(safe(job, "state.json"), state)
    return code


def main(argv=None, root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "stage-event", "observe"))
    parser.add_argument("case", choices=CASES)
    args = parser.parse_args(argv)
    root = Path(root) if root is not None else Path(__file__).resolve().parent
    actions = {"prepare": prepare, "stage-event": stage_event, "observe": observe}
    try:
        code = actions[args.action](root, args.case)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"invalid or uncertain job ({type(exc).__name__}); evidence preserved", file=sys.stderr)
        return 2
    print(f"{args.action} {args.case}: exit {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
