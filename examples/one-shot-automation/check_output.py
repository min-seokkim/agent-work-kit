"""Read mock-job evidence against fixed expectations; never repair it."""

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path

PREVENTS = {"one-shot-automation/check_output.py": ("F1", "F27")}
CASES = ("configured", "no-trigger", "fired", "failed")


def read_path(root, name):
    current = root
    if root.is_symlink():
        raise ValueError("symlink evidence root")
    for part in Path(name).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink evidence")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError("escaping evidence")
    return current


def read_json(root, name):
    return json.loads(read_path(root, name).read_text(encoding="utf-8"))


def equal(got, expected, label):
    if got != expected or type(got) is not type(expected):
        raise ValueError(f"{label} differs from fixed expectation")


def check(root, case):
    expected = read_json(root, "expected.json")
    want = expected["cases"][case]
    task = tomllib.loads(read_path(root, "task.toml").read_text(encoding="utf-8"))
    equal(task["event_id"], expected["event"]["event_id"], "task event")
    equal(task["effect_line"], expected["effect"], "task effect")
    equal(task["signal"], "signal.json", "trigger path")
    equal(task["effect"], "delivery/effect.txt", "effect path")
    equal(task["failure"], "failure.json", "failure path")
    equal(task["attempt_limit"], 1, "attempt limit")
    equal(task["stop_after"], "success-or-failure", "stopping condition")
    equal(task["notification"], "local-record", "failure notification")
    signal_bytes = read_path(root, "input/signal.json").read_bytes()
    equal(json.loads(signal_bytes), expected["event"], "fixture event")
    identities = {name: hashlib.sha256(read_path(root, name).read_bytes()).hexdigest()
                  for name in ("task.toml", "input/signal.json", "expected.json")}
    relative = f"output/{case}"
    job = read_path(root, relative)
    if not job.is_dir():
        raise ValueError("missing job")
    paths = list(job.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("symlink evidence")
    files = {path.relative_to(job).as_posix() for path in paths if path.is_file()}
    required = {"configured.json", "state.json"}
    if case != "configured":
        required.add("observations.jsonl")
    if case in {"fired", "failed"}:
        required.add("signal.json")
    if case == "fired":
        required.update({"delivery/effect.txt", "effect.json"})
    if case == "failed":
        required.update({"failure.json", "delivery"})
    equal(files, required, "job file inventory")
    configured = read_json(root, f"{relative}/configured.json")
    equal(configured, {"case": case, "task": task, "inputs": identities, "observed": False, "attempts": 0},
          "configured record")
    equal(configured["attempts"], 0, "configured attempts")
    equal(configured["observed"], False, "configured observation")
    state = read_json(root, f"{relative}/state.json")
    equal(set(state), {"status", "attempts", "terminal"}, "state fields")
    for key in state:
        equal(state[key], want[key], f"state {key}")
    history = read_path(root, f"{relative}/observations.jsonl")
    rows = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()] \
        if history.exists() else []
    equal(len(rows), len(want["observations"]), "observation count")
    effect_bytes = expected["effect"].encode("utf-8")
    signal_hash = hashlib.sha256(signal_bytes).hexdigest() if case in {"fired", "failed"} else None
    for index, (row, outcome) in enumerate(zip(rows, want["observations"], strict=True)):
        before = len(effect_bytes) if case == "fired" and index else 0
        after = len(effect_bytes) if case == "fired" else 0
        expected_row = {"number": index + 1, "outcome": outcome, "signal_sha256": signal_hash,
                        "before_bytes": before, "after_bytes": after, "attempts": want["attempts"]}
        equal(set(row), set(expected_row), "observation fields")
        for key, value in expected_row.items():
            equal(row[key], value, f"observation {index + 1} {key}")
    if signal_hash:
        equal(read_path(root, f"{relative}/signal.json").read_bytes(), signal_bytes, "staged signal bytes")
    if case == "fired":
        equal(read_path(root, f"{relative}/delivery/effect.txt").read_bytes(), effect_bytes, "effect bytes")
        effect = read_json(root, f"{relative}/effect.json")
        equal(effect, {"event_id": expected["event"]["event_id"], "path": "delivery/effect.txt",
                       "size": len(effect_bytes), "sha256": hashlib.sha256(effect_bytes).hexdigest()},
              "effect record")
    if case == "failed":
        equal(read_path(root, f"{relative}/delivery").read_bytes(), expected["blocker"].encode("utf-8"),
              "failure blocker")
        failure = read_json(root, f"{relative}/failure.json")
        equal(set(failure), {"event_id", "code", "exception", "notification"}, "failure fields")
        equal(failure["event_id"], expected["event"]["event_id"], "failure event")
        equal(failure["code"], "effect-write-failed", "failure code")
        equal(failure["notification"], "local-record", "failure notification")
        if failure["exception"] not in {"NotADirectoryError", "FileNotFoundError", "PermissionError", "OSError"}:
            raise ValueError("unexpected write failure class")
    return {"case": case, "status": state["status"], "attempts": state["attempts"],
            "observations": len(rows), "evidence_matches": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=CASES)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args(argv)
    try:
        result = check(args.root, args.case)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"evidence mismatch ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
