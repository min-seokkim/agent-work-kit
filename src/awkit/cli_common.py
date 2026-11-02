"""What every command group shares: the reference pointer and reading a message body."""

import sys

REFERENCE = ("Formats, rules and exit codes are in agent-work-kit/reference.md "
             "(kit/reference.md in the awkit repository).")


def _read_body(args):
    if args.body is not None:
        return args.body
    if args.body_file is not None:
        return args.body_file.read_text(encoding="utf-8-sig")
    return sys.stdin.read()
