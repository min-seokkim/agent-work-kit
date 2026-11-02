"""The kit commands: add the kit to a project, examples, scan, roles, skills and removal."""

import json
import sys
from pathlib import Path

from .cli_common import REFERENCE
from .kit_install import EXAMPLES, install, install_example, install_roles, install_skills


def add(groups):
    kit = groups.add_parser("kit", help="add the kit to a project, create examples, scan a project, write role files, "
                            "skills and hooks",
                            epilog=REFERENCE)
    kit_commands = kit.add_subparsers(dest="action", required=True, metavar="ACTION")
    init = kit_commands.add_parser("init", help="install the project layer: checks.toml with the [kit] table, the hooks "
                                   "through `kit hooks`, .awkit/ excluded from Git; nothing is committed or copied")
    init.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder that receives the kit (default: .)")
    init.add_argument("--copy", action="store_true",
                      help="copy the whole kit folder instead, as earlier versions did; an existing folder is never "
                           "touched (exit 2)")
    init.add_argument("--name", default="agent-work-kit", help="with --copy, the folder to create (default: agent-work-kit)")
    init.add_argument("--commit", action="store_true",
                      help="also commit what it wrote, in an existing repository: checks.toml and rules.toml, or with "
                           "--copy the new folder; by default nothing is committed")
    init.add_argument("--no-git", action="store_true", help="leave Git alone: no hooks, no exclude line and no commit")
    remove = kit_commands.add_parser("remove", help="take out what init, skills and hooks added, leaving the project "
                                     "or the user folder as it was before")
    remove.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder (default: .)")
    remove.add_argument("--user", action="store_true", help="delete awkit's skills from the user's skill folders")
    remove.add_argument("--project", action="store_true",
                        help="restore the project: the [kit] table, the exclude line, and the hooks and rules.toml "
                             "through `kit hooks --remove` (the default when --user is not given)")
    records = remove.add_mutually_exclusive_group()
    records.add_argument("--keep-records", action="store_true", help="keep the check runs and logs in .awkit/")
    records.add_argument("--delete-records", action="store_true", help="delete .awkit/ with the check runs and logs")
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
    skills = kit_commands.add_parser("skills", help="write the workflow and each situation guide as a skill in your user "
                                     "folder for Claude Code and Codex; awkit's earlier skills are regenerated, other "
                                     "files are kept")
    skills.add_argument("dir", nargs="?", type=Path, default=Path("."), help="project folder, with --project (default: .)")
    skills.add_argument("--provider", choices=("claude", "codex"),
                        help="only this agent (default: both): claude writes ~/.claude/skills/awkit-*/SKILL.md, codex "
                             "~/.agents/skills/awkit-*/SKILL.md")
    skills.add_argument("--without", action="append", default=[], metavar="NAMES",
                        help="leave out these skills, comma-separated, such as delegation,review-session")
    skills.add_argument("--project", action="store_true",
                        help="write into DIR/.claude/skills and DIR/.agents/skills instead of the user folder")
    skills.add_argument("--kit", type=Path, help="with --project: point the skills at this kit folder inside the "
                        "project instead of holding the guides (default: DIR/agent-work-kit when it exists)")
    kit_commands.add_parser("guide", help="print a kit guide; without a name, list them").add_argument("name", nargs="?")
    return kit_commands


COMMITTED = ("checks.toml", "rules.toml")


def _report_tracking(record, what="the new folder"):
    if record["created"]:
        print(f"initialized a Git repository: {record['repository']}")
    if record["committed"]:
        print(f"committed {what} in {record['repository']}")
    else:
        print(f"note: {what} was not committed ({record['skipped']}); commit it before `awkit review check`",
              file=sys.stderr)


def _print_skills(result, indent=""):
    for key, label in (("created", "created"), ("updated", "regenerated"), ("kept", "kept existing file")):
        for path in result[key]:
            print(f"{indent}{label}: {path}")
    for name, reason in result["omitted"]:
        print(f"{indent}left out {name}: {reason}")


