"""Whether a commit author fits a repository: the rule shared by `check commit`, `doctor` and `kit init`.

An author fits when they have committed to the repository before and their identity is not a coding
agent's. awkit's own identities, used for commits awkit makes in a repository with no history, do not
count as history, so the owner's first commit after `kit init` is not reported.
"""

import os
import subprocess

AWKIT_EMAILS = {"awkit@localhost", "snapshot@localhost"}
AGENT_DOMAINS = ("anthropic.com", "openai.com", "cursor.com", "cursor.sh")
AGENT_NAMES = {"claude", "claude code", "codex", "cursor agent", "copilot", "github copilot"}
HISTORY = 50


def _git(top, *args):
    result = subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    return result.stdout.strip() if result.returncode == 0 else ""


def configured(top):
    """(name, email) Git would use for a new commit, or None when either is not set."""
    name = os.environ.get("GIT_AUTHOR_NAME") or _git(top, "config", "user.name")
    email = os.environ.get("GIT_AUTHOR_EMAIL") or _git(top, "config", "user.email")
    return (name, email) if name and email else None


def agent_like(name, email):
    email = email.lower()
    return name.strip().lower() in AGENT_NAMES or any(email.endswith("@" + d) or email.endswith("." + d)
                                                      for d in AGENT_DOMAINS)


def history_authors(top, base="HEAD", history=HISTORY):
    """Emails of the recent authors before `base`, without awkit's own, plus `awkit.allowAuthor` entries."""
    found = set(_git(top, "log", f"-n{history}", "--format=%ae", base).lower().split()) if base else set()
    allowed = {line.strip().lower() for line in _git(top, "config", "--get-all", "awkit.allowauthor").splitlines()}
    return (found - AWKIT_EMAILS) | {a for a in allowed if a}, allowed


def author_problem(top, name, email, base="HEAD", history=HISTORY):
    """None when the author fits the repository, otherwise the reason and how to fix it."""
    authors, allowed = history_authors(top, base, history)
    if email.lower() in allowed:
        return None
    reasons = []
    if agent_like(name, email):
        reasons.append("looks like a coding agent's identity")
    if authors and email.lower() not in authors:
        reasons.append(f"has not committed here before (recent authors: {', '.join(sorted(authors))})")
    if not reasons:
        return None
    return (f"The author {name} <{email}> " + " and ".join(reasons) + ". Commit as the person the repository "
            "belongs to (git config user.name and user.email); to allow this author, run "
            "`git config --add awkit.allowAuthor EMAIL`.")
