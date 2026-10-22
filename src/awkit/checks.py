"""Checks that run without the agent choosing to: commit identity, writing patterns and done reports.

Each check guards a failure recorded in the repository's failure catalogue: commits authored as the
agent or carrying trailers the project never uses (F9), writing patterns readers recognize as
generated (F13, F14, F32), and work reported as done without a passing check of the delivered state
(F1).
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .identity import author_problem
from .review import _probe, git, nested_repositories, nested_warning, toplevel

HISTORY = 50

# The failure catalogue entries (kit/failures.md) each command guards against.
PREVENTS = {"awkit check commit": ("F9",), "awkit check writing": ("F13", "F14", "F32"), "awkit check done": ("F1",),
            "awkit kit hooks": ("F1", "F9")}


def _repository(folder):
    """(top level, has a commit) for a folder inside a Git repository."""
    probe = _probe(Path(folder).resolve(), "rev-parse", "--show-toplevel")
    if probe.returncode:
        raise ValueError(f"Not a Git repository: {folder}")
    top = Path(probe.stdout.strip())
    return top, not _probe(top, "rev-parse", "--verify", "-q", "HEAD^{commit}").returncode


def _config_values(top, key):
    probe = _probe(top, "config", "--get-all", key)
    return [line.strip().lower() for line in probe.stdout.splitlines() if line.strip()]


def trailer_keys(top, message):
    """The trailer keys Git finds in a commit message, comment lines removed."""
    text = "\n".join(line for line in message.splitlines() if not line.startswith("#"))
    result = subprocess.run(["git", "-C", str(top), "interpret-trailers", "--parse"], input=text,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    keys = []
    for line in result.stdout.splitlines():
        key = line.split(":", 1)[0].strip()
        if key and key.lower() not in (k.lower() for k in keys):
            keys.append(key)
    return keys


def commit_identity(folder, message=None, rev=None, history=HISTORY, author=None):
    """Compare a commit's author and trailers with the repository's recent commits.

    With `rev`, the commit is read from the repository and compared with the commits before it.
    Otherwise the author is `author` as (name, email), by default the one Git would use now, and the
    message is `message`, as in a commit-msg hook or before `git commit` runs. A repository without
    earlier commits has nothing to compare with and passes.
    Authors and trailer keys can be allowed with `git config --add awkit.allowAuthor EMAIL` and
    `git config --add awkit.allowTrailer KEY`.
    """
    top, has_commit = _repository(folder)
    if rev is not None:
        name = git(top, "log", "-1", "--format=%an", rev)
        email = git(top, "log", "-1", "--format=%ae", rev)
        message = git(top, "log", "-1", "--format=%B", rev)
        parents = git(top, "log", "-1", "--format=%P", rev).split()
        base = parents[0] if parents else None
    else:
        if author:
            name, email = author
        else:
            ident = git(top, "var", "GIT_AUTHOR_IDENT")
            match = re.match(r"(.*?) <([^>]*)>", ident)
            name, email = (match.group(1), match.group(2)) if match else (ident, "")
        base = "HEAD" if has_commit else None
    report = {"author": f"{name} <{email}>", "trailers": trailer_keys(top, message or ""), "compared_commits": 0,
              "problems": []}
    problem = author_problem(top, name, email, base, history)
    if problem:
        report["problems"].append(problem)
    if base is None:
        report["ok"] = not report["problems"]
        return report
    hashes = git(top, "log", f"-n{history}", "--format=%H", base).split()
    report["compared_commits"] = len(hashes)
    known = {key.lower() for key in _config_values(top, "awkit.allowtrailer")}
    for commit in hashes:
        known.update(key.lower() for key in trailer_keys(top, git(top, "log", "-1", "--format=%B", commit)))
    for key in report["trailers"]:
        if key.lower() not in known:
            report["problems"].append(
                f"The trailer `{key}` does not appear in this repository's recent commits. Remove it unless the "
                "owner asked for it; to allow it, run `git config --add awkit.allowTrailer KEY`.")
    report["ok"] = not report["problems"]
    return report


# Patterns from kit/writing.md and kit/korean-writing.md. Errors are wrong on one sighting; warnings
# need a reader's judgment, since a listed word can be the right one.
ERRORS = (
    ("em-dash", re.compile("—"), "em dash: use a comma, colon, period or parentheses"),
    ("middle-dot", re.compile(r"[가-힣]\s*[·・]\s*[가-힣]"),
     "middle dot joining Korean words: say the relationship in a sentence or a list"),
)
WARNINGS = (
    # Only at the start of a sentence: "whether it happens here is" is not a lead-in.
    ("lead-in", re.compile(r"(?i)(?:^|[.!?:]\s+|^\s*[-*]\s+)here(?:'s|’s| is| are)\b"), "lead-in: start with the point"),
    ("contrast", re.compile(r"(?i)\b(?:not just|isn't just|isn’t just|is not about|isn't about)\b"),
     "contrast against a claim nobody made: state the point directly"),
    ("sales-word", re.compile(r"(?i)\b(?:seamless(?:ly)?|robust|leverag\w*|cutting-edge|game-chang\w*|unlock\w*"
                              r"|empower\w*|delve\w*|revolutioni[sz]\w*|supercharg\w*|effortless(?:ly)?)\b"),
     "sales word: say what it does"),
    ("translationese", re.compile(r"에 있어서|되어지|가지고 있다|시사하는 바|주목할 만|결론적으로|혁신적"),
     "translation artifact or stock phrase: say what happens"),
)
POLITE = re.compile(r"세요[.!?]?(?=\s|$|[)\]\"'”’])")
FORMAL = re.compile(r"(?:십시오|시오)[.!?]?(?=\s|$|[)\]\"'”’])")
SKIP_DIRS = {"build", "dist", "node_modules", "site-packages", "__pycache__"}
MASKS = (re.compile(r"`[^`\n]*`"), re.compile(r"\"[^\"\n]*\""), re.compile(r"“[^”\n]*”"),
         re.compile(r"‘[^’\n]*’"), re.compile(r"\]\([^)\n]*\)"), re.compile(r"<!--.*?-->"))


def _prose_lines(text):
    """(line number, text) for prose lines: code blocks, blockquotes, inline code, quoted spans
    and link targets are blanked, since the patterns apply to the author's own prose only."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if marker:
            if fence is None:
                fence = marker.group(1)[0]
            elif marker.group(1)[0] == fence:
                fence = None
            continue
        if fence is not None or stripped.startswith(">"):
            continue
        for mask in MASKS:
            line = mask.sub(lambda m: " " * len(m.group(0)), line)
        yield number, line


