# Agent Work Kit

English | [한국어](README.ko.md)

Agent Work Kit is a set of working instructions and a command-line tool for Claude Code, Codex and other coding agents. It helps agents preserve task requirements, check a fixed version of their work and report results with evidence. It covers code, documents, data and research, in any programming language.

It is for people who repeatedly hand work to agents in Git projects and spend time checking the results or explaining the same requirements again. You describe the work and review the result; the agent reads the detailed guides and operates the tools.

## Why

Working with agents involves deciding what to do, gathering evidence, creating and revising results, and handing work over. Agent Work Kit addresses recurring problems throughout that process:

- Implementation starts before the problem and completion criteria are clear.
- Research or analysis mixes source facts, observations, assumptions and interpretation.
- A revision changes the author's meaning or loses accepted content, inputs or results.
- Tests and reviews cover a different version from the one delivered.
- Separate sessions duplicate work or leave requests unanswered, while the user relays messages and repeats earlier decisions.
- A setup or delivery command succeeds, but nobody checks whether the change took effect or the recipient received the result.
- Work spreads across models and sessions, making it hard to see how much was used.

## How it works

When you connect the kit, the agent inspects the project's existing instructions, records and checks. It confirms what counts as done and who receives the result. Built-in diagnostics identify missing tools, connection problems and incompatible settings so the agent can set up the workflow around what the project already uses.

The kit then supports the work from the initial request to the next revision:

1. The agent establishes the goal, sources, change scope and completion criteria before starting. Guides for research and analysis ask it to keep source claims, observations, assumptions and conclusions distinct.
2. The agent reads the guides needed for the task. Hooks supply relevant guidance and run checks during work, including checks for specified writing patterns and missing verification of changed files.
3. A snapshot fixes the version being checked without changing the working branch. The tool runs the project's checks in a separate copy, retains logs and selected outputs, and can verify that the retained files have not changed.
4. Accepted output files can be kept as a baseline. Later comparisons identify changed or missing files and can list newly retained ones, helping reviewers find unintended changes to earlier work.
5. Separate sessions can exchange requests, reviews and replies through a local channel, including sessions from different providers. Status reports expose unanswered requests and recorded responsibilities; project handoffs preserve the context needed to resume.
6. Delivery guidance asks the agent to confirm the result where it will be used: a setting in the running program, a published version at its destination, or a file received by its recipient.

Usage reports read Claude Code and Codex session logs to summarize models and token use, marking incomplete information. These reports help inspect resource use; they do not measure the quality of the result or establish time saved.

The local channel needs no server, and the base package has no third-party Python runtime dependencies. Detailed setup and command instructions are written for agents in the [kit guides](kit/README.md).

## By kind of work

| Work | What the agent does | What you can inspect |
|---|---|---|
| Code change | Records the task, snapshots the change and runs existing project checks. | The checked version, logs, retained outputs and untested areas. |
| Document | Preserves source facts and author intent, then reviews facts, prose and structure. | The document, its source comparison and the reasons for revisions. |
| Data cleanup or analysis | Records input hashes, separates observations from interpretation and compares retained outputs with an accepted result. | Input identities, changed results and, optionally, newly retained files. |
| Research and setup | Records sources, assumptions, environment checks and delivery evidence. | The result, supporting evidence and unresolved questions. |
| Second review | Another session reviews a fixed snapshot and returns comments through the channel. | Comments tied to that version, replies and outstanding requests. |

Automated checks verify the conditions configured for a project. Whether a result answers the question and is ready to use still requires review.

### Document writing

The writing guides cover a document's audience and purpose, source preservation, drafting and revision. Before drafting, the agent checks the originals and identifies the facts, qualifications and author intent to keep. It distinguishes plans from completed work and an author's question from a summary's interpretation.

For Korean documents, the guide calls for an English draft followed by a natural Korean rewrite. Review then covers facts, Korean prose and the document's overall structure separately, including the rendered output. A small correction is scoped to the affected passage; an accepted document supplies the wording and structure to preserve during revision.

When you correct a document, the guidance asks the agent to retain the reason and scope of that correction and apply it to later relevant drafts and handoffs. The project's existing records hold these requirements, so a later session can find them.

Built-in writing checks find specified patterns such as mixed Korean endings. A comparison report helps inspect which findings remain between revisions. These tools support editorial review; source fidelity, argument quality and natural prose are judged by reading. The [writing guide](kit/writing.md) and [Korean supplement](kit/korean-writing.md) contain the agent's procedure.

## Get started

awkit requires Python 3.11 or later and Git. There is no release yet; the installers use the `dev` branch.

On Windows, run in PowerShell:

```powershell
irm https://raw.githubusercontent.com/min-seokkim/agent-work-kit/dev/install.ps1 | iex
```

On macOS or Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/min-seokkim/agent-work-kit/dev/install.sh | sh
```

The installer installs missing Git and Python through winget on Windows or Homebrew on macOS; on Linux it identifies missing packages. It installs awkit with [pipx](https://pipx.pypa.io), adds the guides as user skills and checks the installation.

In your project folder, run:

```sh
awkit kit init
```

Then tell your agent:

> Connect Agent Work Kit to this project.

The setup creates project configuration and connects hooks alongside existing ones. It leaves existing instructions, skills and memory files intact and makes no commit. Your agent then fills in the project requirements and checks the proposed commands. You can also ask it to walk through the bundled data example, which starts with a wrong column name and retains both the failed and corrected check results.

To update, rerun the installer, then ask your agent to check the project's connection and reread the updated guides. The installer refreshes awkit and its managed user skills; project settings, hooks and project-local guides remain unchanged. Agents can look up alternate installation, diagnostics and removal in the [command reference](kit/reference.md).

## Status

The project is in development, with no release yet. Commands and file locations may change before the first release. We use awkit in this repository and record results from real tasks in the [development evidence](docs/evidence.md).

See the [roadmap](docs/roadmap.md) for planned work and [CHANGELOG.md](CHANGELOG.md) for changes. To work on the project, start with the [development guide](docs/development.md).

MIT license. The writing guides are adapted in part from `im-not-ai`; its source and license are in the [third-party notices](kit/THIRD_PARTY_NOTICES.md).
