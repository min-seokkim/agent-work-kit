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

from .review import _probe, git, toplevel

HISTORY = 50


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


def commit_identity(folder, message=None, rev=None, history=HISTORY):
    """Compare a commit's author and trailers with the repository's recent commits.

    With `rev`, the commit is read from the repository and compared with the commits before it.
    Otherwise the author is the one Git would use now and the message is `message`, as in a
    commit-msg hook. A repository without earlier commits has nothing to compare with and passes.
    Authors and trailer keys can be allowed with `git config --add awkit.allowAuthor EMAIL` and
    `git config --add awkit.allowTrailer KEY`.
    """
    top, has_commit = _repository(folder)
    if rev is not None:
        author = git(top, "log", "-1", "--format=%an <%ae>", rev)
        email = git(top, "log", "-1", "--format=%ae", rev).lower()
        message = git(top, "log", "-1", "--format=%B", rev)
        parents = git(top, "log", "-1", "--format=%P", rev).split()
        base = parents[0] if parents else None
    else:
        ident = git(top, "var", "GIT_AUTHOR_IDENT")
        match = re.match(r"(.*?) <([^>]*)>", ident)
        author = f"{match.group(1)} <{match.group(2)}>" if match else ident
        email = (match.group(2) if match else "").lower()
        base = "HEAD" if has_commit else None
    report = {"author": author, "trailers": trailer_keys(top, message or ""), "compared_commits": 0,
              "problems": []}
    if base is None:
        report["ok"] = True
        return report
    hashes = git(top, "log", f"-n{history}", "--format=%H", base).split()
    report["compared_commits"] = len(hashes)
    emails = set(git(top, "log", f"-n{history}", "--format=%ae", base).lower().split())
    emails.update(_config_values(top, "awkit.allowauthor"))
    known = {key.lower() for key in _config_values(top, "awkit.allowtrailer")}
    for commit in hashes:
        known.update(key.lower() for key in trailer_keys(top, git(top, "log", "-1", "--format=%B", commit)))
    if email not in emails:
        recent = ", ".join(sorted(emails)) or "none"
        report["problems"].append(
            f"The author {author} has not committed here before (recent authors: {recent}). If an agent set "
            "this identity, commit as the person the repository belongs to; to allow a new contributor, run "
            "`git config --add awkit.allowAuthor EMAIL`.")
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
    ("lead-in", re.compile(r"(?i)\bhere(?:'s|’s| is| are)\b"), "lead-in: start with the point"),
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


def writing_files(paths):
    files = []
    for path in map(Path, paths):
        if path.is_dir():
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


def current_tree(top):
    """The tree of HEAD plus every change in the working tree, untracked files included and `.awkit`
    excluded, written without touching the real index."""
    with tempfile.TemporaryDirectory(prefix="awkit-index-") as temporary:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        git(top, "read-tree", "HEAD", env=env)
        git(top, "add", "-A", "--", ".", ":(exclude).awkit", env=env)
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


def done(folder, runs_root=None, session=None, mark=False):
    """Whether the current state may be reported as done.

    `mark` records the current state as the session's starting point. Otherwise the state passes
    when nothing changed since that starting point (or, with none recorded, since HEAD), or when a
    passing `awkit review check` run checked exactly this state.
    """
    top = toplevel(folder)
    tree = current_tree(top)
    baseline_path = _baseline_path(top, session)
    if mark:
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
    if report["status"] == "unchanged":
        return f"nothing changed since {report['since']}"
    if report["status"] == "checked":
        return f"the current state passed its checks: {report['run_dir']}"
    shown = ", ".join(report["changed"][:20]) + (" ..." if len(report["changed"]) > 20 else "")
    return (f"Files changed since {report['since']} have no passing check of their current state: {shown}. "
            "Snapshot them and run `awkit review check` before reporting the work as done, or say in the report "
            "that it is unchecked and why.")


def git_hook_path(top):
    hooks = Path(git(top, "rev-parse", "--git-path", "hooks"))
    return (hooks if hooks.is_absolute() else top / hooks) / "commit-msg"


def install_hooks(folder, python, use_git=True, use_claude=False):
    """Install the commit identity hook for Git and the done check for Claude Code.

    The Git hook goes to the repository's hooks folder and an existing hook is kept. The Claude Code
    hooks go to .claude/settings.local.json, which stays on this machine, because both hooks name
    this machine's Python interpreter. Returns (written, kept)."""
    top, _ = _repository(folder)
    written, kept = [], []
    command = f'"{Path(python).as_posix()}" -m awkit'
    if use_git:
        hook = git_hook_path(top)
        if hook.exists():
            kept.append(str(hook))
        else:
            hook.parent.mkdir(parents=True, exist_ok=True)
            hook.write_text(f'#!/bin/sh\nexec {command} check commit --message "$1"\n', encoding="utf-8",
                            newline="\n")
            hook.chmod(0o755)
            written.append(str(hook))
    if use_claude:
        path = top / ".claude" / "settings.local.json"
        settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        hooks = settings.setdefault("hooks", {})
        changed = False
        for event in ("SessionStart", "Stop"):
            entries = hooks.setdefault(event, [])
            if any("awkit check done" in h.get("command", "") for e in entries for h in e.get("hooks", [])):
                continue
            entries.append({"hooks": [{"type": "command", "command": f"{command} check done --hook"}]})
            changed = True
        if changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
            written.append(str(path))
        else:
            kept.append(str(path))
    return written, kept
