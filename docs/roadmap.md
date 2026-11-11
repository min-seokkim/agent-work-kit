# Roadmap

**Goal: release 0.3.2, then 0.4.0.** 0.3.2 takes fixes and first runs of what 0.3.0 already promises and changes no existing behavior. 0.4.0 takes the incompatible changes together; they land on `dev` only after 0.3.2 is tagged, because `dev` is the only release line. Compatible work may land at any time and ships in the next release. The gate in [release.md](release.md) applies to each release; work with no release waits in "Later".

An agent picks the highest Ready item it can finish, says which in one line, and starts. When an item is finished, delete its row in the same commit as the code and record the behavior change in [CHANGELOG.md](../CHANGELOG.md). When Ready is empty, compare the gate with the current state and add the next unmet condition an agent can work on as a new Ready row, then start it. Stop only when every unmet condition waits for the owner, and say which. Decisions that later work must respect go in [design.md](design.md).

## Ready

| Item | Release | Done when |
|---|---|---|
| Trial: drive a Claude Code background session with awkit, on the owner's request to try it as early as possible. Claude Code leaves SDK sessions out of its picker by design ([official docs](https://code.claude.com/docs/en/sessions#loop-p-agent-sdk-and-background-sessions)) and lists background sessions; `claude --resume <native_id>` opens an SDK session today. | 0.3.2 if existing sessions behave as before, otherwise 0.4.0 | The trial shows whether awkit can start a background session and keep its approval and interruption controls. If it can, awkit-created Claude sessions can appear in the picker, with tests for the failure paths. If it cannot, `kit/sessions.md` names the operation the provider refuses and this row returns to Later. |
| Run the winget and Homebrew installer branches, which have never run. | 0.3.2 | Each branch ran once where Git or Python was missing and ended with a passing `awkit doctor`; each defect found is fixed. Try a macOS CI runner and Windows Sandbox first, and ask the owner for a clean machine only if both fail. |
| Remove two stale kit lines. | 0.3.2 | `kit/reference.md` no longer requires Playwright for the removed `ui` command. The check line in `kit/failures.md` no longer plans a profile field read by the done check, which [design.md](design.md) decided against. |
| Decide how formats change after a release. The design row "Formats migrate in place before the first release" assumed no released consumer; 0.3.0 and 0.3.1 are on PyPI. | 0.4.0, before any format change | That design row says what a patch and a minor release may change in the formats other tools read, and how files written by 0.3.x are read. Default for the owner to confirm: a patch changes no format; a minor may, migrating in place, with a CHANGELOG entry under "Incompatible changes". |
| Remove `init --commit`, on the owner's decision. | 0.4.0 | `kit init` and `kit init --copy` refuse `--commit`; the kit text, the guard declarations and the guard map no longer name it; the CHANGELOG lists the removal under "Incompatible changes". This is the first incompatible change after the release, so its commit raises the version to 0.4.0. |
| Two-environment trial. The owner's second computer reads the checkout as files and runs no project commands, so it is the file-access-only reviewer. | 0.4.0 | An agent writes the one prompt the owner pastes into a session on that computer. The reviewer there completed a review through a channel, an interrupted request was recovered on an execution-capable client, and each defect found is fixed or has a row here. |

## Waiting for the owner

Each row has a default. An agent applies the default when the rest of the gate is met and there is no answer.

| Decision or material | Default |
|---|---|
| For 0.3.2: the `AWKIT_ENV_PROBE` sentinel probe for Git-Bash commit-path activation. The code fix is delivered in `9093631`; whether the selector activates in a live session is unproven. The owner opens a fresh Claude session on their Windows machine and gives a new go. | 0.3.2 ships without the probe, and this row stays for the next patch. |

## Later

Each waits for what its row names and has no release. A fix or a measured result ships in the release that is open when it arrives. Presentation and HWP work is the candidate theme after 0.4.0.

| Item | What unblocks it, and who |
|---|---|
| Storage growth of shared artifact storage on a real continuation. One copied run is 42.8 MB; the first shared run with one changed file added 284 KB plus a 4.8 KB object. Near-identical repeats prove nothing. | The owner's target project runs a continuation that changes outputs; that session records the increment against a copied counterfactual. |
| Attach to existing IDE sessions; enroll foreign Claude sessions; list live Claude sessions. | A provider endpoint. Codex has none (socket error 10050). The owner says which outcome they want when one appears. |
| Repair the other project's `rules.toml`, which still holds a `MultiplexedPath(...)` value. | Owner authorization; awkit never rewrites a project's rules on its own. |
| The automatic Stop-hook ImportError (`awkit.checks`, `awkit.process`), never reproduced. | The owner captures a failing automatic invocation with its runtime context, if it happens again. |
| Whether writing corrections persist without reminders, and the attribution cost of `writing compare` on a real revision. | The owner selects a real revision. |
| Presentation production with native PowerPoint control; HWP/HWPX validation; the three reported PPTX validator bugs. | A working PowerPoint control connection from the owner, then a selected real task. |

## Decided against

Do not propose these again without a new observed failure: removing the second payload buffer in shared publication (largest observed artifact 11.4 MB, no memory failure); source-snapshot storage cleanup; unifying the two artifact collectors; migrating, expiring or deleting old review runs; a new task store or lookup command; a general updater for connected projects; a scheduler or background listener; a role-management feature; a new document engine or format rule; extending `check done`.