def _guide(name):
    from .kit_install import guide, guide_files
    if not name:
        print("\n".join(sorted(guide_files())))
        return 0
    sys.stdout.write(guide(name))
    return 0


def _skills(args):
    """`kit skills`: the user folders by default, the project's with --project (or --kit)."""
    from .connect import Changes, project_top
    from .kit_install import install_user_skills, skill_names
    providers = (args.provider,) if args.provider else ("claude", "codex")
    if not (args.project or args.kit):
        results, record = install_user_skills(providers, args.without)
        written = []
        for result in results.values():
            _print_skills(result)
            for path in result["removed"]:
                print(f"removed: {path}")
            written += result["created"] + result["updated"]
        if record:
            print(f"recorded: {record} (what `awkit kit remove --user` takes out)")
        return 0 if written or not any(r["kept"] for r in results.values()) else 2
    keep, _ = skill_names(args.without)
    changes = Changes(project_top(args.dir))
    written, kept = [], []
    for provider in providers:
        result = install_skills(args.dir, provider, args.kit, changes, keep)
        _print_skills(result)
        written += result["created"] + result["updated"]
        kept += result["kept"]
    changes.save()
    return 0 if written or not kept else 2


def _git_status(top, names):
    from .review import _probe
    probe = _probe(top, "status", "--porcelain", "--", *names)
    return None if probe.returncode else [line[3:] for line in probe.stdout.splitlines()]


def _commit_init(top, dirty):
    """Commit the files of COMMITTED that `kit init` wrote, unless one already had the user's changes."""
    from .review import track
    if dirty:
        print("note: nothing was committed: " + ", ".join(dirty) + " had uncommitted changes, which a commit would "
              "bundle in; commit the kit's files yourself", file=sys.stderr)
        return
    written = _git_status(top, COMMITTED)
    if written:
        _report_tracking(track(top, [top / name for name in written], "Add Agent Work Kit"), " and ".join(written))


def _session_line(words):
    return (f"words added to every session: {words['claude']} for Claude Code, {words['codex']} for Codex "
            "(the descriptions of awkit's skills; the project's instruction files get nothing)")


# What a project commits after `kit init`; `--commit` commits those of them init wrote.


def _report_init(report, commit=False, dirty=()):
    from .connect import CHECKS, INSTRUCTION_LINE
    top = Path(report["top"])
    what = {"created": "created", "appended": "added the [kit] table to", "filled": "filled the [kit] table in",
            "kept": "kept"}[report["checks"]]
    print(f"{what}: {top / CHECKS}")
    if report["excluded"]:
        print("excluded: .awkit/ in .git/info/exclude")
    if report["hooks"]:
        arguments, code = report["hooks"]
        if code:
            print(f"note: `awkit kit hooks {' '.join(arguments)}` exited {code}; the hooks may be missing", file=sys.stderr)
    if report["record"]:
        print(f"recorded: {report['record']} (what `awkit kit remove` takes out)")
    print(_session_line(report["words"]))
    for note in report["notes"]:
        print(f"note: {note}")
    print("optional: to point agents at the kit from the project's instructions, add this line to AGENTS.md or "
          f"CLAUDE.md yourself:\n  {INSTRUCTION_LINE}")
    if commit and _git_status(top, COMMITTED) is not None:
        _commit_init(top, dirty)
        print("next: tell your agent to connect Agent Work Kit to this project (`awkit kit guide connect`)")
    else:
        print("next: tell your agent to connect Agent Work Kit to this project (`awkit kit guide connect`), then commit "
              "checks.toml and rules.toml; nothing was committed")
    return 2 if report["checks"] == "kept" and not report["excluded"] else 0


