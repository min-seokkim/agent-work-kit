# Real data revision trial

> Historical record preserved from `90e2557`. Read [the current record](../../tasks/real-data-trial.md) before resuming. Stage-specific statuses and assignments below describe that revision. Local `.awkit/` paths remain relative to the repository root.

## Current status

Completed bounded analysis units. The CI-metadata revision and opt-in added-artifact visibility were delivered; a separate other-project analysis used existing guidance and channels. Frozen-runner use on that external analysis and causal benefit remain unverified.

Next action: Reuse the retained analysis and comparison results. Select any further real-data revision separately; no retrospective runner execution or new data command was assigned.

## Earlier scope and evidence

The following sections retain the original assignments and observations. Their stage-specific status statements are historical; use the current status above when resuming.

Status: M-113 returned the checked revision in R-066; planning retains that result. M-116 implements the bounded comparison-output follow-up; its technical and final combined delivery records are identified below. Parent base: `d04c994`. This task contributes to [roadmap item 5](../roadmap.md#next-work); using this repository's public CI metadata does not complete its separate requirement for data work in another project.

## Product question

Can an agent update a real analysis through existing awkit commands while preserving accepted source material and calculations? Record what the workflow preserves, what must be repeated and whether an observed omission warrants a feature. A correct report alone does not establish reduced effort or an awkit effect.

Planning chooses inputs, preservation requirements and product disposition. Implementation owns data retrieval, transformation, technical checks and retained artifacts. The research session read the baseline's sources and claims under M-013; it did not review implementation code or grant human approval. The isolated executor workspace has no remote and does not change parent product code, CI configuration or installed tools.

## Accepted baseline

M-110 selected three completed successful CI attempts from `min-seokkim/agent-work-kit`:

| Run | Commit | Jobs | Job span, seconds | Sum of job intervals, seconds |
|---|---|---:|---:|---:|
| 40069950544 | `2d41ba1` | 17 | 334 | 1807 |
| 40074074546 | `23575fb` | 17 | 340 | 1795 |
| 40076741585 | `b070924` | 17 | 328 | 1828 |

Each source is attempt 1 with two retained job pages containing 10 and 7 rows. The twelve original metadata responses, manifest, assumptions, transformation, independent recomputation, report and CSV outputs are retained with hashes. The task check passed source identity, pagination, all-row preservation, numeric recomputation and mechanical writing checks; artifact verification covered 49 files.

R-013 matched the report and runs CSV hashes, inspected source identities and pagination, and recomputed the first run's 334-second span and 1807-second sum from all 17 retained jobs. It read the other two aggregates without recomputing them. Planning read the fixed report, runs CSV and returned evidence, then accepted the baseline for this trial in M-113.

The sum includes overlapping jobs. Neither it nor the span measures queue time, billable usage, active effort or delivery duration. Workflow completion remains unknown rather than inferred from metadata update time. These selected attempts are not a representative performance sample. Human approval and rendered Markdown inspection are absent; no causal benefit is claimed.

## Revision result and product decision

M-113 added existing failed run `40068654398` at `335270b9bc1a06b0711888f94b5d27efbc9dcdda`. Its 17 jobs include 13 successes and four failures, with a 354-second span and 1778-second sum. The revised population has four runs and 68 jobs. All observed timestamps support nonnegative durations; this case supplies no new empirical coverage of cancelled jobs or missing timestamps.

R-066 reports that all 38 original input files remain byte-identical, all 51 original job rows and three run rows match in every field, and the three summary objects retain their values. No baseline response was refreshed. Snapshot `264b1591899819720e76bcb82106999dd2b783dd` passed four task stages in `review-7__7itji`; verification matched 72 artifacts. The original accepted label, `ci-timing-three-successful`, remains unchanged. Planning read the fixed revised report, preservation result and comparison summary; this is product interpretation of returned evidence, not another technical review.

Existing `review compare` reported 39 unchanged and ten changed accepted paths, with no missing or unexplained change. Its exit 1 represents expected differences. A separate manifest comparison inventoried 23 added artifacts, which the command did not list. Existing commands completed the task, but this extra inventory step is a concrete output gap for reviewing the whole revision.

M-116 assigns an opt-in `review compare --include-added --run` report that exposes added retained artifacts alongside the existing accepted-file comparison. Default output, accepted-file statuses and exit behavior stay unchanged; an addition alone is not an accepted-content regression. Identify the inventory's source and limits, without scanning unrelated worktree files, advancing acceptance or treating presence as correctness. Implementation must settle compatibility with existing run formats and report any conflict before changing the contract. No general data adapter or new command is selected.

Two corrective events remain separate. The first acceptance attempt failed during directory promotion with WinError 5; state inspection and one ordinary retry succeeded, with the cause unresolved. The first revision check caught Git newline normalization in copied baseline CSVs; a task-local attribute preserving their bytes corrected the setup. Both failed results remain retained. Neither event establishes a general product fix, and no acceptance retry mechanism is assigned.

The revision reused source files, CSV schema, calculations, the independent parser and task-local check configuration. Generic analysis work added one source and preservation checks. Awkit supplied acceptance, frozen checks, verification and comparison. The isolated repository, page size, optional lint and explicit addition inventory were experiment choices. The baseline recorded about 466 seconds from its declared setup start to the check, including tool latency and waiting; initial reading preceded that start. This is phase wall time, not active effort or a task-cost estimate.

Retain the existing data-work procedure with the bounded output follow-up. Neither the successful revision nor the additional inventory proves reduced user effort. Workflow reruns, CI fixes, publication and another project's setup remain outside this task.

## Comparison follow-up

M-116 appends an opt-in `added_artifacts` object with its manifest source, recorded-path scope and sorted path-only entries. It requires `--run`, preserves the accepted-file list and leaves additions outside the existing `unchanged`/exit decision. M-117 clarifies that CLI help describes exit 0 in terms of unchanged accepted files; additions are listed separately without deciding exits 0/1. Missing, malformed, mismatched or unsafe requested metadata fails with exit 2; the same default command remains independent of that inventory. No added content is opened or diffed, and unrecorded files are excluded. Metadata presence certifies neither content integrity nor correctness. The known schema-1 format supplies the inventory without a storage change.

The actual M-113 pair returned exactly the existing 23 additions while retaining 39 same and ten changed accepted files with exit 1. Default output before and after is byte-identical; the selected baseline, revised run and acceptance retained their bytes and mtimes. A separate fictional additions-only comparison exits 0. The inspected real task can now obtain additions from the comparison without a separate manifest-set calculation; time savings, fewer reminders and broader coordination gains remain unmeasured.

Product snapshot `41a09bb` passed Ruff, 38 focused review/kit tests with 3 skips, and writing checks in `review-z0tn2x3p`. The local actual-link case was skipped because Windows denied symlink creation; Linux CI runs the same case. Tests also cover missing/changed accepted files, no additions, invalid/unavailable metadata, recorded-path safety, control metadata only when declared and no added-content reads. The existing F16 guard declarations are unchanged; the command reference has 8,993 words. Implementation read source/diff and actual CLI output. Documentation rendering remains unperformed under the recorded browser/native-control restrictions; no independent review or human approval is claimed.

`.awkit/handoffs/compare-added-artifacts/delivery/validation.json` owns the exact cumulative checked tree, committed revision, CI and final installation state. Its `report.md` returns that final delivery state through the implementation channel. Product-only evidence, before/after CLI outputs, focused/full check runs and installation comparisons remain under that folder. This delivery combines the five product files with the transferred roadmap and this record; it excludes the read-only data workspace and does not diagnose the unresolved acceptance promotion failure.

R-070 completes delivery at `9e17bdb`. The receipt reports 371 tests with eight local skips, all seventeen Windows/Linux jobs passing in [CI run 40083120682](https://github.com/min-seokkim/agent-work-kit/actions/runs/40083120682), and matching installed source, kit and managed skills. Planning then used the installed option on the retained real pair and observed the separate 23-path inventory with expected exit 1. M-119/M-120 retain that product result; no further comparison extension is selected. Rendering, human acceptance and measured savings remain unverified.

## Retained evidence

The local baseline snapshot is `614455d2acc0c6502c338c1642fe66a4ece59b68`; run `.awkit/handoffs/ci-data-trial/executor/reviews/review-1fjrhfx9` owns the frozen artifacts. Its receipt and effort record are in the executor directory. Research evidence is `.awkit/handoffs/product-research/executor/ci-data-reading/decision.md` with `source-reading.json`.

Implementation channel R-065 returns M-110; M-113 accepts the baseline and assigns the revision, returned in R-066. Its frozen artifacts are under `.awkit/handoffs/ci-data-trial/executor/reviews/review-7__7itji/`; `revision-report.md`, `revision-comparison.json` and `revision-effort.json` in the executor directory retain the feedback and failures. Research R-013 returns M-013; M-014 records its disposition. `.awkit/handoffs/collaboration-obligations/task.json` tracks active obligations. These ignored paths are local evidence locations, not files shipped in the repository. Parent verification and installation receipts remain separate from this data task's checks.

## Other-project observed collection analysis

M-065/M-066 selected an actual metadata task in an existing personal data project and established its permitted input. M-067 assigned a bounded analysis of one completed UTC day. R-072 returned the result; M-068 accepted that observed-history outcome. The data and row references remain ignored inside the source project. The generalized memo is .awkit/handoffs/product-research/executor/next-data-task/analysis-result.md.

The report distinguishes manifest requests, raw observations, first-seen documents and version observations. It retains failed and duplicate requests and anchors publication time to supported versions at first acquisition. One conflicting publication case is excluded explicitly. The interval supports a historical quality case, but observed collection covers only part of the day, historical expected-request configuration is unavailable and no day snapshot exists. It does not qualify a full daily evaluation window. The project's current roadmap already records the later failing-feed removal, so planning selected no repeated repair or new collector.

Research reports preserved source identities, a separate SQLite recomputation and a bounded source-metadata comparison. This is research self-execution and recomputation, not an independent person reviewing the work. The initial helper-creation quoting failure and following missing-helper invocation remain retained; neither was an awkit defect. Rendering, real owner acceptance, operational repair and detection quality remain unverified.

R-073 separates actual kit use from ordinary analysis. The work-types, checking and writing guides supplied applicable instructions; existing channels carried assignments and results. The project-local c3dd1bf writing checker and a source invocation checked mechanical prose patterns. Python and SQLite performed capture, arithmetic, row classification and recomputation. No review snapshot/check configuration or run was prepared for this data unit. The separate managed-session validation package is not evidence for this analysis.

This supplies an actual other-project data case using kit guidance and communication. It does not demonstrate the frozen review runner on that project's real data, a revision against an accepted analysis, reduced effort or causal kit benefit. No repeated owner instruction, unnecessary owner approval or human relay was reported within the bounded execution. The non-use of the review runner was a task choice, not evidence of a missing external-data feature. Planning selected no new data command or retrospective validation run.

The stale project reference to shared instructions required source resolution. R-075 reports the narrow project-local AGENTS pointer repair complete using the verified shared source, with unrelated source/index content preserved. This is a reported repair separate from the completed calculation; active-session instruction reload remains unverified.
