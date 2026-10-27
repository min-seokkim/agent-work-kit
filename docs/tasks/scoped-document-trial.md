# Scoped document revision trial

## Current status

Completed document trial. A local correction and substantive revision were accepted with source preservation, scoped evidence reuse and explicit reporting of missing review. Delivery evidence remains below.

Next action: Reuse the demonstrated procedure for a selected revision. Productivity and intended-reader acceptance belong to later real-use evaluation.

## Earlier scope and evidence

The following sections retain the original assignments and observations. Their stage-specific status statements are historical; use the current status above when resuming.

Status: document outputs accepted; cumulative repository delivery is tracked in the receipt below. Base: `ccea298`. The planning session owns scope, source premises, acceptance and repository records. The existing implementation session owns the assigned document outputs and execution evidence. This continues the [document plan](../document-workflow-plan.md#scale-the-work-to-the-change) after the [planning trial](planning-implementation.md). The document assignment adds no product behavior.

## Outcome and inputs

Exercise the existing partial-edit procedure on one local wording correction and one substantive revision. Determine which source and review evidence can be reused, which work the change requires, and whether command success is reported separately from content and rendered inspection. The comparison-report feature is not a prerequisite.

The inputs are independently invented fixtures under `.awkit/handoffs/scoped-document-trial/`. They contain no private originals or real institutional policy. The Korean baseline documents have actual English drafts and source premises. Their accepted status is a scenario premise, not a person's acceptance of a real document. The trial evaluates actual editing and verification of fictional material; it does not establish usefulness to the intended readers.

| Task | Reader and requested change | Preservation and acceptance |
|---|---|---|
| A, equipment return guide | Help a borrower understand who completes a return and when. Revise one sentence under the return-status section. | Keep all other bytes, numbers, headings and the status label. Submission records a request; the operator checks equipment and components before completion. Missing components keep the return pending. |
| B, export pilot brief | Help an operations lead understand new pilot results, the current operating decision and evidence needed before expansion. Revise the earlier plan substantively. | Derive counts and any timing statistic from the supplied CSV with explicit denominators. Preserve two operators, synthetic inputs, the production-data restriction and decision ownership. A proposed correction is unapplied, retries have not run and expansion remains unapproved. Preserve the title and operating-conditions anchor. |

The executor uses a nested Git repository under the handoff folder, with fixed input hashes, owner-identity baseline commits and awkit snapshots. Source and baseline inputs remain distinct from candidate documents. Only that isolated repository's Git setup is assigned initially; the root index, source, kit, tests and installed environment remain outside the document assignment.

## Review and evidence

Draft only the changed A passage and the full revised B brief in English, then write Korean. Retain scoped fact, Korean-only and overall-reading observations. Inspect the frozen Markdown and rendered output at 1200 px and 390 px. The planner reads both final documents against sources and inspects those outputs. This is informed review, not an independent or blinded evaluation.

Before B's rendering is inspected, retain an explicit incomplete checkpoint even if mechanical checks pass. Complete the missing inspection afterward on identified sources. This is a reporting control; it does not establish that awkit detects omitted human review. Source changes require renewed affected evidence, while unchanged-source evidence can be reused.

Keep full-file writing reports, snapshot IDs, check runs, artifacts and source hashes. Separate preparation, drafting/review, automated execution and channel waiting where observed; missing durations and task usage remain unknown. Record actual mistakes and corrections, including avoidable repeated work. The two tasks differ in content and scope, so their durations cannot establish a causal productivity gain.

## Collaboration and current evidence

The old channel is closed. The owner supplied one restart input because a stored message cannot wake an ended session. The new channel is `.awkit/scoped-document-trial.sqlite3`, with planner at `main` and executor at `reviewer`. The resumed executor acknowledged readiness in `R-001`; `M-002` assigns both documents and their bounded evidence. No additional agent is assigned.

A bounded metadata read in `session-metadata.json` identifies both clients as `codex_vscode` `0.162.0-alpha.17.2`, with latest model contexts `gpt-6-astra`/high for planning and `gpt-6.1-sol`/high for implementation. These are observed context records, not API-call counts or task-usage measurements.

A fresh fetch confirmed `HEAD` and `origin/dev` at `ccea298`. The isolated installed-runtime comparison matches that commit: 24 source modules, five example modules, 29 kit resources and 16 generated user skills, with no module/resource-set difference. Existing Python 3.14.7 remains. The four initial handoff/baseline text checks report zero errors and warnings; this is not acceptance of revised output. The first attempt to create the ignored handoff folder failed under filesystem permissions; approved directory creation succeeded before any input was written.

## Accepted results

The executor returned `R-005`; the planner accepted both documents in `M-006` at nested snapshot `461aeddea0eaa73676897faeaaa176371992e6ac`. Run `executor/reviews/review-8yr3s8cf` passed complete-file writing checks, retained both Markdown artifacts and reported no missing artifacts. Nested `check done` and artifact verification passed. This checks the document workspace, not the root repository records.

A changes exactly one sentence; reversing that replacement restores every baseline byte. B reports ten completed outputs and two failures from twelve inputs, with a median of 82.5 seconds across the ten successful outputs. Failed durations remain unknown. The brief preserves operating restrictions, the developer's maintenance role, decision ownership, and the unapplied correction, absent retries and unapproved expansion. New pilot results are identified as additions from B2.

| Finding | Discovery and correction | Evidence and consequence |
|---|---|---|
| A's first revision repeated the adjacent protected sentence | Planner reading after the writing pass; executor shortened only the assigned sentence. | `a-byte-preservation.json` and `a-diff-final.txt` retain the exact scope. Initial executor reading noticed repetition but left it; a protected neighbour did not prevent revising the assigned sentence. |
| B's correction instruction left the actor implicit | Executor prose review before the first cumulative snapshot; the developer became the explicit actor. | English and Korean drafts remain in the executor folder. |
| B omitted the developer's maintenance role | Executor rereading against B1 after a mechanical pass and rendering; the role was restored in the English draft and Korean brief. | A new snapshot, check and affected B renders cover the correction. Planner's initial content review also missed the omission. |
| Narrow rendering split Korean words | Executor visual inspection of the first captures; shared CSS changed to keep words together. | Original CSS and captures remain. All affected baseline/candidate images were recaptured; unchanged text checks were reused. This was a trial renderer setting, not an awkit defect. |
| Console output displayed corrupted Korean | Executor checked the UTF-8 file bytes and read with explicit encoding. | No source corruption or writing-check defect was established. |

The planner inspected all four final candidate images and four baseline images at 1200 px and 390 px. The corrected outputs show readable wrapping without clipping or horizontal overflow. The fictional label is outside each article, and B retains its operating-conditions anchor. A's final renders come from `rendered-final-a`; B's come from `rendered-final`, whose source bytes match the final snapshot. Baselines come from `rendered-afc5abdc-02`. Manifests retain source, HTML and image hashes, viewport, CSS and renderer identity.

The explicit `incomplete-before-render.txt` checkpoint reported missing visual review despite passing commands. The later inspections cover that gap on identified sources. This demonstrates accurate reporting by the sessions; automatic detection of an omitted review remains unverified. Both sessions were informed about the task. Intended-reader understanding and acceptance were not tested.

## Reuse and next decision

A reused the audience, source policy and unchanged content evidence. B reused unchanged B1 conditions but required new source arithmetic and review of the revised explanation. Unchanged B render evidence remained usable after the later A correction because its source hash matched. Four frozen check runs followed actual content revisions; CSS-only correction required rendering, not another prose check. Evidence reuse depended on inputs and coverage rather than the size of the edit alone.

The setup, phase boundaries and automated rendering intervals are retained in `executor/timing.json`. Active drafting/review time, total waiting, task cost and productivity effects remain unknown. The two tasks have different inputs and scopes. No existing-finding block occurred in these clean fixtures, so this trial does not reproduce that earlier burden or justify changing enforcement.

The bounded follow-up is the [writing-comparison report](writing-comparison.md), following the contract assigned in `M-006` and reviewed before `M-008` authorized implementation. Its justification remains the proposal trial's existing-finding burden. Existing findings and full-file exit policy remain visible. Presentation phases remain open. No additional agent or new timed window was started.

Detailed local evidence lives under `.awkit/handoffs/scoped-document-trial/`: `executor/final-validation.json`, `planner-acceptance.json`, original inputs, intermediate drafts and renders. Root delivery receipts will be retained separately in `delivery/validation.json` so they can identify the delivered commit without changing its tree.