def _ask_keep_records(folder):
    """Ask whether to keep .awkit/ when it holds check runs or logs; without a terminal, keep it."""
    from .connect import awkit_records, project_top
    found = awkit_records(project_top(folder))
    if not found:
        return None
    # Windows reports the null device as a terminal, so an input that ends counts as no answer too.
    answer = None
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            answer = input(".awkit/ holds " + ", ".join(found) + ". Keep it? [Y/n] ").strip().lower()
        except EOFError:
            answer = None
    if answer is None:
        print("note: keeping .awkit/, which holds " + ", ".join(found) + "; pass --delete-records to delete it",
              file=sys.stderr)
        return True
    return answer not in ("n", "no")


def _print_remove(report):
    for path, what in report["files"]:
        print(f"{what}: {path}")
    for path in report["dirs"]:
        print(f"removed empty folder: {path}")
    if report.get("awkit_folder", "absent") != "absent":
        print(f"{report['awkit_folder']}: {Path(report['top']) / '.awkit'}")
    if report.get("hooks"):
        print(f"note: `awkit kit hooks --remove` exited {report['hooks']}; awkit's hook entries were taken out by "
              "the record and their markers instead", file=sys.stderr)
    if not report["recorded"]:
        print("note: no installed.json here, so files were found by awkit's markers; check what is left",
              file=sys.stderr)


def run(args, parser):
    if args.action == "hooks":
        from . import hook_cli
        return hook_cli.run(args, parser)
    if args.action == "guide":
        return _guide(args.name)
    if args.action == "skills":
        return _skills(args)
    if args.action == "remove":
        from .connect import remove, remove_user
        if args.user:
            _print_remove({"top": str(Path.home()), **remove_user()})
        if args.project or not args.user:
            keep = True if args.keep_records else False if args.delete_records else None
            if keep is None:
                keep = _ask_keep_records(args.dir)
            _print_remove(remove(args.dir, keep))
            print("next: commit the removal of checks.toml and rules.toml if they were committed")
        return 0
    if args.action == "roles":
        written, skipped, warnings = install_roles(args.dir, args.provider, args.model)
        for path in written:
            print(f"created: {path}")
        for path in skipped:
            print(f"kept existing file: {path}")
        for warning in warnings:
            print(f"note: {warning}", file=sys.stderr)
        return 0 if written or not skipped else 2
    if args.action == "scan":
        from .scan import scan as scan_project
        report = scan_project(args.dir)
        if not args.checks:
            words = report["session_words"]
            state = "adds" if words["measured"] else "would add"
            print(f"awkit {state} {words['claude']} words to every Claude Code session and {words['codex']} to every "
                  "Codex session here", file=sys.stderr)
        print(report["suggested_checks_toml"] if args.checks else json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    # Imported here, not at the top, so `awkit hook` does not load them on every tool call.
    from .review import track
    if args.action == "example":
        target, copied = install_example(args.kind, args.dir)
        print(f"created the {args.kind} example: {target}\ncopied {len(copied)} files")
        if not args.no_git:
            _report_tracking(track(target, [target], f"Add the {args.kind} example"))
        print(f"next: read {target / 'README.md'} and run the commands there")
        return 0
    if args.copy:
        target, copied = install(args.dir, args.name)
        print(f"created the kit: {target}\ncopied {len(copied)} files")
        if _git_status(args.dir, ()) is None:
            print(f"note: {args.dir.resolve()} is not in a Git repository; nothing was committed", file=sys.stderr)
        elif args.commit and not args.no_git:
            _report_tracking(track(args.dir, [target], f"Add {args.name}"))
        print(f"next: tell your agent to read {target / 'README.md'} and connect the kit to this project")
        return 0
    from .connect import init as connect
    from .connect import project_top
    commit = args.commit and not args.no_git
    dirty = (_git_status(project_top(args.dir), COMMITTED) or []) if commit else []
    return _report_init(connect(args.dir, git=not args.no_git), commit, dirty)
