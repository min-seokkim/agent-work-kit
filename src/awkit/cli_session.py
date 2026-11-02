"""The session commands: local controls for managed conversations."""

import json
import sys
from pathlib import Path

from .channel import ROLES
from .cli_common import REFERENCE, _read_body

DECISION_CHOICES = ("accept", "acceptForSession", "decline", "cancel", "allow", "deny")


PREVENTS = {"awkit session decide": ("F1", "F29")}


def add(groups):
    session = groups.add_parser("session", help="local controls for managed conversations and read-only channel history",
                                epilog=REFERENCE)
    session.add_argument("--project", type=Path, default=Path.cwd(), help="project owned by the local controller")
    session_commands = session.add_subparsers(dest="action", required=True, metavar="ACTION")
    session_serve = session_commands.add_parser("serve", help="own a local controller; print its private human-control URL")
    session_serve.add_argument("--codex", default="codex", help="Codex executable (default: codex on PATH)")
    session_serve.add_argument("--claude", help="unmodified Claude executable; otherwise use the SDK bundled binary")
    session_serve.add_argument("--port", type=int, default=0, help="loopback port; 0 selects an available port")
    session_serve.add_argument("--record", type=Path, help="existing schema-1 declaration record to observe read-only")
    session_create = session_commands.add_parser("create", help="create a named owned Codex or Claude conversation")
    session_create.add_argument("name")
    session_create.add_argument("--responsibility", required=True)
    session_create.add_argument("--provider", choices=("codex", "claude"), default="codex")
    session_create.add_argument("--model", help="explicit model ID or provider alias for a new conversation; omitted uses native defaults")
    session_create.add_argument("--reasoning-effort", help="explicit reasoning effort with --model; omitted inherits native configuration")
    session_create.add_argument("--sandbox", choices=("read-only", "workspace-write"), help="Codex scope (default: read-only)")
    session_create.add_argument("--permission-mode", choices=("default",), help="Claude native mode (default: default)")
    session_enroll = session_commands.add_parser("enroll", help="enroll an explicit idle local Codex thread; send no assignment")
    session_enroll.add_argument("name")
    session_enroll.add_argument("--thread-id", required=True)
    session_enroll.add_argument("--provider", choices=("codex", "claude"), default="codex", help="selected provider; unsupported enrollment returns its reason")
    session_discover = session_commands.add_parser("discover", help="list current-project Codex metadata through an existing eligible connection")
    session_discover.add_argument("--cursor", help="opaque next cursor from the same discovery sequence")
    session_discover.add_argument("--limit", type=int, default=20, help="page size from 1 to 50 (default: 20)")
    session_discover.add_argument("--provider", choices=("codex", "claude"), default="codex", help="selected provider; unsupported discovery returns its reason")
    session_send = session_commands.add_parser("send", help="store an assignment; the owner starts an idle turn automatically")
    session_send.add_argument("ident", help="managed session name or ID")
    session_send.add_argument("--key", help="reuse this client key to recover the same stored submission; never auto-resend")
    session_send.add_argument("--kind", choices=("review", "scout", "test", "draft", "question", "final", "notice"),
                              default="question")
    session_body = session_send.add_mutually_exclusive_group()
    session_body.add_argument("--body")
    session_body.add_argument("--body-file", type=Path)
    session_update = session_commands.add_parser("update", help="update one exact active Codex assignment; never queue or replay")
    session_update.add_argument("ident")
    session_update.add_argument("--request", required=True, dest="request_id")
    session_update.add_argument("--expected-turn-id", required=True)
    session_update.add_argument("--key", required=True)
    update_body = session_update.add_mutually_exclusive_group()
    update_body.add_argument("--body")
    update_body.add_argument("--body-file", type=Path)
    session_status = session_commands.add_parser("status", help="read all sessions, one managed session or one exact request as JSON")
    session_status.add_argument("--session", dest="status_session", action="append", help="exact local managed session name or ID")
    session_status.add_argument("--request", dest="status_request", action="append", help="exact stored input ID; requires --session")
    session_register = session_commands.add_parser("register", help="open an existing pairwise channel read-only")
    session_register.add_argument("--channel", type=Path, required=True)
    session_register.add_argument("--main-name", required=True, help="human name for the channel's existing main party")
    session_register.add_argument("--reviewer-name", required=True, help="human name for the existing reviewer party")
    session_register.add_argument("--local-role", choices=ROLES, default="main")
    session_register.add_argument("--task", default="", help="optional task label; no task state is created")
    session_decide = session_commands.add_parser("decide", help="answer an actual pending provider request on its connection")
    session_decide.add_argument("ident")
    decision_source = session_decide.add_mutually_exclusive_group(required=True)
    decision_source.add_argument("--decision", dest="decision_id")
    decision_source.add_argument("--input-file", type=Path, help="complete decision JSON in UTF-8; - reads stdin; cannot mix with choice/answers arguments")
    decision_answer = session_decide.add_mutually_exclusive_group()
    decision_answer.add_argument("--choice", choices=DECISION_CHOICES)
    decision_answer.add_argument("--answers-file", type=Path, help="Claude question answers JSON object keyed by exact question text")
    session_interrupt = session_commands.add_parser("interrupt", help="request interruption of the observed native turn")
    session_interrupt.add_argument("ident")
    session_resume = session_commands.add_parser("resume", help="retry exact-ID reconnection; never replay uncertain work")
    session_resume.add_argument("ident")
    session_cancel = session_commands.add_parser("cancel", help="cancel an unsent assignment or retain a later stop request")
    session_cancel.add_argument("ident")
    session_cancel.add_argument("--request", required=True, dest="request_id")
    session_commands.add_parser("stop", help="stop this controller and its owned provider; persisted sessions remain")


