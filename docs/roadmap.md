# Roadmap

**Goal: release 0.3.0.** The gate and the feature scope are in [release.md](release.md). Until the tag, the Ready table holds only work toward that gate and CI fixes; any other idea goes to "After 0.3.0".

An agent picks the highest Ready item it can finish, says which in one line, and starts. When an item is finished, delete its row in the same commit as the code and record the behavior change in [CHANGELOG.md](../CHANGELOG.md). When Ready is empty, compare the gate with the current state and add the next unmet condition an agent can work on as a new Ready row, then start it. Stop only when every unmet condition waits for the owner, and say which. Decisions that later work must respect go in [design.md](design.md).

## Ready

| Item | Done when |
|---|---|
| Diagnose Codex sidebar visibility | Compare a fresh awkit-created root-project thread with native listing and the app sidebar; fix an awkit cause or record the app-side blocker. |

## Cloud-session channel plan

The compatible host-local stdio adapter is implemented; setup and recovery are in [cloud-channels.md](../kit/cloud-channels.md). Desktop-started cloud Cowork on Windows reported `OperationalError: unable to open database file` for the host path. Through Desktop's local MCP connection, an echo and then an actual channel request/reply succeeded. Duplicate send, receipt replay, acknowledgement retry and acknowledged-body recovery succeeded. No permission prompt was observed. The echo entry was replaced by the bound adapter; the configuration backup is retained. Other runtimes, offline access and unsolicited wake-up remain unverified.

Owner observation is the remaining stage-5 action below. The route needs no incompatible change and preserves local Claude Code behavior. No scheduler, universal agent server, transcript mirror or default hosted relay is planned; denied operations never fall back to another adapter.

Research: [Cowork architecture](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview), [surface availability](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile), [SQLite network guidance](https://www.sqlite.org/useovernet.html).

## Waiting for the owner

Each row has a default. An agent applies the default when the rest of the gate is met and there is no answer.

| Decision or material | Default |
|---|---|
| Codex sidebar visibility. The owner still cannot see the probe in the exact project; the native listing API returns it. | Restore the Computer Use connection for app-side diagnosis; native pipe lookup still fails after the owner opened the app. |
| Claude's picker excludes SDK sessions by design ([official docs](https://code.claude.com/docs/en/sessions#loop-p-agent-sdk-and-background-sessions)). Exact-ID interactive resume opened the original probe and its saved reply. | The owner retains picker visibility as a release condition and holds the release. Resume when the provider supports listing SDK sessions or the owner changes the condition. |
| Observe the cloud channel round trip in Claude Desktop. | Open the prepared "Cloud transport connectivity probe" conversation and confirm the `AWKIT_CLOUD_CHANNEL_OK` reply. The main session exercised delivery and recovery; owner observation remains required. |
| The PyPI pending publisher and the `pypi` environment ([release.md](release.md#release)). | None: the upload needs them. |
| The word "release". | None. |

## After 0.3.0

Each waits for what its row names; do not start them before the tag.

| Item | What unblocks it, and who |
|---|---|
| Whether to remove `init --commit`; it stays in 0.3.0. | The owner's decision after the release. |
| Storage growth of shared artifact storage on a real continuation. One copied run is 42.8 MB; the first shared run with one changed file added 284 KB plus a 4.8 KB object. Near-identical repeats prove nothing. | The owner's target project runs a continuation that changes outputs; that session records the increment against a copied counterfactual. |
| Two-environment trial: a file-access-only reviewer on another computer, and recovery of an interrupted request on an execution-capable client. | The owner makes another computer available. |
| Attach to existing IDE sessions; enroll foreign Claude sessions; list live Claude sessions. | A provider endpoint. Codex has none (socket error 10050). The owner says which outcome they want when one appears. |
| Repair the other project's `rules.toml`, which still holds a `MultiplexedPath(...)` value. | Owner authorization; awkit never rewrites a project's rules on its own. |
| The `AWKIT_ENV_PROBE` sentinel probe for Git-Bash commit-path activation. The code fix is delivered in `9093631`; whether the selector activates in a live session is unproven. | The owner opens a fresh Claude session on their Windows machine and gives a new go. |
| The automatic Stop-hook ImportError (`awkit.checks`, `awkit.process`), never reproduced. | The owner captures a failing automatic invocation with its runtime context, if it happens again. |
| Whether writing corrections persist without reminders, and the attribution cost of `writing compare` on a real revision. | The owner selects a real revision. |
| Presentation production with native PowerPoint control; HWP/HWPX validation; the three reported PPTX validator bugs. | A working PowerPoint control connection from the owner, then a selected real task. |
| The winget and Homebrew installer branches have never run. | A clean machine without Git or Python. |

## Decided against

Do not propose these again without a new observed failure: removing the second payload buffer in shared publication (largest observed artifact 11.4 MB, no memory failure); source-snapshot storage cleanup; unifying the two artifact collectors; migrating, expiring or deleting old review runs; a new task store or lookup command; a general updater for connected projects; a scheduler or background listener; a role-management feature; a new document engine or format rule; extending `check done`.
