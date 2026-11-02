# Roadmap

What to work on in this repository. An agent picks the highest Ready item it can finish, says which in one line, and starts. Blocked items wait for the thing named in their row; do not start them and do not rewrite them. When Ready is empty, say so and stop. When an item is finished, delete its row in the same commit as the code and record the behavior change in [CHANGELOG.md](../CHANGELOG.md). Decisions that later work must respect go in [design.md](design.md).

## Ready

| Item | Done when |
|---|---|
| Check that the Windows file-replacement retry from `7e82e3f` also covers acceptance directory promotion in `review accept`, which failed with WinError 5 in real use. | A test holds the target open and acceptance still succeeds, or the gap is fixed. |
| Run the [snapshot recipe](../kit/reference.md#snapshot) on Linux. It has only been exercised on Windows. | The recipe works in bash or the reference gives a POSIX form, with a test. |

## Blocked

| Item | What unblocks it, and who |
|---|---|
| Usage accounting against current clients: a counting unit and matching across log files. A call-count guard would depend on it. | The owner supplies fresh Claude Desktop and Codex logs and decides what one call means. |
| Storage growth of shared artifact storage on a real continuation. One copied run is 42.8 MB; the first shared run with one changed file added 284 KB plus a 4.8 KB object. Near-identical repeats prove nothing. | The owner's target project runs a continuation that changes outputs; that session records the increment against a copied counterfactual. |
| Two-environment trial: a file-access-only reviewer on another computer, and recovery of an interrupted request on an execution-capable client. | The owner makes another computer available. |
| Attach to existing IDE sessions; enroll foreign Claude sessions; list live Claude sessions. | A provider endpoint. Codex has none (socket error 10050). The owner says which outcome they want when one appears. |
| Remove `init --commit`, merge the default rules and clean up installation records. | Owner approval; it is an incompatible change. |
| Repair the other project's `rules.toml`, which still holds a `MultiplexedPath(...)` value. | Owner authorization; awkit never rewrites a project's rules on its own. |
| The `AWKIT_ENV_PROBE` sentinel probe for Git-Bash commit-path activation. The code fix is delivered in `9093631`; whether the selector activates in a live session is unproven. | The owner opens a fresh Claude session on their Windows machine and gives a new go. |
| The automatic Stop-hook ImportError (`awkit.checks`, `awkit.process`), never reproduced. | The owner captures a failing automatic invocation with its runtime context, if it happens again. |
| Whether writing corrections persist without reminders, and the attribution cost of `writing compare` on a real revision. | The owner selects a real revision. |
| Presentation production with native PowerPoint control; HWP/HWPX validation; the three reported PPTX validator bugs. | A working PowerPoint control connection from the owner, then a selected real task. |
| The winget and Homebrew installer branches have never run. | A clean machine without Git or Python. |
| First release, `release.yml` has never run. | The conditions in [release.md](release.md). |

## Decided against

Do not propose these again without a new observed failure: removing the second payload buffer in shared publication (largest observed artifact 11.4 MB, no memory failure); source-snapshot storage cleanup; unifying the two artifact collectors; migrating, expiring or deleting old review runs; a new task store or lookup command; a general updater for connected projects; a scheduler or background listener; a role-management feature; a new document engine or format rule; extending `check done`.
