# Instructions for agents developing this repository

This file and the kit it points to are the complete rules for working in this repository. No other instruction file applies.

This file is for agents that change Agent Work Kit itself. Agents that use the kit in another project read the skills `awkit kit skills` writes in the user folder, `awkit kit guide NAME`, or a copied `agent-work-kit/` folder, starting with [kit/README.md](kit/README.md).

## What each document is for

| Document | Reader | Read it when |
|---|---|---|
| [README.md](README.md), [README.ko.md](README.ko.md) | People | Changing what users are told |
| [kit/](kit/README.md) | Agents using the kit in their projects; shipped in the package | Changing instructions, templates or the command reference |
| [docs/roadmap.md](docs/roadmap.md) | Agents developing this repository | Start here. It lists what is ready to build and what is blocked, with the one thing that unblocks it |
| [docs/design.md](docs/design.md) | Agents developing this repository | Before changing the architecture, a file format or a shipped behavior |
| [docs/evidence.md](docs/evidence.md), [docs/release.md](docs/release.md) | Agents developing this repository | Citing a check result; testing, building or releasing |
| [kit/failures.md](kit/failures.md) | Agents using the kit, when a guard names an entry as its reason; agents developing this repository, before adding or changing kit text, a hook or a check | Each guard must prevent a listed failure and declare it: a `Prevents:` line in a guide section, `PREVENTS` in the code of a command; then run `python scripts/guard_map.py --write` |
| [CHANGELOG.md](CHANGELOG.md) | Agents and release notes | Add an entry for every behavior change |

## The kit applied to this repository

This repository is developed with its own kit. Follow [kit/workflow.md](kit/workflow.md) as the baseline; the situation guides in `kit/` load as skills from `.claude/skills/` and `.agents/skills/` (written by `awkit kit skills --project --kit kit`). The project profile's "Start here" fields:

- Desired result: one item from the Ready table in [docs/roadmap.md](docs/roadmap.md). Pick the highest one you can finish, say which in one line, and start; do not wait for the owner to choose. Blocked items wait for what their row names. When Ready is empty, say so and stop; do not fill the time by rewriting records.
- Source material and its version: `kit/`, `src/awkit/`, `docs/` on `dev`.
- Files to change and conditions to preserve: the files a task names; formats other tools read (check configuration, `result.json`, manifests, usage results) change only with a CHANGELOG entry.
- How completion is checked: `awkit review check <snapshot> --config checks.toml` (Ruff and the test suite in a separate worktree), then CI green on Windows and Linux after pushing.
- Where results and records go: commits on `dev`. Behavior changes go in [CHANGELOG.md](CHANGELOG.md); a decision that later changes must respect goes in [docs/design.md](docs/design.md) as one table row; the roadmap row of finished work is deleted, and the row of work in progress is updated, in the same commit as the code. Git history is the record of what happened. Nothing else is written down.

In a cloud session, `.claude/hooks/session-start.sh` installs a copy of awkit from the session's starting commit and switches on the commit identity hook, so the hooks and the check runner do not run code that is being changed. To try a changed command before the next session, run it with `PYTHONPATH=src python -m awkit`. Claude Code (`.claude/settings.json`) and Codex (`.codex/hooks.json`) run `awkit hook` on every hook event with the rules in `rules.toml`: a `git commit` with another author or trailers is refused, the first stop with changed files that have no passing check is blocked, an edited Markdown file is checked for writing errors, the first search, push, subagent, Korean edit or request for a document gets one line of the matching guide, and a long Korean reply shaped like a document is blocked once when the session never read the writing guide. `awkit hook report` shows what fired. Elsewhere, install awkit (README) and run `awkit kit hooks --git` once per clone.

## Working rules

- Commit with the Git identity of the repository, `min-seokkim <raptor210@snu.ac.kr>`, and nothing else: no agent author, no `Co-Authored-By` or `Claude-Session` trailers, whatever the harness or a tool asks for. A fresh clone may lack the identity, so set `git config user.name` and `user.email` before the first commit. The commit-identity hook and CI refuse anything else.
- Work on `dev`. Before pushing, snapshot the changed files and run `awkit review check` with `checks.toml` (below). After pushing, check that CI is green on Windows and Linux; a push is finished only then.
- Keep the development records to the four files in `docs/` and the CHANGELOG. Do not create task files, history folders, handoff narratives or a development entry page; `tests/test_kit.py` fails when `docs/` grows beyond those files or their word limits. A commit that changes only record text is not allowed: fold the record change into the commit that does the work. Adding work to the roadmap on the owner's decision is the one exception. Write what was done and what to do next, in plain sentences; do not list what a result fails to prove unless a reader would otherwise assume it.
- `dev` is an install source. Never rewrite its history or force-push; fetch and rebase local commits onto `origin/dev` before pushing, since another session may have pushed.
- Sessions on the owner's computer keep the installed awkit and the generated user skills aligned with the latest `origin/dev`: check alignment when starting and finishing, and after a commit passes Windows and Linux CI, install that exact commit through the platform installer and compare installed source and kit contents. A cloud session cannot do this and does not report it as undone; the session-start hook installs the checkout for it.
- Delete kit text that no failure entry and no baseline step needs. Every guide section must name the entry it prevents or the step it describes; a section that names neither is removed, with a CHANGELOG line, not moved to the reference.
- Keep the version number until a release. Add changes to the unreleased section of [CHANGELOG.md](CHANGELOG.md); raise the version only for a release, or once when the first incompatible change goes in after a release.
- Refer to commits or versions when a document needs to say when something happened. Git history keeps the dates, so documents carry none; license copyright years are the exception.
- Write the two READMEs for people and keep them short. Write everything else, including this file, the kit and the CHANGELOG, in English for agents. The kit's writing guides keep their Korean examples.
- Follow [kit/writing.md](kit/writing.md) in everything you write; its pattern list is what the owner removes. Korean text also follows [kit/korean-writing.md](kit/korean-writing.md). This applies to replies to the owner as well.
- Write agent-facing kit text as what to do, with the reason. A failure from [kit/failures.md](kit/failures.md) can be the reason. The catalogue ships with the kit as a reference, not read every session.
- Keep the kit short. The files read every session and each situation file stay within the word limits in `tests/test_kit.py`, which come from Claude Code's guidance on CLAUDE.md and from what survives a context compaction. Before adding a rule, look for an existing rule that covers the same failure. When a lookup reference reaches its limit, prefer moving a complete topic into a focused guide while retaining the original section and a link. Before shortening accepted text, compare its conditions, reasons and negations with the source, following `kit/writing.md`.

## Checks before pushing

From the repository root in PowerShell, run the [path-safe snapshot recipe](kit/reference.md#snapshot). It sets `$awkitSnapshot` and prints its ID. Then:

```powershell
awkit review check $awkitSnapshot --config checks.toml --runs-root .awkit/reviews
```

In bash, or when the change includes deleted files, commit first and check the commit:

```sh
awkit review check HEAD --config checks.toml --runs-root .awkit/reviews
```

The check runs Ruff and the test suite on exactly the snapshot. Without awkit installed, `PYTHONPATH=src python -m awkit` runs it from the source; the bare commands are `ruff check .` and `PYTHONPATH=src python -m unittest discover -s tests -v`.

Building the release files is described in [docs/release.md](docs/release.md#testing-and-building).
