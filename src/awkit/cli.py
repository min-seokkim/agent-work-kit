"""Command-line entry points."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .channel import Channel, KINDS, ROLES, render
from .kit_install import install, install_roles
from .pipeline import Pipeline, StepError
from .publish import Publisher
from .review import snapshot, check as run_checks


def _parser():
    parser = argparse.ArgumentParser(prog="awkit", description="Agent Work Kit: 작업 지침, 한국어 작성 가이드와 검증 도구")
    parser.add_argument("--version", action="version", version=f"awkit {__version__}")
    groups = parser.add_subparsers(dest="group", required=True)

    kit = groups.add_parser("kit", help="공통 개발 키트를 프로젝트에 복사")
    kit_commands = kit.add_subparsers(dest="action", required=True)
    init = kit_commands.add_parser("init", help="키트 폴더를 새로 만듭니다. 기존 폴더는 덮어쓰지 않습니다.")
    init.add_argument("dir", nargs="?", type=Path, default=Path("."), help="키트를 둘 프로젝트 폴더")
    init.add_argument("--name", default="agent-work-kit", help="만들 폴더 이름 (기본값: agent-work-kit)")
    roles = kit_commands.add_parser("roles", help="역할 양식으로 Claude Code나 Codex의 역할 파일을 만듭니다. 기존 파일은 덮어쓰지 않습니다.")
    roles.add_argument("dir", nargs="?", type=Path, default=Path("."), help="역할 파일을 둘 프로젝트 폴더")
    roles.add_argument("--provider", choices=("claude", "codex"), required=True)
    roles.add_argument("--model", action="append", metavar="등급=모델[:추론수준]",
                       help="등급(efficient, standard, judge, top)별 모델. 여러 번 지정할 수 있습니다.")

    usage = groups.add_parser("usage", help="Claude Code와 Codex 실행 기록에서 실제 모델과 토큰을 모읍니다.")
    usage.add_argument("paths", nargs="+", type=Path, help="실행 기록 파일(.jsonl)이나 폴더")
    usage.add_argument("--since", help="이 날짜(YYYY-MM-DD, UTC) 이후에 바뀐 파일만 읽습니다.")
    usage.add_argument("--json", action="store_true")

    channel = groups.add_parser("channel", help="로컬 에이전트 검토 채널")
    channel.add_argument("--db", type=Path, default=Path(".awkit/channel.sqlite3"))
    commands = channel.add_subparsers(dest="action", required=True)
    post = commands.add_parser("post", help="메시지를 기록합니다. 본문은 표준 입력, --body나 --body-file로 받습니다.")
    post.add_argument("sender", choices=ROLES)
    post.add_argument("receiver", choices=ROLES)
    post.add_argument("kind", choices=KINDS)
    post.add_argument("--reply-to")
    post.add_argument("--snap")
    body = post.add_mutually_exclusive_group()
    body.add_argument("--body", help="본문 문자열")
    body.add_argument("--body-file", type=Path, help="UTF-8 본문 파일")
    wait = commands.add_parser("wait", help="메시지를 기다립니다.")
    wait.add_argument("role", choices=ROLES)
    wait.add_argument("mode", choices=("request", "new", "reply"))
    wait.add_argument("target", nargs="?")
    wait.add_argument("--max", type=float, default=120)
    wait.add_argument("--json", action="store_true")
    export = commands.add_parser("export", help="전체 채널을 출력합니다.")
    export.add_argument("--json", action="store_true")

    pipeline = groups.add_parser("pipeline", help="프로젝트 명령으로 배포하고 결과를 확인")
    pipeline.add_argument("--config", type=Path, required=True)
    pipeline.add_argument("action", choices=("plan", "deploy", "rollback", "status", "reconcile", "history"))
    pipeline.add_argument("release", nargs="?")
    pipeline.add_argument("--allow-unhealthy-current", action="store_true",
                          help="현재 버전의 검사가 실패한 상태에서도 배포합니다. 고친 버전을 올릴 때 사용합니다.")
    pipeline.add_argument("--json", action="store_true")

    review = groups.add_parser("review", help="고정된 변경본을 만들고 별도 작업 폴더에서 검사")
    review.add_argument("--repo", type=Path, default=Path.cwd())
    review_commands = review.add_subparsers(dest="action", required=True)
    freeze = review_commands.add_parser("snapshot", help="선택한 파일의 변경을 담은 Git 객체를 만듭니다.")
    freeze.add_argument("files", nargs="+")
    isolated = review_commands.add_parser("check", help="고정된 버전을 별도 worktree에서 검사합니다.")
    isolated.add_argument("snapshot")
    isolated.add_argument("--config", type=Path, required=True)
    isolated.add_argument("--runs-root", type=Path)
    isolated.add_argument("--keep", action="store_true")

    publish = groups.add_parser("publish", help="정적 문서 결과물을 검사한 뒤 로컬 발행")
    publish.add_argument("--output", type=Path, required=True)
    publish.add_argument("--project", required=True)
    publications = publish.add_subparsers(dest="action", required=True)
    build = publications.add_parser("build")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--files", type=Path, required=True, help="발행할 상대 파일 경로의 JSON 배열")
    restore = publications.add_parser("restore")
    restore.add_argument("version")

    ui = groups.add_parser("ui", help="지정한 화면을 여러 폭으로 캡처")
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
    print(f"대상: {report['target']}\n배포 버전: {report['release']}")
    for check in report["checks"]:
        print(f"{check['name']}: {'통과' if check['ok'] else '실패'}")


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
                print(f"만들었습니다: {path}")
            for path in skipped:
                print(f"이미 있어 건너뛰었습니다: {path}")
            for warning in warnings:
                print(f"주의: {warning}", file=sys.stderr)
            return 0 if written or not skipped else 2
        if args.group == "usage":
            from datetime import datetime, timezone
            from .usage import collect, render as render_usage
            since = None
            if args.since:
                since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            result = collect(args.paths, since)
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_usage(result))
            return 0
        if args.group == "kit":
            target, copied = install(args.dir, args.name)
            print(f"키트를 만들었습니다: {target}\n복사한 파일 {len(copied)}개")
            print(f"다음 단계: {target / 'README.md'}를 열어 적용표부터 채우세요.")
            return 0
        if args.group == "review":
            if args.action == "snapshot":
                print(snapshot(args.repo, args.files))
                return 0
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
                    raise ValueError("허용 파일 목록은 문자열의 JSON 배열이어야 합니다.")
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
                print("메인이 작업 종료를 알렸습니다.")
            return code
        if (args.action == "deploy") != bool(args.release):
            parser.error("deploy에만 고정된 버전을 지정하세요.")
        if args.allow_unhealthy_current and args.action != "deploy":
            parser.error("--allow-unhealthy-current는 deploy에만 사용할 수 있습니다.")
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
                print("검사를 통과한 배포 이력이 없습니다.")
            for index, release in enumerate(reversed(releases)):
                print(f"{release}{'  (가장 최근)' if index == 0 else ''}")
        else:
            print(f"실행 결과: {result.get('status')}")
            failure = result.get("failure")
            if failure:
                detail = ", ".join(failure.get("failed_checks", []))
                print(f"실패 단계: {failure['phase']}" + (f" ({detail})" if detail else ""))
            if result.get("run_id"):
                print(f"기록: {runner.state / 'runs' / result['run_id']}")
        return 0 if success else 1
    except StepError as exc:
        print(f"확인 실패: {exc}", file=sys.stderr)
        return exc.code if 1 <= exc.code <= 125 else 1
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
        print(f"실행할 수 없습니다: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("중단했습니다. 실행 기록과 대상 상태를 확인하세요.", file=sys.stderr)
        return 130
