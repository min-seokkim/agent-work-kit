"""Command-line entry points."""

import argparse
import json
import sqlite3
import sys
from datetime import UTC
from pathlib import Path

from . import __version__
from .channel import KINDS, ROLES, Channel, render
from .extras.pipeline import Pipeline, StepError
from .extras.publish import Publisher
from .kit_install import EXAMPLES, install, install_example, install_roles, install_skills
from .review import accept, compare, snapshot, track
from .review import check as run_checks
from .review import verify as verify_run

REFERENCE = ("Formats, rules and exit codes are in agent-work-kit/reference.md "
             "(kit/reference.md in the awkit repository).")


def _parser():
    parser = argparse.ArgumentParser(
        prog="awkit", epilog=REFERENCE,
        description="Agent Work Kit: working instructions for coding agents and tools that freeze changes, "
                    "check them in isolation and retain the evidence.")
    parser.add_argument("--version", action="version", version=f"awkit {__version__}")
    groups = parser.add_subparsers(dest="group", required=True, metavar="COMMAND")

    kit = groups.add_parser("kit", help="add the kit to a project, create examples, scan a project, write role files, "
                            "skills and hooks",
                            epilog=REFERENCE)
    kit_commands = kit.add_subparsers(dest="action", required=True, metavar="ACTION")
    init = kit_commands.add_parser("init", help="create the kit folder; an existing folder is never touched (exit 2)")
    init.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder that receives the kit (default: .)")
    init.add_argument("--name", default="agent-work-kit", help="name of the folder to create (default: agent-work-kit)")
    init.add_argument("--no-git", action="store_true",
                      help="only copy; by default the new folder is committed, creating the repository if needed")
    example = kit_commands.add_parser("example", help="create a runnable example with one deliberate defect")
    example.add_argument("kind", choices=EXAMPLES, help="documents: Korean documents with a broken link; "
                         "data: a CSV with a wrong column name; analysis: sensor readings with a wrong assumption")
    example.add_argument("dir", type=Path, help="new folder to create; must not exist")
    example.add_argument("--no-git", action="store_true",
                         help="only copy; by default the new folder is committed, creating the repository if needed")
    scan = kit_commands.add_parser("scan", help="report manifests, check commands, CI steps, docs and Git state as JSON")
    scan.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder to look at (default: .)")
    scan.add_argument("--checks", action="store_true", help="print only the suggested checks.toml")
    roles = kit_commands.add_parser("roles", help="write Claude Code or Codex subagent role files; existing files are kept")
    roles.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder that receives the role files (default: .)")
    roles.add_argument("--provider", choices=("claude", "codex"), required=True,
                       help="claude writes .claude/agents/*.md, codex writes .codex/agents/*.toml")
    roles.add_argument("--model", action="append", metavar="TIER=MODEL[:EFFORT]",
                       help="model for a tier (efficient, standard, judge, top); EFFORT is Codex only; repeatable")
    skills = kit_commands.add_parser("skills", help="write one skill per situation guide for Claude Code or Codex; "
                                     "existing skill files are kept")
    skills.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder (default: .)")
    skills.add_argument("--provider", choices=("claude", "codex"), required=True,
                        help="claude writes .claude/skills/awkit-*/SKILL.md, codex writes .agents/skills/awkit-*/SKILL.md")
    skills.add_argument("--kit", type=Path, help="the kit folder inside the project (default: DIR/agent-work-kit)")
    hooks = kit_commands.add_parser("hooks", help="install the commit identity hook for Git and the done check for "
                                    "Claude Code; existing hooks are kept")
    hooks.add_argument("dir", nargs="?", type=Path, default=Path("."), help="folder in the Git repository (default: .)")
    hooks.add_argument("--git", action="store_true", help="write the repository's commit-msg hook (`awkit check commit`)")
    hooks.add_argument("--claude", action="store_true",
                       help="add SessionStart and Stop hooks running `awkit check done` to .claude/settings.local.json")

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
    identity.add_argument("--history", type=int, default=50, help="number of earlier commits to compare with (default: 50)")
    writing = check_commands.add_parser("writing", help="find writing patterns in Markdown files; exit 1 when a pattern "
                                        "that is wrong on one sighting is found, warnings do not fail")
    writing.add_argument("paths", nargs="+", type=Path, help="Markdown files, or folders searched recursively for *.md")
    writing.add_argument("--json", action="store_true", help="print the findings as JSON")
    finished = check_commands.add_parser("done", help="check that the files changed in this session have a passing "
                                         "`review check` of their current state; exit 0 yes, 1 no")
    finished.add_argument("--repo", type=Path, default=Path("."), help="folder in the Git repository (default: .)")
    finished.add_argument("--runs-root", type=Path, help="run folder root used with `review check`, besides "
                          ".awkit/reviews and the system temp default")
    finished.add_argument("--session", help="session ID the starting point is recorded under (default: one shared point)")
    finished.add_argument("--mark", action="store_true", help="record the current state as the session's starting point")
    finished.add_argument("--hook", action="store_true", help="run as a Claude Code hook: read the hook input from stdin, "
                          "mark on SessionStart, exit 2 with the reason on Stop, and let a second stop in a turn pass")

    usage = groups.add_parser("usage", help="total models, tokens, user messages and minutes from session logs",
                              epilog=REFERENCE)
    usage.add_argument("paths", nargs="+", type=Path, help="Claude Code or Codex .jsonl files, or folders searched recursively")
    usage.add_argument("--since", metavar="YYYY-MM-DD", help="read only files modified on or after this date (UTC)")
    usage.add_argument("--json", action="store_true", help="print the result as JSON (format 2)")

    channel = groups.add_parser("channel", help="message log for a main session and a reviewer session",
                                epilog=REFERENCE)
    channel.add_argument("--db", type=Path, default=Path(".awkit/channel.sqlite3"),
                         help="SQLite file both sessions use (default: .awkit/channel.sqlite3)")
    commands = channel.add_subparsers(dest="action", required=True, metavar="ACTION")
    post = commands.add_parser("post", help="record a message and print its ID; the body comes from --body, --body-file or stdin")
    post.add_argument("sender", choices=ROLES, help="who sends")
    post.add_argument("receiver", choices=ROLES, help="who receives; must differ from the sender")
    post.add_argument("kind", choices=KINDS, help="request kinds: review, scout, test, draft, question, final; "
                      "notice; re and rebut answer --reply-to; close (main only) ends the channel")
    post.add_argument("--reply-to", metavar="ID", help="message ID that a re or rebut answers, sent by the other side")
    post.add_argument("--snap", metavar="ID", help="snapshot or commit the message is about (7-64 hex characters)")
    body = post.add_mutually_exclusive_group()
    body.add_argument("--body", help="body text")
    body.add_argument("--body-file", type=Path, help="UTF-8 file with the body")
    wait = commands.add_parser("wait", help="wait for messages; exit 0 found, 1 timeout, 3 channel closed (reviewer)")
    wait.add_argument("role", choices=ROLES, help="the role that is waiting")
    wait.add_argument("mode", choices=("request", "new", "reply"),
                      help="request: unanswered requests and rebuttals; new: messages after the read position; "
                           "reply: answers to the given ID")
    wait.add_argument("target", nargs="?", metavar="ID", help="message ID, for reply mode only")
    wait.add_argument("--max", type=float, default=120, metavar="SECONDS", help="how long to wait; 0 checks once (default: 120)")
    wait.add_argument("--json", action="store_true", help="print messages as JSON")
    export = commands.add_parser("export", help="print the whole channel; does not move read positions")
    export.add_argument("--json", action="store_true", help="print messages as JSON")

    pipeline = groups.add_parser("pipeline", help="extra for web projects: run delivery commands and verify the live release",
                                 epilog=REFERENCE)
    pipeline.add_argument("--config", type=Path, required=True, help="pipeline TOML (schema_version = 1)")
    pipeline.add_argument("action", choices=("plan", "deploy", "rollback", "status", "reconcile", "history"),
                          help="plan: show phases without running anything; deploy RELEASE; rollback: one healthy release back; "
                               "status: verify what runs now; reconcile: record the real state after an uncertain run; "
                               "history: healthy releases")
    pipeline.add_argument("release", nargs="?", help="release ID for deploy (7-64 lowercase hex characters)")
    pipeline.add_argument("--allow-unhealthy-current", action="store_true",
                          help="deploy even though the current version fails its checks; use it to ship a fix")
    pipeline.add_argument("--json", action="store_true", help="print the full record as JSON")

    review = groups.add_parser("review", help="freeze changes, check them in a separate worktree, keep and compare results",
                               epilog=REFERENCE)
    review.add_argument("--repo", type=Path, default=Path.cwd(),
                        help="folder in a Git repository with a commit; paths are relative to it (default: current folder)")
    review_commands = review.add_subparsers(dest="action", required=True, metavar="ACTION")
    freeze = review_commands.add_parser("snapshot", help="print a commit of HEAD plus the named files; nothing else changes")
    freeze.add_argument("files", nargs="+", help="files to include, relative to --repo; added and deleted files count")
    isolated = review_commands.add_parser("check", help="run the configured checks on a commit in a new worktree; "
                                          "exit 0 passed, 1 failed or uncertain, 2 cannot run")
    isolated.add_argument("snapshot", help="full commit ID from `review snapshot`, or HEAD")
    isolated.add_argument("--config", type=Path, required=True, help="checks TOML (schema = 1) with setup, checks and artifacts")
    isolated.add_argument("--runs-root", type=Path, help="where run folders are kept (default: a folder in the system temp directory)")
    isolated.add_argument("--keep", action="store_true", help="keep the worktree after a normal finish")
    confirm = review_commands.add_parser("verify", help="rehash a run's retained artifacts against its manifest; exit 0 when all match")
    confirm.add_argument("run_dir", type=Path, help="run folder printed by `review check`")
    keep = review_commands.add_parser("accept", help="keep a verified run's artifacts as the accepted version")
    keep.add_argument("run_dir", type=Path, help="run folder printed by `review check`")
    keep.add_argument("--label", default="accepted", help="name of the accepted version (default: accepted)")
    against = review_commands.add_parser("compare", help="compare the working tree, or a run's artifacts, with the accepted "
                                         "version; exit 0 when nothing changed")
    against.add_argument("--label", default="accepted", help="accepted version to compare with (default: accepted)")
    against.add_argument("--run", type=Path, help="compare this run folder's retained artifacts instead of the working tree")
    against.add_argument("--diff", action="store_true", help="include a unified diff for changed text files")

    publish = groups.add_parser("publish", help="extra for web projects: check a static site build and switch to it atomically",
                                epilog=REFERENCE)
    publish.add_argument("--output", type=Path, required=True, help="publish folder; must be empty on first use")
    publish.add_argument("--project", required=True, help="project name owning the output folder (lowercase, digits, _ and -)")
    publications = publish.add_subparsers(dest="action", required=True, metavar="ACTION")
    build = publications.add_parser("build", help="check links in the listed files, store a new version and switch to it")
    build.add_argument("--source", type=Path, required=True, help="build folder the listed paths are relative to")
    build.add_argument("--files", type=Path, required=True, help="JSON array of relative file paths to publish; must include index.html")
    restore = publications.add_parser("restore", help="re-verify an earlier version and switch back to it")
    restore.add_argument("version", help="full version hash printed by build")

    ui = groups.add_parser("ui", help="extra for web projects: capture pages at several widths into one review sheet",
                           epilog=REFERENCE)
    ui.add_argument("--config", type=Path, required=True, help="JSON with base_url, pages and widths")
    ui.add_argument("--output", type=Path, required=True, help="empty folder for PNGs, index.html, sheet.png and result.json")
    ui.add_argument("--channel", choices=("chrome", "msedge", "chromium"), help="use an installed browser instead of Playwright's Chromium")
    _describe(parser)
    return parser


