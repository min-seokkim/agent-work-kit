# Agent Work Kit

English | [한국어](README.ko.md)

Agent Work Kit is a set of instructions and a command-line tool for coding agents such as Claude Code and Codex. An agent using it reports a finished task together with the files it checked, the project checks it ran on them and what those checks produced. It works for code, documents, data and research, in any programming language.

It is for people who hand work to an agent again and again in a Git project and already spend time checking what comes back. For a one-off document by someone who does not write code, it is not yet as easy to use.

## Why

Agents often report work as finished without evidence you could use to confirm it. Common cases:

- Tests are reported as passing, but they ran on a different version of the files, or did not run.
- A fix in one place changes a document or result you had already approved.
- The author keeps editing while a reviewer reads, so the version that ships was never reviewed.
- Each new session needs the project explained again.
- Korean documents read like translations.

## How it works

After `awkit kit init`, ask your agent to connect the kit. The agent reads the project, asks you what counts as done and who receives the result, writes both into `checks.toml`, and sets up checks from commands the project already has.

Each task then follows the same steps:

1. The agent writes down the goal, the files it may change and the checks that decide whether the task is done.
2. It saves the changed files as a snapshot. The snapshot is a Git commit; your branch and working folder do not change.
3. It runs your checks on the snapshot in a separate copy of the project and keeps the logs and output files with their hashes.
4. When you approve a result, it keeps that result as the accepted version and compares later versions with it.
5. If you want a second review, another agent session reviews the same snapshot, and their messages refer to it.

You can open separate implementation and review sessions, including sessions from different providers, and have them exchange requests and results through a shared local channel. The channel needs no server, and the base package has no Python runtime dependencies. See the [review session guide](kit/review-session.md) for setup.

## By kind of work

| Task | What the agent does | What you can check afterwards | Checked by the tool, or left to the agent |
|---|---|---|---|
| Code change | Records the task, snapshots the change, runs the checks in a separate copy | The snapshot ID, the check logs, and what was not checked | Checked: your project's checks run on the snapshot, and their logs and output files are kept |
| Korean document | Lists the facts to keep, drafts in English, writes the Korean, then reviews facts, sentences and structure separately | The document and the list of facts it was checked against | Mostly left to the agent: `awkit check writing` finds mechanical patterns such as middle dots and mixed endings, but whether the Korean reads naturally is the agent's judgment |
| Data cleanup or analysis | Records input hashes and keeps observations, assumptions and interpretation apart | Output files traced to their inputs, and assumptions checked against the data | Checked for data in files: checks run on them and the outputs are kept with hashes; keeping observations apart from interpretation is left to the agent |
| Research, setup and other work | Follows the per-type rules on what to fix first, what to keep and when to ask | The result, its sources or evidence, and the known gaps | Left to the agent: whether the sources fit the question is its judgment |
| Second review | Another session reviews a fixed snapshot | Review comments tied to that snapshot | The tool fixes the snapshot; the review is the other session's judgment |

## Get started

awkit needs Python 3.11 or later and Git, and has no release yet. The installer adds Git and Python when they are missing (winget on Windows, Homebrew on macOS; on Linux it names the package to install), installs awkit from the development branch with [pipx](https://pipx.pypa.io), writes the kit's guides as skills in your user folder, and runs `awkit doctor`, which says how to fix anything still missing. The guides are your way of working, so they live on your computer once, for every project.

For a fresh install, the scripts use Python found in the active shell. Updating an existing pipx environment preserves its Python interpreter. Run `awkit doctor` to see which Python actually runs awkit.

On Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/min-seokkim/agent-work-kit/dev/install.ps1 | iex
```

On macOS or Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/min-seokkim/agent-work-kit/dev/install.sh | sh
```

With Python, Git and pipx already installed, run `pipx install "git+https://github.com/min-seokkim/agent-work-kit@dev"`, then `awkit kit skills` and `awkit doctor`. The first release will also offer the skills as a ZIP to unpack in your home folder, for writing and research work without Python.

In your project folder, run:

```sh
awkit kit init
```

It writes `checks.toml` with the checks your project already runs and a `[kit]` table that says what done means here. It adds awkit hooks alongside your existing hooks and keeps its own `.awkit/` folder out of Git. It commits nothing and leaves your instructions, skills and memory files as they are; it prints a line you can add to `AGENTS.md` or `CLAUDE.md` yourself. Only `checks.toml` and `rules.toml` are meant to be committed.

Then tell your agent:

> Connect Agent Work Kit to this project.

To update, rerun the installer above; it reinstalls awkit from `dev` and refreshes the skills. `awkit kit remove` takes the kit out of the project and `awkit kit remove --user` out of your user folder. An agent without skills reads a guide with `awkit kit guide workflow`.

To try it on a sample first, tell your agent to run `awkit kit example data demo` and follow its README. The sample is a small data project with one wrong column name. The agent runs the check and sees it fail, fixes the input, runs the check again and shows you the files it kept.

## Status

The project is in development. Commands and file locations may change before the first release. We use awkit in this repository's own work and record what works and what fails in the [development notes](docs/evidence.md). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

MIT license. The writing guides are adapted in part from `im-not-ai`; its source and license are in the [third-party notices](kit/THIRD_PARTY_NOTICES.md).
