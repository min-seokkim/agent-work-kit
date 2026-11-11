# Roadmap

0.3.1 is released on PyPI and GitHub with the current README. Fresh installs from PyPI passed on Windows and Linux. No next release goal has been selected; the items in "Later" wait for their stated decisions or evidence. The gate in [release.md](release.md) applies to each release.

An agent picks the highest Ready item it can finish, says which in one line, and starts. When an item is finished, delete its row in the same commit as the code and record the behavior change in [CHANGELOG.md](../CHANGELOG.md). When Ready is empty, compare the gate with the current state and add the next unmet condition an agent can work on as a new Ready row, then start it. Stop only when every unmet condition waits for the owner, and say which. Decisions that later work must respect go in [design.md](design.md).

## Ready

| Item | Done when |
|---|---|

## Waiting for the owner

Each row has a default. An agent applies the default when the rest of the gate is met and there is no answer.

| Decision or material | Default |
|---|---|

## Later

Each waits for what its row names.

| Item | What unblocks it, and who |
|---|---|
| Whether to remove `init --commit`; it stays in 0.3.0. | The owner's decision after the release. |
| Claude picker visibility of awkit-created Claude sessions. Claude Code leaves SDK sessions out of its picker by design ([official docs](https://code.claude.com/docs/en/sessions#loop-p-agent-sdk-and-background-sessions)); `claude --resume <native_id>` opens them. Claude Code's background sessions appear in the picker; whether awkit can drive one with its approvals and interruption is untested. | A provider change that lists SDK sessions, or the owner selecting a background-session trial. |
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