def _decision_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate decision input key: {key}")
        result[key] = value
    return result


def _decision_constant(value):
    raise ValueError(f"Invalid JSON constant in decision input: {value}")


def _read_decision(args):
    if args.input_file is None:
        if args.choice is None and args.answers_file is None:
            raise ValueError("--decision requires --choice or --answers-file.")
        choice = {"answers": json.loads(args.answers_file.read_text(encoding="utf-8"))} if args.answers_file else args.choice
        return dict(ident=args.ident, decision_id=args.decision_id, choice=choice)
    if args.choice is not None or args.answers_file is not None:
        raise ValueError("--input-file cannot be mixed with --choice or --answers-file.")
    if str(args.input_file) == "-":
        content = getattr(sys.stdin, "buffer", sys.stdin).read()
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content.removeprefix("\ufeff")
    else:
        text = args.input_file.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text, object_pairs_hook=_decision_object, parse_constant=_decision_constant)
    except RecursionError as exc:
        raise ValueError("Decision JSON nesting exceeds parser support.") from exc
    if not isinstance(data, dict) or set(data) != {"decision_id", "choice"}:
        raise ValueError("Decision input must contain only decision_id and choice; the session stays the CLI target.")
    if not isinstance(data["decision_id"], str) or not data["decision_id"].strip():
        raise ValueError("Decision input requires a nonempty exact decision_id string.")
    choice = data["choice"]
    if isinstance(choice, str):
        if choice not in DECISION_CHOICES:
            raise ValueError("Decision input requires an offered choice supported by decide.")
    elif (not isinstance(choice, dict) or set(choice) != {"answers"} or not isinstance(choice["answers"], dict)
          or not all(isinstance(value, str) or isinstance(value, list) and all(isinstance(item, str) for item in value)
                     for value in choice["answers"].values())):
        raise ValueError("Question choice must contain answers keyed by exact question text, with string or string-list values.")
    return dict(ident=args.ident, **data)


def run(args, parser):
    import shutil
    import uuid

    from .session_http import request, serve
    if args.action == "serve":
        command = shutil.which(args.codex) or args.codex
        return serve(args.project, [command], port=args.port, record=args.record, claude_cli=args.claude)
    payload = {}
    if args.action == "status":
        from .session_reading import selectors
        payload = selectors({key: value for key, value in (("session", args.status_session), ("request", args.status_request)) if value is not None})
    elif args.action == "create":
        payload = dict(name=args.name, responsibility=args.responsibility, provider=args.provider,
                       sandbox=args.sandbox, permission_mode=args.permission_mode, project=str(args.project.resolve()))
        if args.model is not None:
            payload["model"] = args.model
        if args.reasoning_effort is not None:
            payload["reasoning_effort"] = args.reasoning_effort
    elif args.action == "enroll":
        payload = dict(name=args.name, thread_id=args.thread_id)
        if args.provider != "codex":
            payload["provider"] = args.provider
    elif args.action == "discover":
        payload = dict(cursor=args.cursor, limit=args.limit)
        if args.provider != "codex":
            payload["provider"] = args.provider
    elif args.action == "send":
        payload = dict(ident=args.ident, key=args.key or uuid.uuid4().hex,
                       body=_read_body(args), kind=args.kind, entry="agent")
    elif args.action == "update":
        payload = dict(ident=args.ident, key=args.key, request_id=args.request_id,
                       expected_turn_id=args.expected_turn_id, body=_read_body(args), entry="agent")
    elif args.action == "register":
        payload = dict(channel=str(args.channel), main_name=args.main_name, reviewer_name=args.reviewer_name,
                       local_role=args.local_role, task=args.task)
    elif args.action == "decide":
        payload = _read_decision(args)
    elif args.action == "interrupt":
        payload = dict(ident=args.ident)
    elif args.action == "resume":
        payload = dict(ident=args.ident)
    elif args.action == "cancel":
        payload = dict(ident=args.ident, request_id=args.request_id)
    result = request(args.project, args.action, payload)
    print(json.dumps(dict(schema=1, **result)))
    if args.action == "update":
        return 0 if result["state"] == "acknowledged" else 1
    if args.action == "discover":
        return 0 if result["available"] else 1
    return 1 if args.action in ("create", "enroll") and result["session"]["state"] == "unknown" else 0