def _describe(parser):
    """Show each command's one-line help at the top of its own --help, with the reference pointer below."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for choice in action._choices_actions:
                sub = action.choices[choice.dest]
                sub.description = sub.description or choice.help
                sub.epilog = sub.epilog or REFERENCE
                _describe(sub)


def _read_body(args):
    if args.body is not None:
        return args.body
    if args.body_file is not None:
        return args.body_file.read_text(encoding="utf-8-sig")
    return sys.stdin.read()


def _report_tracking(record):
    if record["created"]:
        print(f"initialized a Git repository: {record['repository']}")
    if record["committed"]:
        print(f"committed the new folder in {record['repository']}")
    else:
        print(f"note: the new folder was not committed ({record['skipped']}); commit it before `awkit review check`",
              file=sys.stderr)


def _print_report(report):
    print(f"target: {report['target']}\nrelease: {report['release']}")
    for check in report["checks"]:
        print(f"{check['name']}: {'passed' if check['ok'] else 'failed'}")


def _run_check(args):
    from . import checks
    if args.action == "commit":
        message = args.message.read_text(encoding="utf-8", errors="replace") if args.message else None
        report = checks.commit_identity(args.repo, message, args.rev, args.history)
        for problem in report["problems"]:
            print(problem, file=sys.stderr)
        return 0 if report["ok"] else 1
    if args.action == "writing":
        report = checks.check_writing(args.paths)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else checks.render_writing(report))
        return 0 if report["ok"] else 1
    session, event, repeated = args.session, None, False
    if args.hook:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            payload = {}
        session = session or payload.get("session_id")
        event = payload.get("hook_event_name")
        repeated = bool(payload.get("stop_hook_active"))
        if repeated:
            return 0
    report = checks.done(args.repo, args.runs_root, session, mark=args.mark or event == "SessionStart")
    message = checks.render_done(report)
    if args.hook:
        if not report["ok"]:
            print(message, file=sys.stderr)
            return 2
        return 0
    print(message, file=sys.stdout if report["ok"] else sys.stderr)
    return 0 if report["ok"] else 1


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.group == "check":
            return _run_check(args)
        if args.group == "kit" and args.action == "hooks":
            from .checks import install_hooks
            if not (args.git or args.claude):
                parser.error("choose --git, --claude or both")
            written, kept = install_hooks(args.dir, sys.executable, args.git, args.claude)
            for path in written:
                print(f"installed: {path}")
            for path in kept:
                print(f"kept existing hook: {path}")
            return 0
        if args.group == "kit" and args.action == "skills":
            written, skipped = install_skills(args.dir, args.provider, args.kit)
            for path in written:
                print(f"created: {path}")
            for path in skipped:
                print(f"kept existing file: {path}")
            return 0 if written or not skipped else 2
        if args.group == "kit" and args.action == "roles":
            written, skipped, warnings = install_roles(args.dir, args.provider, args.model)
            for path in written:
                print(f"created: {path}")
            for path in skipped:
                print(f"kept existing file: {path}")
            for warning in warnings:
                print(f"note: {warning}", file=sys.stderr)
            return 0 if written or not skipped else 2
        if args.group == "usage":
            from datetime import datetime

            from .usage import collect
            from .usage import render as render_usage
            since = None
            if args.since:
                since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=UTC)
            result = collect(args.paths, since)
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_usage(result))
            return 0
        if args.group == "kit" and args.action == "scan":
            from .scan import scan as scan_project
            report = scan_project(args.dir)
            print(report["suggested_checks_toml"] if args.checks else json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.group == "kit" and args.action == "example":
            target, copied = install_example(args.kind, args.dir)
            print(f"created the {args.kind} example: {target}\ncopied {len(copied)} files")
            if not args.no_git:
                _report_tracking(track(target, [target], f"Add the {args.kind} example"))
            print(f"next: read {target / 'README.md'} and run the commands there")
            return 0
        if args.group == "kit":
            target, copied = install(args.dir, args.name)
            print(f"created the kit: {target}\ncopied {len(copied)} files")
            if not args.no_git:
                _report_tracking(track(args.dir, [target], f"Add {args.name}"))
            print(f"next: tell your agent to read {target / 'README.md'} and connect the kit to this project")
            return 0
        if args.group == "review":
            if args.action == "snapshot":
                print(snapshot(args.repo, args.files))
                return 0
            if args.action == "verify":
                report = verify_run(args.run_dir)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0 if report["verified"] else 1
            if args.action == "accept":
                print(json.dumps(accept(args.repo, args.run_dir, args.label), ensure_ascii=False, indent=2))
                return 0
            if args.action == "compare":
                report = compare(args.repo, args.label, args.run, args.diff)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0 if report["unchanged"] else 1
            result = run_checks(args.repo, args.snapshot, args.config, args.runs_root, args.keep)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "passed" else 1
        if args.group == "publish":
            publisher = Publisher(args.output, args.project)
            if args.action == "restore":
                result = publisher.restore(args.version)
            else:
                files = json.loads(args.files.read_text(encoding="utf-8"))
                if not isinstance(files, list) or any(not isinstance(name, str) for name in files):
                    raise ValueError("The file list must be a JSON array of strings.")
                result = publisher.publish(args.source, files)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.group == "ui":
            from .extras.ui import capture
            result = capture(args.config, args.output, args.channel)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "passed" else 1
        if args.group == "channel":
            store = Channel(args.db)
            if args.action == "post":
                print(store.post(args.sender, args.receiver, args.kind, _read_body(args),
                                 reply_to=args.reply_to, snap=args.snap))
                return 0
            if args.action == "export":
                print(render(store.export(), args.json))
                return 0
            code, rows = store.wait(args.role, args.mode, args.target, seconds=args.max)
            if rows:
                print(render(rows, args.json))
            elif code == 3:
                print("main closed the channel.")
            return code
        if (args.action == "deploy") != bool(args.release):
            parser.error("a release is required for deploy and not accepted by other actions")
        if args.allow_unhealthy_current and args.action != "deploy":
            parser.error("--allow-unhealthy-current applies to deploy only")
        runner = Pipeline(args.config)
        if args.action == "plan":
            result = {"target": runner.target, "state_dir": str(runner.state),
                      "phases": ["preflight", "verify-current", "backup", "deploy", "verify"],
                      "auto_rollback": runner.auto_rollback, "commands_executed": False}
        elif args.action == "history":
            result = {"target": runner.target, "releases": runner.history() if runner.state.exists() else []}
        elif args.action == "status":
            result = runner.inspect()
        elif args.action == "reconcile":
            result = runner.reconcile()
        else:
            result = runner.run(args.action, args.release,
                                allow_unhealthy_current=args.allow_unhealthy_current)
        if args.action == "status":
            success = result["healthy"]
        else:
            success = result.get("status", "passed") in ("passed", "reconciled")
        if args.json or args.action == "plan":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.action == "status":
            _print_report(result)
        elif args.action == "history":
            releases = result["releases"]
            if not releases:
                print("No release has passed verification on this target.")
            for index, release in enumerate(reversed(releases)):
                print(f"{release}{'  (latest)' if index == 0 else ''}")
        else:
            print(f"status: {result.get('status')}")
            failure = result.get("failure")
            if failure:
                detail = ", ".join(failure.get("failed_checks", []))
                print(f"failed phase: {failure['phase']}" + (f" ({detail})" if detail else ""))
            if result.get("run_id"):
                print(f"run record: {runner.state / 'runs' / result['run_id']}")
        return 0 if success else 1
    except StepError as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return exc.code if 1 <= exc.code <= 125 else 1
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
        print(f"cannot run: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted. Check the run record and the target's actual state.", file=sys.stderr)
        return 130
