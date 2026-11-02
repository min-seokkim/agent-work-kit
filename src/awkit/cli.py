"""Command-line entry points. Each command group lives in its own module, which adds its parser and runs
its commands; this module puts the parser together and dispatches by group."""

import argparse
import sqlite3
import sys

from . import __version__, cli_channel, cli_check, cli_extras, cli_kit, cli_review, cli_session, hook_cli
from .cli_check import _run_check  # noqa: F401  (rule_command and tests use it)
from .cli_common import REFERENCE
from .cli_extras import _step_error
from .cli_kit import _report_init  # noqa: F401  (tests use it)

# tests/test_kit_commands.py parses every `awkit` command line in kit/*.md with this parser.
PREVENTS = {"awkit parser, against every command shown in kit/*.md": ("F4",)}

# The handler for each command group; `kit hooks` is handled by the kit module, which hands it to hook_cli.
HANDLERS = {"doctor": cli_check.run_doctor, "check": cli_check.run_check, "hook": hook_cli.run, "kit": cli_kit.run,
            "usage": cli_check.run_usage, "review": cli_review.run, "publish": cli_extras.run_publish,
            "ui": cli_extras.run_ui, "session": cli_session.run, "channel": cli_channel.run,
            "pipeline": cli_extras.run_pipeline}


def _parser():
    parser = argparse.ArgumentParser(
        prog="awkit", epilog=REFERENCE,
        description="Agent Work Kit: working instructions for coding agents and tools that freeze changes, "
                    "check them in isolation and retain the evidence.")
    parser.add_argument("--version", action="version", version=f"awkit {__version__}")
    groups = parser.add_subparsers(dest="group", required=True, metavar="COMMAND")
    # The order here is the order of `awkit --help`.
    kit_commands = cli_kit.add(groups)
    cli_check.add(groups)
    hook_cli.add(groups, kit_commands)
    cli_check.add_doctor(groups)
    cli_check.add_usage(groups)
    cli_channel.add(groups)
    cli_session.add(groups)
    cli_extras.add_pipeline(groups)
    cli_review.add(groups)
    cli_extras.add_publish(groups)
    cli_extras.add_ui(groups)
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


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return HANDLERS[args.group](args, parser)
    except _step_error() as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return exc.code if 1 <= exc.code <= 125 else 1
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
        print(f"cannot run: {exc}", file=sys.stderr)
        for note in getattr(exc, "__notes__", ()):
            print(note, file=sys.stderr)
        return 2
    except KeyboardInterrupt as exc:
        print("Interrupted. Check the run record and the target's actual state.", file=sys.stderr)
        for note in getattr(exc, "__notes__", ()):
            print(note, file=sys.stderr)
        return 130
