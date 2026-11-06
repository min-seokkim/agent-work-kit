# Roadmap

**Goal: release 0.3.0.** The gate and the feature scope are in [release.md](release.md). Until the tag, the Ready table holds only work toward that gate and CI fixes; any other idea goes to "After 0.3.0".

An agent picks the highest Ready item it can finish, says which in one line, and starts. When an item is finished, delete its row in the same commit as the code and record the behavior change in [CHANGELOG.md](../CHANGELOG.md). When Ready is empty, compare the gate with the current state and add the next unmet condition an agent can work on as a new Ready row, then start it. Stop only when every unmet condition waits for the owner, and say which. Decisions that later work must respect go in [design.md](design.md).

## Ready

| Item | Done when |
|---|---|
| Remove the web extras `pipeline`, `publish` and `ui` (the owner's default). They have no recorded real use, and the design says they leave the package then. | Their modules, CLI groups, tests, `kit/extras.md`, the example they use and the CI quick-start steps that call them are gone; the Wheel job's quick start uses `review` alone; the CHANGELOG lists the removal under incompatible changes. |
| Verify Codex runtime capability admission in CI. Runtime-range implementation and no-model-call live check are under review. | The independent runtime review is applied and Windows and Linux CI pass. |
| Run a current Codex CLI in CI. | A CI job on Linux, Windows and macOS installs the current Codex CLI, starts its app server, runs initialize and the capability probes, and makes no model call. |
| Accept a tested range of the Claude Agent SDK instead of exactly 0.2.174. | `claude_session.availability` accepts the range in `pyproject.toml`, and the Claude SDK CI job tests its lowest and newest versions. |
| Run the session tests on macOS. | A macOS CI job runs the session, Codex and Claude test modules and is green. |
| Count one call the same way for Claude and Codex. The owner's default unit: one model response, which is a Claude `message.id`, or a Codex turn whose `token_count` changed. | `awkit usage` reports `calls` in that unit for both providers, in a new result format announced in the CHANGELOG, with tests for repeated IDs, resumed logs and missing token counts. |
| Test `awkit usage` on a real Claude Code log. | A fixture built from a real Claude Code transcript, with its text replaced by fictional text, gives exact calls, user messages and tokens. |

## Waiting for the owner

Each row has a default. An agent applies the default when the rest of the gate is met and there is no answer.

| Decision or material | Default |
|---|---|
| Real logs from Codex CLI, Codex IDE and Claude Desktop, a few turns each, for `usage` fixtures. Codex writes `rollout-*.jsonl` under `~/.codex/sessions/`. | None: `usage` is a stable group, so the release waits for them. |
| The definition of one call for `usage`. | One model response, as in the Ready row. |
| Remove `init --commit`, an incompatible change. | Keep it in 0.3.0; decide after. |
| Keep any of `pipeline`, `publish`, `ui`. | Remove all three. |
| The PyPI pending publisher and the `pypi` environment ([release.md](release.md#release)). | None: the upload needs them. |
| The word "release". | None. |

## After 0.3.0

Each waits for what its row names; do not start them before the tag.

| Item | What unblocks it, and who |
|---|---|
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
