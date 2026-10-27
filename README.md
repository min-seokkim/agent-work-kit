# Agent Work Kit

English | [한국어](README.ko.md)

Agent Work Kit is a set of working instructions and an `awkit` command-line tool for Claude Code, Codex and other coding agents. It covers code, documents, research and data, in any programming language.

You describe the outcome and decide whether to accept it. The agent uses the kit to define the work, preserve requirements, check a fixed version and leave evidence that another session can follow.

## Why

Giving an agent a task often leaves you with more work to supervise: explaining a requirement again, recovering text that a revision removed, or finding out which version was actually tested. With several sessions, you may also end up relaying messages and reconstructing earlier decisions.

The kit gives those tasks a common procedure. It asks agents to agree on the goal before implementation, keep sources and accepted results available, and report what they checked and what remains uncertain. Hooks and executable checks enforce selected parts of that procedure. The project records retain the decisions needed for later work.

## How it works

The agent starts with the project's existing instructions, records and check commands. It reads the kit guides relevant to the task and follows three stages:

1. Define the outcome, source material, change scope and completion criteria. Record who owns the work and where its result belongs.
2. Check a fixed revision in a separate working copy. Keep the commands, logs and selected output files, including failed attempts. Hashes show whether the retained files have changed.
3. Compare revisions with accepted outputs, review the result and confirm delivery at its destination. Leave the checked version, remaining limits and next action in the task record.

Hooks can supply relevant guidance and check configured conditions while the agent works, such as writing patterns or changed files without a passing check.

For work across sessions, local channels retain requests, reviews and replies. Session controls can start Codex or Claude conversations and display assignments, responses and pending decisions in a local browser view. Agents can use the same controls from the command line. These controls use the installed providers; Claude support needs the optional integration described in the [session guide](kit/sessions.md).

Usage reports summarize models and tokens from Claude Code and Codex logs, marking incomplete coverage. The channel needs no server, and the base package has no third-party Python runtime dependencies. Detailed procedures are in the [kit guides](kit/README.md).

## By kind of work

| Work | What the kit helps the agent do | What to inspect |
|---|---|---|
| Code change | Run the project's checks against a frozen revision. | The revision, test logs and untested behavior. |
| Document | Preserve source meaning and accepted choices while drafting or revising. | The text, source comparison and reasons for changes. |
| Data analysis | Identify inputs, keep the analysis outputs and compare them with an accepted result. | Input hashes, calculations, changed or missing files and optional added-file listings. |
| Research | Separate source claims, observations, assumptions and conclusions. | Supporting sources, reasoning and unresolved questions. |
| Setup or delivery | Inspect the environment and verify the result where it will be used. | Diagnostic results and evidence that the change took effect. |

Automated checks cover the conditions configured for the project. Reading the result, judging its usefulness and accepting it remain part of review. A second session can review the same fixed version and return comments through a channel.

### Document writing

The writing guides start with the reader, purpose and original sources. They ask the agent to preserve facts, qualifications and author intent, scope small edits to the affected passage, and carry the reason for a correction into later relevant work.

Drafting methods follow the document's purpose and the user's requirements. Korean writing gets separate reviews of facts, natural phrasing and overall structure, followed by inspection of the rendered result. Built-in checks find specified writing patterns and compare findings between revisions; source fidelity and argument quality require reading. See the [writing guide](kit/writing.md) and [Korean supplement](kit/korean-writing.md).

## Get started

awkit requires Python 3.11 or later and Git. The installers currently use the `dev` branch.

On Windows, run in PowerShell:

```powershell
irm https://raw.githubusercontent.com/min-seokkim/agent-work-kit/dev/install.ps1 | iex
```

On macOS or Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/min-seokkim/agent-work-kit/dev/install.sh | sh
```

The installer uses winget on Windows or Homebrew on macOS for missing prerequisites; on Linux it identifies the missing packages. It installs awkit with [pipx](https://pipx.pypa.io), writes the guides as user skills and checks the installation. Open a new terminal if `awkit` is not found.

In your project folder, run:

```sh
awkit kit init
```

Then tell your agent:

> Connect Agent Work Kit to this project.

Setup adds project configuration and connects hooks alongside existing ones. It preserves existing instructions, skills and memory files and makes no commit. The agent fills in the project's requirements and verifies its check commands. To try the workflow, ask it to run the bundled data example: a wrong column name produces a failed check, and the corrected run retains its own evidence.

To update, rerun the installer and ask the agent to inspect the project connection and reread the guides. The installer updates awkit and its managed user skills; project settings, hooks and local guides keep their existing contents. Alternate installation, diagnostics and removal are in the [command reference](kit/reference.md).

## Status

The project is in development and has no release yet. Commands and file locations may change before the first release. We use the kit in this repository; [development evidence](docs/evidence.md) records observed results and their limits. Usage totals and passing checks alone do not establish time saved or better work.

The [roadmap](docs/roadmap.md) describes unfinished work, and [CHANGELOG.md](CHANGELOG.md) records changes. To contribute, start with the [development guide](docs/development.md).

MIT license. The writing guides include adaptations of `im-not-ai`; source attribution and its license are in the [third-party notices](kit/THIRD_PARTY_NOTICES.md).
