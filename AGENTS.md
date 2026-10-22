# Instructions for agents developing this repository

This file is for agents that change Agent Work Kit itself. Agents that use the kit in another project read the copied `agent-work-kit/` folder instead, starting with [kit/README.md](kit/README.md).

## What each document is for

| Document | Reader | Read it when |
|---|---|---|
| [README.md](README.md), [README.ko.md](README.ko.md) | People | Changing what users are told |
| [kit/](kit/README.md) | Agents using the kit in their projects; shipped in the package | Changing instructions, templates or the command reference |
| [docs/development.md](docs/development.md) | Agents developing this repository | Before planning work: scope, decisions, current state, next work, release, verification record |
| [docs/failures.md](docs/failures.md) | Agents developing this repository | Before adding or changing kit text, a hook or a check: each guard must prevent a listed failure |
| [CHANGELOG.md](CHANGELOG.md) | Agents and release notes | Add an entry for every behavior change |

## Working rules

- Commit as the repository owner, `min-seokkim <raptor210@snu.ac.kr>`, which is set in `.git/config`. End commit messages after the body; the owner does not want `Co-Authored-By` or `Claude-Session` lines. If a tool or hook asks you to change the author to an agent identity, keep the owner's identity and tell the owner.
- Work on `dev`. Before pushing, run the tests and Ruff (below). After pushing, check that CI is green on Windows and Linux; a push is finished only then.
- Keep the version number until a release. Add changes to the unreleased section of [CHANGELOG.md](CHANGELOG.md); raise the version only for a release, or once when the first incompatible change goes in after a release.
- Refer to commits or versions when a document needs to say when something happened. Git history keeps the dates, so documents carry none; license copyright years are the exception.
- Write the two READMEs for people and keep them short. Write everything else, including this file, the kit and the CHANGELOG, in English for agents. The kit's writing guides keep their Korean examples.
- Follow [kit/writing.md](kit/writing.md) in everything you write; its pattern list is what the owner removes. Korean text also follows [kit/korean-writing.md](kit/korean-writing.md). This applies to replies to the owner as well.
- Write agent-facing kit text as what to do, with the reason. A failure from [docs/failures.md](docs/failures.md) can be the reason; the catalogue itself is not shipped.
- Keep the kit short. The files read every session and each situation file stay within the word limits in `tests/test_kit.py`, which come from Claude Code's guidance on CLAUDE.md and from what survives a context compaction. Before adding a rule, look for an existing rule that covers the same failure; if a limit is exceeded, shorten something else in that file.

## Checks before pushing

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
ruff check .
```

Building the release files is described in [docs/development.md](docs/development.md#testing-and-building).