def _tracked_markdown(folder):
    """Markdown files Git tracks or would track under `folder`, or None outside a repository. Git skips
    ignored folders and does not descend into another repository, such as a clone inside the project."""
    probe = _probe(folder, "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", ".")
    if probe.returncode:
        return None
    names = {name for name in probe.stdout.split("\0") if name.endswith(".md")}
    return [folder / name for name in sorted(names) if (folder / name).is_file()]


def writing_files(paths):
    files = []
    for path in map(Path, paths):
        listed = _tracked_markdown(path) if path.is_dir() else None
        if listed is not None:
            files.extend(listed)
        elif path.is_dir():
            for found in sorted(path.rglob("*.md")):
                parts = found.relative_to(path).parts[:-1]
                if not any(part.startswith(".") or part in SKIP_DIRS for part in parts):
                    files.append(found)
        elif path.is_file():
            files.append(path)
        else:
            raise ValueError(f"No such file or folder: {path}")
    return files


def check_text(text):
    findings = []
    polite, formal = [], []
    for number, line in _prose_lines(text):
        for level, patterns in (("error", ERRORS), ("warning", WARNINGS)):
            for name, pattern, advice in patterns:
                for match in pattern.finditer(line):
                    findings.append({"line": number, "level": level, "pattern": name, "advice": advice,
                                     "text": line[max(0, match.start() - 30):match.end() + 30].strip()})
        if POLITE.search(line):
            polite.append(number)
        if FORMAL.search(line):
            formal.append(number)
    if polite and formal:
        findings.append({"line": formal[0], "level": "error", "pattern": "mixed-endings",
                         "advice": f"-세요 (line {polite[0]}) and -시오 (line {formal[0]}) endings in one document: "
                                   "use one style throughout", "text": ""})
    return sorted(findings, key=lambda f: (f["line"], f["level"]))


