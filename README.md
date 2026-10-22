# Agent Work Kit

English | [한국어](README.ko.md)

Agent Work Kit is a set of instructions and a command-line tool for coding agents such as Claude Code and Codex. An agent using it reports a finished task together with the files it checked, the project checks it ran on them and what those checks produced. It works for code, documents, data and research, in any programming language.

## Why

Agents often report work as finished without evidence you could use to confirm it. Common cases:

- Tests are reported as passing, but they ran on a different version of the files, or did not run.
- A fix in one place changes a document or result you had already approved.
- The author keeps editing while a reviewer reads, so the version that ships was never reviewed.
- Each new session needs the project explained again.
- Korean documents read like translations.

## How it works

After `awkit kit init`, ask your agent to connect the kit. The agent reads the project, asks you what counts as done and who receives the result, writes a one-page project profile and sets up checks from commands the project already has.

Each task then follows the same steps:

1. The agent writes down the goal, the files it may change and the checks that decide whether the task is done.
2. It saves the changed files as a snapshot. The snapshot is a Git commit; your branch and working folder do not change.
3. It runs your checks on the snapshot in a separate copy of the project and keeps the logs and output files with their hashes.
4. When you approve a result, it keeps that result as the accepted version and compares later versions with it.
5. If you want a second review, another agent session reviews the same snapshot, and their messages refer to it.

## By kind of work

| Task | What the agent does | What you can check afterwards |
|---|---|---|
| Code change | Records the task, snapshots the change, runs the checks in a separate copy | The snapshot ID, the check logs, and what was not checked |
| Korean document | Lists the facts to keep, drafts in English, writes the Korean, then reviews facts, sentences and structure separately | The document and the list of facts it was checked against |
| Data cleanup or analysis | Records input hashes and keeps observations, assumptions and interpretation apart | Output files traced to their inputs, and assumptions checked against the data |
| Research, setup and other work | Follows the per-type rules on what to fix first, what to keep and when to ask | The result, its sources or evidence, and the known gaps |
| Second review | Another session reviews a fixed snapshot | Review comments tied to that snapshot |

## Get started

You need Python 3.11 or later and Git. awkit has no release yet, so install it from the development branch with [pipx](https://pipx.pypa.io):

```sh
pipx install "git+https://github.com/min-seokkim/agent-work-kit@dev"
```

In your project folder, run:

```sh
awkit kit init
```

Then tell your agent:

> Read `agent-work-kit/README.md` and connect the kit to this project.

To try it on a sample first, tell your agent to run `awkit kit example data demo` and follow its README. The sample is a small data project with one wrong column name. The agent runs the check and sees it fail, fixes the input, runs the check again and shows you the files it kept.

## Status

The project is in development. Commands and file locations may change before the first release. Changes are listed in [CHANGELOG.md](CHANGELOG.md), and development notes are in [docs/development.md](docs/development.md).

MIT license. The Korean writing guide is adapted from `im-not-ai`; its source and license are in the [third-party notices](kit/THIRD_PARTY_NOTICES.md).
