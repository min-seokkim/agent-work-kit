"""The channel commands: a message log between a main and a reviewer session."""

import json
import sys
from pathlib import Path

from .channel import KINDS, ROLES, Channel, render
from .cli_common import REFERENCE, _read_body


def add(groups):
    channel = groups.add_parser("channel", help="message log for a main session and a reviewer session",
                                epilog=REFERENCE)
    channel.add_argument("--db", type=Path,
                         help="SQLite file both sessions use (default: .awkit/channel.sqlite3)")
    commands = channel.add_subparsers(dest="action", required=True, metavar="ACTION")
    post = commands.add_parser("post", help="record a message and print its ID; the body comes from --body, --body-file or stdin")
    post.add_argument("sender", choices=ROLES, help="who sends")
    post.add_argument("receiver", choices=ROLES, help="who receives; must differ from the sender")
    post.add_argument("kind", choices=KINDS, help="request kinds: review, scout, test, draft, question, final; "
                      "notice; re and rebut answer --reply-to; withdraw retracts a reviewer's re; "
                      "close (main only) refuses outstanding protocol obligations")
    post.add_argument("--reply-to", metavar="ID", help="other side's message for re/rebut; reviewer's own re for withdraw")
    post.add_argument("--snap", metavar="ID", help="snapshot or commit the message is about (7-64 hex characters)")
    body = post.add_mutually_exclusive_group()
    body.add_argument("--body", help="body text")
    body.add_argument("--body-file", type=Path, help="UTF-8 file with the body")
    wait = commands.add_parser("wait", help="wait for messages; exit 0 found, 1 timeout, 3 channel closed (reviewer)")
    wait.add_argument("role", choices=ROLES, help="the role that is waiting")
    wait.add_argument("mode", choices=("request", "new", "reply", "peek"),
                      help="request: unanswered requests and rebuttals; new: messages after the read position; "
                           "reply: answers to the given ID; peek: all incoming messages without moving cursors")
    wait.add_argument("--consumer", metavar="ID", help="new mode reader identity; omitted uses the shared role cursor with a warning")
    wait.add_argument("target", nargs="?", metavar="ID", help="message ID, for reply mode only")
    wait.add_argument("--max", type=float, default=120, metavar="SECONDS", help="how long to wait; 0 checks once (default: 120)")
    wait.add_argument("--json", action="store_true", help="print messages as JSON")
    wait.add_argument("--keep-awake", action="store_true",
                      help="best-effort Windows idle-sleep prevention during this wait; warns if unavailable")
    export = commands.add_parser("export", help="print the whole channel; does not move read positions")
    export.add_argument("--json", action="store_true", help="print messages as JSON")
    status = commands.add_parser("status", help="observe listed channels and explicit task-record obligations without writes")
    status.add_argument("--record", type=Path, required=True, help="schema-1 task record JSON")
    status.add_argument("--json", action="store_true", help="print the schema-1 aggregate report")


def run(args, parser):
    if args.action == "status":
        if args.db is not None:
            parser.error("channel status uses --record; --db is not accepted")
        from .channel_status import observe
        from .channel_status import render as render_status
        result, code = observe(args.record)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_status(result))
        return code
    store = Channel(args.db if args.db is not None else Path(".awkit/channel.sqlite3"))
    if args.action == "post":
        print(store.post(args.sender, args.receiver, args.kind, _read_body(args),
                         reply_to=args.reply_to, snap=args.snap))
        return 0
    if args.action == "export":
        print(render(store.export(), args.json))
        return 0
    if args.mode == "new" and args.consumer is None:
        print("Warning: new without --consumer uses the shared role cursor; "
              "pass a session ID to keep independent read positions.", file=sys.stderr)
    options = dict(seconds=args.max)
    if args.consumer is not None:
        options["consumer"] = args.consumer
    if args.keep_awake:
        from .keep_awake import keep_awake
        with keep_awake():
            code, rows = store.wait(args.role, args.mode, args.target, **options)
    else:
        code, rows = store.wait(args.role, args.mode, args.target, **options)
    if rows:
        print(render(rows, args.json))
    elif code == 3:
        print("main closed the channel.")
    return code