def check_writing(paths):
    report = {"files": 0, "errors": 0, "warnings": 0, "findings": []}
    for path in writing_files(paths):
        report["files"] += 1
        for finding in check_text(path.read_text(encoding="utf-8", errors="replace")):
            finding["path"] = path.as_posix()
            report["findings"].append(finding)
            report["errors" if finding["level"] == "error" else "warnings"] += 1
    report["ok"] = not report["errors"]
    return report


def render_writing(report):
    lines = [f"{f['path']}:{f['line']}: {f['level']} [{f['pattern']}] {f['advice']}"
             + (f": {f['text']}" if f["text"] else "") for f in report["findings"]]
    lines.append(f"{report['files']} files, {report['errors']} errors, {report['warnings']} warnings")
    return "\n".join(lines)


def current_tree(top, exclude=()):
    """The tree of HEAD plus every change in the working tree, untracked files included, without the
    LOCAL_ONLY files and the `exclude` paths, written without touching the real index."""
    with tempfile.TemporaryDirectory(prefix="awkit-index-") as temporary:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        git(top, "read-tree", "HEAD", env=env)
        # Naming an ignored path in a pathspec is an error for git add, so local-only files are dropped after.
        git(top, "add", "-A", "--", ".", *(f":(exclude){path}" for path in exclude), env=env)
        git(top, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *LOCAL_ONLY, env=env)
        return git(top, "write-tree", env=env)


def _baseline_path(top, session):
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "default")[:120]
    return top / ".awkit" / "done" / f"{name}.json"


def _run_roots(top, runs_root):
    roots = [Path(runs_root)] if runs_root else []
    roots += [top / ".awkit" / "reviews", Path(tempfile.gettempdir()) / "agent-work-kit-reviews"]
    return [root for root in dict.fromkeys(r.resolve() for r in roots) if root.is_dir()]


def passing_run(top, tree, runs_root=None, limit=500):
    """The most recent passing run whose snapshot has exactly `tree`, or None."""
    results = []
    for root in _run_roots(top, runs_root):
        results.extend(root.glob("*/result.json"))
    results.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in results[:limit]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if record.get("status") != "passed" or not isinstance(record.get("snapshot"), str):
            continue
        probe = _probe(top, "rev-parse", "--verify", "-q", record["snapshot"] + "^{tree}")
        if not probe.returncode and probe.stdout.strip() == tree:
            return str(path.parent)
    return None


def done(folder, runs_root=None, session=None, mark=False, replace=True):
    """Whether the current state may be reported as done.

    `mark` records the current state as the session's starting point; with `replace` false an
    existing starting point is kept, because a resumed or compacted session continues the same work.
    Otherwise the state passes
    when nothing changed since that starting point (or, with none recorded, since HEAD), or when a
    passing `awkit review check` run checked exactly this state.
    """
    top = toplevel(folder)
    # Another repository inside the project is not supported. Git cannot add one that has no commit,
    # so it stays out of the state, and its presence alone fails the check with the reason.
    nested = nested_repositories(top)
    tree = current_tree(top, [entry["path"] for entry in nested])
    baseline_path = _baseline_path(top, session)
    if mark:
        if not replace and baseline_path.is_file():
            return {"ok": True, "status": "kept", "tree": tree}
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps({"tree": tree}), encoding="utf-8")
        return {"ok": True, "status": "marked", "tree": tree}
    try:
        base = json.loads(baseline_path.read_text(encoding="utf-8"))["tree"]
        since = "the session started"
    except (OSError, ValueError, KeyError):
        base = git(top, "rev-parse", "HEAD^{tree}")
        since = "the last commit"
    report = {"tree": tree, "since": since}
    if nested:
        return {**report, "ok": False, "status": "nested-repository", "nested": nested, "changed": []}
    if tree == base:
        return {**report, "ok": True, "status": "unchanged"}
    run = passing_run(top, tree, runs_root)
    if run:
        return {**report, "ok": True, "status": "checked", "run_dir": run}
    changed = git(top, "diff", "--name-only", base, tree).splitlines()
    return {**report, "ok": False, "status": "unchecked", "changed": changed}


