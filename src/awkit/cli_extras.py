"""The web-project extras: pipeline, publish and ui."""

import json
import sys
from pathlib import Path

from .cli_common import REFERENCE


def add_pipeline(groups):
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


def add_publish(groups):
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


def add_ui(groups):
    ui = groups.add_parser("ui", help="extra for web projects: capture pages at several widths into one review sheet",
                           epilog=REFERENCE)
    ui.add_argument("--config", type=Path, required=True, help="JSON with base_url, pages and widths")
    ui.add_argument("--output", type=Path, required=True, help="empty folder for PNGs, index.html, sheet.png and result.json")
    ui.add_argument("--channel", choices=("chrome", "msedge", "chromium"), help="use an installed browser instead of Playwright's Chromium")


def _step_error():
    """The release runner's error class once it is loaded, else nothing to catch. The web extras are
    imported only by their commands, so `awkit hook`, which runs on every tool call, starts faster."""
    module = sys.modules.get("awkit.extras.pipeline")
    return module.StepError if module else ()


def _print_report(report):
    print(f"target: {report['target']}\nrelease: {report['release']}")
    for check in report["checks"]:
        print(f"{check['name']}: {'passed' if check['ok'] else 'failed'}")


def run_pipeline(args, parser):
    if (args.action == "deploy") != bool(args.release):
        parser.error("a release is required for deploy and not accepted by other actions")
    if args.allow_unhealthy_current and args.action != "deploy":
        parser.error("--allow-unhealthy-current applies to deploy only")
    from .extras.pipeline import Pipeline
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


def run_publish(args, parser):
    from .extras.publish import Publisher
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


def run_ui(args, parser):
    from .extras.ui import capture
    result = capture(args.config, args.output, args.channel)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1
