"""The `hook` and `kit hooks` commands: their arguments and what they print. cli.py registers them with one
call, so the hook runner's commands change here without touching the other commands."""

import argparse
import json
import sys
from pathlib import Path

EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SubagentStop")


def _runner_options(parser, keep_parent=False):
    """The runner's options, on `hook` and again after an event name. After the event they default to
    SUPPRESS, so a value given before the event is kept."""
    default = (lambda value: argparse.SUPPRESS) if keep_parent else (lambda value: value)
    parser.add_argument("--root", type=Path, default=default(None),
                        help="project folder with rules.toml (default: found from the event's cwd)")
    parser.add_argument("--kit-rules", action="store_true", default=default(False),
                        help="apply the kit's default rules when the project has no rules.toml")
    parser.add_argument("--skip", action="append", default=default([]), metavar="RULE",
                        help="leave out a rule by name; `kit hooks` adds --skip done-check when the project has its own "
                             "completion gate")
    parser.add_argument("--kit-hooks", action="store_true", default=default(False),
                        help="marks a handler `awkit kit hooks` added, so `kit hooks --remove` can find it")


def add(groups, kit_commands):
    """Register `awkit hook` and `awkit kit hooks`."""
    hooks = kit_commands.add_parser(
        "hooks", help="write rules.toml when there is none, run `awkit hook` from .claude/settings.local.json and "
                      ".codex/hooks.json, and add the commit identity check to the commit-msg hook")
    hooks.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder (default: .)")
    hooks.add_argument("--git", action="store_true", help="only the commit-msg hook (with rules.toml)")
    hooks.add_argument("--claude", action="store_true", help="only Claude Code's handlers (with rules.toml)")
    hooks.add_argument("--codex", action="store_true", help="only Codex's handlers (with rules.toml)")
    hooks.add_argument("--remove", action="store_true",
                       help="take out what `kit hooks` added; a changed rules.toml is deleted only after asking")

    hook = groups.add_parser("hook", help="run as a Claude Code or Codex hook: apply rules.toml to the event on stdin "
                                          "and print the decision JSON", description="See reference.md, section hook.")
    _runner_options(hook)
    actions = hook.add_subparsers(dest="action", metavar="EVENT|ACTION")
    for event in EVENTS:
        _runner_options(actions.add_parser(event, help=f"handle a {event} event"), keep_parent=True)
    report = actions.add_parser("report", help="how often rules fired, blocked and failed, per session")
    report.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder (default: .)")
    report.add_argument("--json", action="store_true", help="print the summary as JSON")
    reply = actions.add_parser("reply", help="the default writing-reply rule: exit 1 with what is wrong when the "
                                             "final reply is a Korean document written without the writing guide")
    reply.add_argument("--hangul", type=int, default=500,
                       help="Hangul syllables above which a reply counts as long (default: 500)")
    actions.add_parser("kit-version", help="the default kit-version rule: exit 1 with a line when checks.toml "
                                           "records another kit version than the installed awkit")


def run(args, parser):
    """Run `awkit hook ...` or `awkit kit hooks`; returns the exit code."""
    if args.group == "kit":
        return _kit_hooks(args)
    if args.action == "report":
        from . import hooks
        result = hooks.report(args.dir)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else hooks.render_report(result))
        return 0
    if args.action in ("reply", "kit-version"):
        from .session_rules import main
        return main(args.action, getattr(args, "hangul", 500))
    from . import hooks
    try:
        text = sys.stdin.read()
    except (OSError, UnicodeDecodeError):
        text = "�"
    output = hooks.run(text, args.root, args.skip, args.kit_rules, event=args.action)
    if output:
        print(output)
    return 0


def _kit_hooks(args):
    from . import kit_hooks
    if args.remove:
        for path, what in kit_hooks.remove(args.dir):
            print(f"{what}: {path}")
        return 0
    chosen = args.git or args.claude or args.codex
    result = kit_hooks.install(args.dir, args.git or not chosen, args.claude or not chosen, args.codex or not chosen)
    for path in result["installed"]:
        print(f"installed: {path}")
    for path in result["connected"]:
        print(f"connected: {path}")
    for path in result["kept"]:
        print(f"kept existing hook: {path}")
    for note in result["notes"]:
        print(f"note: {note}")
    return 0