def render_done(report):
    if report["status"] == "marked":
        return "recorded the current state as this session's starting point"
    if report["status"] == "kept":
        return "kept the starting point recorded earlier in this session"
    if report["status"] == "unchanged":
        return f"nothing changed since {report['since']}"
    if report["status"] == "checked":
        return f"the current state passed its checks: {report['run_dir']}"
    if report["status"] == "nested-repository":
        return "\n".join(nested_warning(entry) for entry in report["nested"])
    shown = ", ".join(report["changed"][:20]) + (" ..." if len(report["changed"]) > 20 else "")
    return (f"Files changed since {report['since']} have no passing check of their current state: {shown}. "
            "Snapshot them and run `awkit review check` before reporting the work as done, or say in the report "
            "that it is unchecked and why.")


def git_hook_path(top):
    hooks = Path(git(top, "rev-parse", "--git-path", "hooks"))
    return (hooks if hooks.is_absolute() else top / hooks) / "commit-msg"


GIT_HOOK = """#!/bin/sh
# Installed by `awkit kit hooks --git`: compare the commit's author and trailers with this repository's history.
# awkit is found by name, so the hook keeps working when awkit is reinstalled or its environment moves.
if command -v awkit >/dev/null 2>&1; then
    exec awkit check commit --message "$1"
fi
for python in python3 python; do
    if "$python" -c "import awkit" >/dev/null 2>&1; then
        exec "$python" -m awkit check commit --message "$1"
    fi
done
echo "awkit was not found; the commit identity check did not run." >&2
"""
CLAUDE_DONE_HOOK = "if command -v awkit >/dev/null 2>&1; then awkit check done --hook; fi"
# Files a tool keeps on one machine; they are never part of the work being checked.
LOCAL_ONLY = (".awkit", ".claude/settings.local.json", "CLAUDE.local.md")


def install_hooks(folder, python=None, use_git=True, use_claude=False, use_codex=False):
    """Install the commit identity hook for Git and the hook runner for Claude Code and Codex.

    The Git hook goes to the repository's hooks folder. The agents' hooks go to their project settings,
    `.claude/settings.json` and `.codex/hooks.json`, and run `awkit hook`, which applies the project's
    rules.toml; the kit's example rules are written there when the project has none. Everything calls
    awkit by name, so the files can be committed. Existing hooks are kept; the done-check entries an
    earlier awkit wrote to .claude/settings.local.json are removed, since the rules run that check now.
    `python` is accepted for compatibility and not used. Returns (written, kept)."""
    from .hooks import install_rules, install_settings, remove_entries
    top, _ = _repository(folder)
    written, kept = [], []
    if use_git:
        hook = git_hook_path(top)
        if hook.exists():
            kept.append(str(hook))
        else:
            hook.parent.mkdir(parents=True, exist_ok=True)
            hook.write_text(GIT_HOOK, encoding="utf-8", newline="\n")
            hook.chmod(0o755)
            written.append(str(hook))
    providers = [name for name, chosen in (("claude", use_claude), ("codex", use_codex)) if chosen]
    for provider in providers:
        path, changed = install_settings(top, provider)
        (written if changed else kept).append(str(path))
    if use_claude:
        local = top / ".claude" / "settings.local.json"
        if remove_entries(local, CLAUDE_DONE_HOOK):
            written.append(str(local))
    if providers:
        path, created = install_rules(top)
        (written if created else kept).append(str(path))
    return written, kept
