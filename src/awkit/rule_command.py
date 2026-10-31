"""Versioned results for explicitly opted-in bundled hook commands.

The hook runner's PREVENTS declaration covers this transport. Legacy CLI and
custom command semantics are unchanged; only this adapter distinguishes errors.
"""

import contextlib
import io
import json
import sys

PROTOCOL = "awkit-v1"
MESSAGE_LIMIT = 1000
ACTIONS = ("check commit --hook", "check writing", "check done --hook", "hook reply", "hook kit-version")


def _dispatch(args, parser, payload, *, bash_paths=None):
    from . import cli, hook_cli

    if args.group == "check" and args.action == "writing":
        return cli._run_check(args)
    if args.group == "check" and args.action in ("commit", "done") and args.hook:
        if args.action == "commit":
            data = payload.get("tool_input")
            if not isinstance(data, dict) or not isinstance(data.get("command"), str):
                raise ValueError("commit hook input needs tool_input.command")
            from .hooks import check_commit_command

            problems = check_commit_command(payload, strict=True, bash_paths=bash_paths)
            for problem in problems:
                print(problem, file=sys.stderr)
            return 1 if problems else 0
        if payload.get("hook_event_name") not in ("SessionStart", "Stop", "SubagentStop"):
            raise ValueError("done hook input needs its event name")
        return cli._run_check(args)
    if args.group == "hook" and args.action in ("reply", "kit-version"):
        return hook_cli.run(args, parser)
    raise ValueError("unsupported bundled action")


def execute(argv, raw):
    """One envelope; pass includes intentional no-op results of existing checks."""
    captured = io.StringIO()
    original_stdin = sys.stdin
    try:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("hook input must be a JSON object")
            from .hook_cli import EVENTS

            if payload.get("hook_event_name") not in EVENTS:
                raise ValueError("hook input needs a supported event name")
            for field in ("cwd", "session_id", "last_assistant_message"):
                if field in payload and not isinstance(payload[field], str):
                    raise ValueError(f"hook {field} must be text")
            if "stop_hook_active" in payload and type(payload["stop_hook_active"]) is not bool:
                raise ValueError("stop_hook_active must be boolean")
            if payload.get("transcript_path") is not None and not isinstance(payload["transcript_path"], str):
                raise ValueError("transcript_path must be text or null")
            from .cli import _parser

            bash_paths = None
            if any(part.split("=", 1)[0] == "--bash-paths" for part in argv):
                from .commit_paths import ARGUMENT, MODE
                if argv != ["check", "commit", "--hook", ARGUMENT]:
                    raise ValueError("unsupported or conflicting bundled commit path selector")
                argv, bash_paths = argv[:3], MODE
            parser = _parser()
            args = parser.parse_args(argv)
            sys.stdin = io.StringIO(raw)
            code = _dispatch(args, parser, payload, bash_paths=bash_paths)
            finding_codes = (0, 1, 2) if args.group == "check" and args.action == "done" else (0, 1)
            if type(code) is not int or code not in finding_codes:
                raise ValueError("unsupported bundled action result")
        status = "pass" if code == 0 else "finding"
        message = captured.getvalue().strip()
    except (Exception, SystemExit) as exc:
        status = "error"
        message = f"{type(exc).__name__}: {exc}"
        if captured.getvalue().strip():
            message += "\n" + captured.getvalue().strip()
    finally:
        sys.stdin = original_stdin
    return {"protocol": PROTOCOL, "status": status, "message": message[:MESSAGE_LIMIT]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--capabilities"]:
        print(json.dumps({"protocol": PROTOCOL, "actions": ACTIONS}))
        return 0
    try:
        raw = sys.stdin.read()
    except (OSError, UnicodeError) as exc:
        result = {"protocol": PROTOCOL, "status": "error", "message": f"{type(exc).__name__}: unreadable hook input"}
    else:
        result = execute(argv, raw)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
