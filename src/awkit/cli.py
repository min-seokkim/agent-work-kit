"""Command-line entry points."""

import argparse
import json
import sqlite3
import sys
from datetime import UTC
from pathlib import Path

from . import __version__
from .channel import KINDS, ROLES, Channel, render
from .kit_install import EXAMPLES, install, install_example, install_roles
from .pipeline import Pipeline, StepError
from .publish import Publisher
from .review import check as run_checks
from .review import snapshot
from .review import verify as verify_run


def _parser():
    parser = argparse.ArgumentParser(prog="awkit", description="Agent Work Kit: working instructions, a Korean writing guide and verification tools")
    parser.add_argument("--version", action="version", version=f"awkit {__version__}")
    groups = parser.add_subparsers(dest="group", required=True)

    kit = groups.add_parser("kit", help="Copy the Markdown kit into a project")
    kit_commands = kit.add_subparsers(dest="action", required=True)
    init = kit_commands.add_parser("init", help="Create the kit folder. An existing folder is never overwritten.")
    init.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder that receives the kit")
    init.add_argument("--name", default="agent-work-kit", help="name of the folder to create (default: agent-work-kit)")
    example = kit_commands.add_parser("example", help="Create a folder with a runnable first-run example.")
    example.add_argument("kind", choices=EXAMPLES, help="documents: a small Korean document set; data: a CSV to summarise")
    example.add_argument("dir", type=Path, help="new folder to create")
    roles = kit_commands.add_parser("roles", help="Generate Claude Code or Codex role files from the role templates. Existing files are kept.")
    roles.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder that receives the role files")
    roles.add_argument("--provider", choices=("claude", "codex"), required=True)
    roles.add_argument("--model", action="append", metavar="TIER=MODEL[:EFFORT]",
                       help="model for a tier (efficient, standard, judge, top); may be repeated")

    usage = groups.add_parser("usage", help="Collect actual models and tokens from Claude Code and Codex session logs")
    usage.add_argument("paths", nargs="+", type=Path, help="session log files (.jsonl) or folders")
    usage.add_argument("--since", help="read only files modified on or after this date (YYYY-MM-DD, UTC)")
    usage.add_argument("--json", action="store_true")

    channel = groups.add_parser("channel", help="Local review channel between two agent sessions")
    channel.add_argument("--db", type=Path, default=Path(".awkit/channel.sqlite3"))
    commands = channel.add_subparsers(dest="action", required=True)
    post = commands.add_parser("post", help="Record a message. The body comes from stdin, --body or --body-file.")
    post.add_argument("sender", choices=ROLES)
    post.add_argument("receiver", choices=ROLES)
    post.add_argument("kind", choices=KINDS)
    post.add_argument("--reply-to")
    post.add_argument("--snap")
    body = post.add_mutually_exclusive_group()
    body.add_argument("--body", help="body text")
    body.add_argument("--body-file", type=Path, help="UTF-8 file with the body")
    wait = commands.add_parser("wait", help="Wait for messages.")
    wait.add_argument("role", choices=ROLES)
    wait.add_argument("mode", choices=("request", "new", "reply"))
    wait.add_argument("target", nargs="?")
    wait.add_argument("--max", type=float, default=120)
    wait.add_argument("--json", action="store_true")
    export = commands.add_parser("export", help="Print the whole channel.")
    export.add_argument("--json", action="store_true")

    pipeline = groups.add_parser("pipeline", help="Replace a running version with project commands and verify the result")
    pipeline.add_argument("--config", type=Path, required=True)
    pipeline.add_argument("action", choices=("plan", "deploy", "rollback", "status", "reconcile", "history"))
    pipeline.add_argument("release", nargs="?")
    pipeline.add_argument("--allow-unhealthy-current", action="store_true",
                          help="deploy even though the current version fails its checks; use it to ship a fix")
    pipeline.add_argument("--json", action="store_true")

    review = groups.add_parser("review", help="Freeze selected changes and check them in a separate worktree")
    review.add_argument("--repo", type=Path, default=Path.cwd())
    review_commands = review.add_subparsers(dest="action", required=True)
    freeze = review_commands.add_parser("snapshot", help="Write the named files' changes into a Git commit object.")
    freeze.add_argument("files", nargs="+")
    isolated = review_commands.add_parser("check", help="Run the project's checks on a frozen revision in a separate worktree.")
    isolated.add_argument("snapshot")
    isolated.add_argument("--config", type=Path, required=True)
    isolated.add_argument("--runs-root", type=Path)
    isolated.add_argument("--keep", action="store_true")
    compare = review_commands.add_parser("verify", help="Compare a run folder's retained artifacts with its manifest.")
    compare.add_argument("run_dir", type=Path)

    publish = groups.add_parser("publish", help="Validate a static document build and publish it locally")
    publish.add_argument("--output", type=Path, required=True)
    publish.add_argument("--project", required=True)
    publications = publish.add_subparsers(dest="action", required=True)
    build = publications.add_parser("build")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--files", type=Path, required=True, help="JSON array of relative file paths to publish")
    restore = publications.add_parser("restore")
    restore.add_argument("version")

    ui = groups.add_parser("ui", help="Capture the listed pages at several widths")
    ui.add_argument("--config", type=Path, required=True)
    ui.add_argument("--output", type=Path, required=True)
    ui.add_argument("--channel", choices=("chrome", "msedge", "chromium"))
    return parser


def _read_body(args):
    if args.body is not None:
        return args.body
    if args.body_file is not None:
        return args.body_file.read_text(encoding="utf-8-sig")
    return sys.stdin.read()


def _print_report(report):
    print(f"target: {report['target']}\nrelease: {report['release']}")
    for check in report["checks"]:
        print(f"{check['name']}: {'passed' if check['ok'] else 'failed'}")


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = _parser()
    args = parser.parse_args(argv)
    try:
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
        if args.group == "kit" and args.action == "example":
            target, copied = install_example(args.kind, args.dir)
            print(f"created the {args.kind} example: {target}\ncopied {len(copied)} files")
            print(f"next: read {target / 'README.md'} and run the commands there")
            return 0
        if args.group == "kit":
            target, copied = install(args.dir, args.name)
            print(f"created the kit: {target}\ncopied {len(copied)} files")
            print(f"next: open {target / 'README.md'} and fill in the project profile")
            return 0
        if args.group == "review":
            if args.action == "snapshot":
                print(snapshot(args.repo, args.files))
                return 0
            if args.action == "verify":
                report = verify_run(args.run_dir)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0 if report["verified"] else 1
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
            from .ui import capture
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
