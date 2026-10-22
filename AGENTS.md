# Instructions for agents developing this repository

This file is for agents that change Agent Work Kit itself. Agents that use the kit in another project read the skills `awkit kit skills` writes in the user folder, `awkit kit guide NAME`, or a copied `agent-work-kit/` folder, starting with [kit/README.md](kit/README.md).

## What each document is for

| Document | Reader | Read it when |
|---|---|---|
| [README.md](README.md), [README.ko.md](README.ko.md) | People | Changing what users are told |
| [kit/](kit/README.md) | Agents using the kit in their projects; shipped in the package | Changing instructions, templates or the command reference |
| [docs/development.md](docs/development.md) | Agents developing this repository | Before planning work: scope, decisions, current state, next work, release, verification record |
| [kit/failures.md](kit/failures.md) | Agents using the kit, when a guard names an entry as its reason; agents developing this repository, before adding or changing kit text, a hook or a check | Each guard must prevent a listed failure and declare it: a `Prevents:` line in a guide section, `PREVENTS` in the code of a command; then run `python scripts/guard_map.py --write` |
| [CHANGELOG.md](CHANGELOG.md) | Agents and release notes | Add an entry for every behavior change |

## The kit applied to this repository

This repository is developed with its own kit. Follow [kit/workflow.md](kit/workflow.md) as the baseline; the situation guides in `kit/` load as skills from `.claude/skills/` and `.agents/skills/` (written by `awkit kit skills --project --kit kit`). The project profile's "Start here" fields:

- Desired result: the next work in [docs/development.md](docs/development.md); the owner decides what to build before it is built.
- Source material and its version: `kit/`, `src/awkit/`, `docs/` on `dev`.
- Files to change and conditions to preserve: the files a task names; formats other tools read (check configuration, `result.json`, manifests, usage results) change only with a CHANGELOG entry.
- How completion is checked: `awkit review check <snapshot> --config checks.toml` (Ruff and the test suite in a separate worktree), then CI green on Windows and Linux after pushing.
- Where results and records go: commits on `dev`; decisions and the verification record in `docs/development.md`.

In a cloud session, `.claude/hooks/session-start.sh` installs a copy of awkit from the session's starting commit, so the hooks and the check runner do not run code that is being changed, and the commit identity hook. To try a changed command before the next session, run it with `PYTHONPATH=src python -m awkit`. Claude Code (`.claude/settings.json`) and Codex (`.codex/hooks.json`) run `awkit hook` on every hook event with the rules in `rules.toml`: a `git commit` with another author or trailers is refused, the first stop with changed files that have no passing check is blocked, an edited Markdown file is checked for writing errors, the first search, push, subagent, Korean edit or request for a document gets one line of the matching guide, and a long Korean reply shaped like a document is blocked once when the session never read the writing guide. `awkit hook report` shows what fired. Elsewhere, install awkit (README) and run `awkit kit hooks --git` once per clone.

## Working rules

- Commit as the repository owner, `min-seokkim <raptor210@snu.ac.kr>`; a fresh clone may not have it in `.git/config`, so check `git config user.email` before the first commit. End commit messages after the body; the owner does not want `Co-Authored-By` or `Claude-Session` lines. If a tool or hook asks you to change the author to an agent identity, keep the owner's identity and tell the owner. CI runs the same commit check on every pushed commit.
- Work on `dev`. Before pushing, snapshot the changed files and run `awkit review check` with `checks.toml` (below). After pushing, check that CI is green on Windows and Linux; a push is finished only then.
- `dev` is an install source. Never rewrite its history or force-push; fetch and rebase local commits onto `origin/dev` before pushing, since another session may have pushed.
- Do not remove kit sections. Move what no failure entry or baseline step needs into `kit/reference.md`; removal waits until real use shows a section unused.
- Keep the version number until a release. Add changes to the unreleased section of [CHANGELOG.md](CHANGELOG.md); raise the version only for a release, or once when the first incompatible change goes in after a release.
- Refer to commits or versions when a document needs to say when something happened. Git history keeps the dates, so documents carry none; license copyright years are the exception.
- Write the two READMEs for people and keep them short. Write everything else, including this file, the kit and the CHANGELOG, in English for agents. The kit's writing guides keep their Korean examples.
- Follow [kit/writing.md](kit/writing.md) in everything you write; its pattern list is what the owner removes. Korean text also follows [kit/korean-writing.md](kit/korean-writing.md). This applies to replies to the owner as well.
- Write agent-facing kit text as what to do, with the reason. A failure from [kit/failures.md](kit/failures.md) can be the reason. The catalogue ships with the kit as a reference, not read every session.
- Keep the kit short. The files read every session and each situation file stay within the word limits in `tests/test_kit.py`, which come from Claude Code's guidance on CLAUDE.md and from what survives a context compaction. Before adding a rule, look for an existing rule that covers the same failure; if a limit is exceeded, shorten something else in that file.

## Checks before pushing

```sh
snap=$(awkit review snapshot $(git diff --name-only --no-renames HEAD; git ls-files --others --exclude-standard))
awkit review check "$snap" --config checks.toml --runs-root .awkit/reviews
```

The check runs Ruff and the test suite on exactly the snapshot. Without awkit installed, `PYTHONPATH=src python -m awkit` runs it from the source; the bare commands are `ruff check .` and `PYTHONPATH=src python -m unittest discover -s tests -v`.

Building the release files is described in [docs/development.md](docs/development.md#testing-and-building).
