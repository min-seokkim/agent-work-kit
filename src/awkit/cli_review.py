"""The review commands."""

import json
from pathlib import Path

from .cli_common import REFERENCE


def add(groups):
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
    isolated.add_argument("--runs-root", type=Path, help="where run folders are kept (default: .awkit/reviews in the repository, excluded from Git locally)")
    isolated.add_argument("--keep", action="store_true", help="keep the worktree after a normal finish")
    preview = review_commands.add_parser("preview", help="preview current artifact paths and sizes without running checks; exit 0 complete, 1 partial, 2 invalid")
    preview.add_argument("--config", type=Path, required=True, help="checks TOML; observe current files before setup and checks")
    preview.add_argument("--json", action="store_true", help="print paths, patterns, logical sizes and observation limits as JSON")
    storage = review_commands.add_parser("storage", help="inspect existing review storage without changing files; exit 0 complete, 1 partial, 2 unavailable")
    storage.add_argument("--runs-root", type=Path, help="existing run store (default: repository .awkit/reviews)")
    storage_output = storage.add_mutually_exclusive_group()
    storage_output.add_argument("--json", action="store_true", help="print observed sizes, metadata coverage and unverified hash accounting as JSON")
    storage_output.add_argument("--summary", action="store_true", help="print totals, coverage, issue counts and limitations; omit individual rows/details")
    confirm = review_commands.add_parser("verify", help="rehash a run's retained artifacts against its manifest; exit 0 when all match")
    confirm.add_argument("run_dir", type=Path, help="run folder printed by `review check`")
    export = review_commands.add_parser("export", help="export verified run evidence as independent ordinary files")
    export.add_argument("run_dir", type=Path, help="complete run folder to export")
    export.add_argument("--output", type=Path, required=True, help="new bundle directory; must not exist")
    keep = review_commands.add_parser("accept", help="keep a verified run's artifacts as the accepted version")
    keep.add_argument("run_dir", type=Path, help="run folder printed by `review check`")
    keep.add_argument("--label", default="accepted", help="name of the accepted version (default: accepted)")
    against = review_commands.add_parser("compare", help="compare the working tree, or a run's artifacts, with the accepted "
                                         "version; exit 0 when accepted files are unchanged")
    against.add_argument("--label", default="accepted", help="accepted version to compare with (default: accepted)")
    against.add_argument("--run", type=Path, help="compare this run folder's retained artifacts instead of the working tree")
    against.add_argument("--diff", action="store_true", help="include a unified diff for changed text files")
    against.add_argument("--include-added", action="store_true",
                         help="list recorded added paths separately; requires --run; no content verification or effect on exit 0/1")


def run(args, parser):
    # Imported here, not at the top, so `awkit hook` does not load them on every tool call.
    from .review import accept, compare, snapshot
    from .review import check as run_checks
    from .review import verify as verify_run
    if args.action == "preview":
        from .review_selection import preview, text
        report = preview(args.repo, args.config)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else text(report))
        return 0 if report["complete"] else 1
    if args.action == "storage":
        from .review import storage
        from .review_storage import text
        report = storage(args.repo, args.runs_root)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else text(report, summary=args.summary))
        return 0 if report["complete"] else 1
    if args.action == "snapshot":
        print(snapshot(args.repo, args.files))
        return 0
    if args.action == "verify":
        report = verify_run(args.run_dir)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["verified"] else 1
    if args.action == "export":
        from .review_export import export_run
        print(json.dumps(export_run(args.run_dir, args.output), ensure_ascii=False, indent=2))
        return 0
    if args.action == "accept":
        print(json.dumps(accept(args.repo, args.run_dir, args.label), ensure_ascii=False, indent=2))
        return 0
    if args.action == "compare":
        report = compare(args.repo, args.label, args.run, args.diff, args.include_added)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["unchanged"] else 1
    result = run_checks(args.repo, args.snapshot, args.config, args.runs_root, args.keep)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1
