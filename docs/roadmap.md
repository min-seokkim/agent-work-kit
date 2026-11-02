# Roadmap

What to work on in this repository. An agent picks the highest Ready item it can finish, says which in one line, and starts. Blocked items wait for the thing named in their row; do not start them and do not rewrite them. When Ready is empty, say so and stop. When an item is finished, delete its row in the same commit as the code and record the behavior change in [CHANGELOG.md](../CHANGELOG.md). Decisions that later work must respect go in [design.md](design.md).

## Ready

| Item | Done when |
|---|---|
| Fix the two flaky Windows CI tests: Python 3.11 lock creation and 3.12 session deadline, first seen failing then passing on retry in [run 41196269839](https://github.com/min-seokkim/agent-work-kit/actions/runs/41196269839). | The cause is found and the test is deterministic, or the product defect is fixed. Passing on a rerun does not count. |
| Find the intermittent Linux temporary-directory cleanup failure in CI and make it deterministic. | Same standard as above. |
| Make room in the command reference. `kit/reference.md` has 8,984 of its 9,000 words. Move one complete topic into its own guide, as `windows-recovery` was. | The reference has at least 500 words of margin, the moved text matches its source, and links and `kit guide` still work. |
| Check that the Windows file-replacement retry from `7e82e3f` also covers acceptance directory promotion in `review accept`, which failed with WinError 5 in real use. | A test holds the target open and acceptance still succeeds, or the gap is fixed. |
| Run the [snapshot recipe](../kit/reference.md#snapshot) on Linux. It has only been exercised on Windows. | The recipe works in bash or the reference gives a POSIX form, with a test. |
| Design one check for a failure entry that now has a recorded occurrence: F16, F21 or F22 in [kit/failures.md](../kit/failures.md). Follow the rule in design.md: a guard that can be a check becomes a `rules.toml` rule. | A rule or command fires on a fixture built from the recorded occurrence, with a `PREVENTS` declaration and the guard table regenerated. Or a written finding that no check could have caught it. |

## Blocked

| Item | What unblocks it, and who |
|---|---|
| Measure real work. Run one real task with the kit and record five values: user messages with repeated instructions counted; tokens (fresh input, cache write, cache read, output); failure entries that occurred or were caught; hook firings with wrong ones counted; what the user did not have to do. Never run the same task twice with and without the kit: the second run knows the answer. | The owner names one real task and runs it with the kit. The agent records the values. This unblocks the three rows below. |
| Evidence for the nine failure entries still marked "needs evidence" in `kit/failures.md`, or their removal. | Real work above. |
| Candidate guards: a state check before install commands (F11), a SessionStart hook printing the latest checkpoint (F29), refusing edits outside the named files (F19), call counts against the premium cap (F18), handoff size limits (F21). | Each is built only when real work shows its failure. F18 also needs the usage work below. |
| Usage accounting against current clients: a counting unit and matching across log files. | The owner supplies fresh Claude Desktop and Codex logs and decides what one call means. |
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
