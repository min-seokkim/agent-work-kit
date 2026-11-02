"""The check, doctor and usage commands."""

import json
import sys
from datetime import UTC
from pathlib import Path

from .cli_common import REFERENCE


def add(groups):
    checks = groups.add_parser("check", help="checks for hooks and CI: commit identity, writing patterns, done reports",
                               epilog=REFERENCE)
    check_commands = checks.add_subparsers(dest="action", required=True, metavar="ACTION")
    identity = check_commands.add_parser("commit", help="compare a commit's author and trailers with the repository's "
                                         "recent commits; exit 0 consistent, 1 not")
    identity.add_argument("--repo", type=Path, default=Path("."), help="folder in the Git repository (default: .)")
    source = identity.add_mutually_exclusive_group(required=True)
    source.add_argument("--message", type=Path, help="commit message file, as a commit-msg hook receives it; the author "
                        "is the one Git would use now")
    source.add_argument("--rev", help="an existing commit to check against the commits before it")
    source.add_argument("--hook", action="store_true", help="read a Claude Code or Codex hook event on stdin and check "
                        "each `git commit` in its shell command before it runs")
    identity.add_argument("--history", type=int, default=50, help="number of earlier commits to compare with (default: 50)")
    writing = check_commands.add_parser("writing", help="find writing patterns in Markdown files; exit 1 when a pattern "
                                        "that is wrong on one sighting is found, warnings do not fail")
    writing.add_argument("paths", nargs="*", type=Path, help="Markdown files, or folders searched recursively for *.md")
    writing.add_argument("--changed", action="store_true", help="also the Markdown files added, modified or untracked "
                         "in the repository of the current folder; without paths, only those (nothing changed: exit 0)")
    writing.add_argument("--json", action="store_true", help="print the findings as JSON")
    comparison = check_commands.add_parser("writing-compare", help="compare complete-file writing findings at two "
                                           "explicit Git revisions; candidate errors still exit 1, invalid evidence 2")
    comparison.add_argument("baseline", help="explicit baseline Git revision; never advanced automatically")
    comparison.add_argument("candidate", help="explicit candidate Git revision")
    comparison.add_argument("paths", nargs="+", help="repository-relative regular Markdown file paths")
    comparison.add_argument("--repo", type=Path, default=Path("."), help="folder in the Git repository (default: .)")
    comparison.add_argument("--json", action="store_true", help="print the separate format-1 comparison report")
    finished = check_commands.add_parser("done", help="check that the files changed in this session have a passing "
                                         "`review check` of their current state; exit 0 yes, 1 no")
    finished.add_argument("--repo", type=Path, default=Path("."), help="folder in the Git repository (default: .)")
    finished.add_argument("--runs-root", type=Path, help="run folder root used with `review check`, besides .awkit/reviews and the system temp folder older versions used")
    finished.add_argument("--session", help="session ID the starting point is recorded under (default: one shared point)")
    finished.add_argument("--mark", action="store_true", help="record the current state as the session's starting point")
    finished.add_argument("--hook", action="store_true", help="run as a Claude Code hook: read the hook input from stdin, "
                          "mark on SessionStart, exit 2 with the reason on Stop, and let a second stop in a turn pass")


def add_doctor(groups):
    doctor = groups.add_parser("doctor", help="check Python, Git, the Git identity and the project folder, and say how "
                               "to fix each missing item; exit 0 no required tools missing, 1 something required is missing",
                               epilog=REFERENCE)
    doctor.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder to look at (default: .)")
    doctor.add_argument("--json", action="store_true", help="print the findings as JSON")


def add_usage(groups):
    usage = groups.add_parser("usage", help="total models, tokens, user messages and minutes from session logs",
                              epilog=REFERENCE)
    usage.add_argument("paths", nargs="+", type=Path, help="Claude Code or Codex .jsonl files, or folders searched recursively")
    usage.add_argument("--since", metavar="YYYY-MM-DD", help="read only files modified on or after this date (UTC)")
    usage.add_argument("--json", action="store_true", help="print JSON (format 3; token and human-input coverage are separate)")


def _run_check(args):
    from . import checks
    if args.action == "commit" and args.hook:
        from .hooks import check_commit_command
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            return 0
        problems = check_commit_command(payload if isinstance(payload, dict) else {})
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    if args.action == "commit":
        message = args.message.read_text(encoding="utf-8", errors="replace") if args.message else None
        report = checks.commit_identity(args.repo, message, args.rev, args.history)
        for problem in report["problems"]:
            print(problem, file=sys.stderr)
        return 0 if report["ok"] else 1
    if args.action == "writing":
        paths = list(args.paths)
        if args.changed:
            changed = checks.changed_markdown(Path.cwd())
            if changed is None and not paths:
                print("not in a Git repository; nothing checked", file=sys.stderr)
                return 0
            paths.extend(changed or [])
            if not paths:
                return 0
        elif not paths:
            print("awkit check writing: name Markdown files or folders, or pass --changed", file=sys.stderr)
            return 2
        report = checks.check_writing(paths)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else checks.render_writing(report))
        return 0 if report["ok"] else 1
    if args.action == "writing-compare":
        from .writing_compare import compare_writing, render_comparison
        report = compare_writing(args.repo, args.baseline, args.candidate, args.paths)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_comparison(report))
        return report["exit_code"]
    session, event, repeated, source = args.session, None, False, None
    if args.hook:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            payload = {}
        session = session or payload.get("session_id")
        event = payload.get("hook_event_name")
        repeated = bool(payload.get("stop_hook_active"))
        source = payload.get("source")
        if repeated:
            return 0
    # A resumed or compacted session keeps its starting point; a cleared one starts again.
    report = checks.done(args.repo, args.runs_root, session, mark=args.mark or event == "SessionStart",
                         replace=args.mark or source in (None, "startup", "clear"))
    message = checks.render_done(report)
    if args.hook:
        if not report["ok"]:
            print(message, file=sys.stderr)
            return 2
        return 0
    print(message, file=sys.stdout if report["ok"] else sys.stderr)
    return 0 if report["ok"] else 1


def run_check(args, parser):
    return _run_check(args)


def run_doctor(args, parser):
    from .doctor import diagnose
    from .doctor import render as render_doctor
    findings = diagnose(args.dir)
    print(json.dumps(findings, ensure_ascii=False, indent=2) if args.json else render_doctor(findings))
    return 1 if any(f["status"] == "missing" for f in findings) else 0


def run_usage(args, parser):
    from datetime import datetime

    from .usage import collect
    from .usage import render as render_usage
    since = None
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=UTC)
    result = collect(args.paths, since)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_usage(result))
    return 0
