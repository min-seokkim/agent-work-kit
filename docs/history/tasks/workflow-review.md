# Document workflow trial

> Historical record preserved from `90e2557`. Read [the current record](../../tasks/workflow-review.md) before resuming. Stage-specific statuses and assignments below describe that revision. Local `.awkit/` paths remain relative to the repository root.

## Current status

Completed assigned local proposal trial, delivered in `89549b7`. Check/report scope was clarified; no push or installation change was part of that trial. The historical automatic-hook failure remains unresolved.

Next action: Use [writing comparison](../../tasks/writing-comparison.md) for the delivered follow-up and [connection diagnostics](../../tasks/connection-diagnostics.md) for the deferred hook investigation.

## Earlier scope and evidence

The following sections retain the original assignments and observations. Their stage-specific status statements are historical; use the current status above when resuming.

Status: accepted for local delivery. Owner: the main Codex session, with the existing Bimmer session as reviewer. Base: `0f41f0b`. The owner authorized a time-limited collaboration and a final local commit. Closing preparation starts at the agreed deadline; necessary checks and the commit may finish later. Shutdown belongs to the reviewer only after both sessions explicitly report completion. No push or installation change is part of this trial.

## Goal and scope

Use a real proposal-writing task to identify where awkit's evidence helps and where its output can overstate what was checked. Accept only changes supported by observed behavior, preserving the existing check decisions, exit codes, JSON fields, writing requirements and project ownership. The main session edits this repository; the reviewer owns the proposal and its evidence. No additional agents participate.

The change is limited to check summaries in `src/awkit/checks.py`, the reporting and writing guides, the command reference, regression checks and these development records. The design decision against expanding the done check remains in force. Acceptance requires a frozen snapshot passing `checks.toml`, review through the existing channel, inspection of rendered documentation, a local owner-authored commit and a record of remaining limits.

## Observations

The reported four hook firings were confirmed in the other project's log: two guidance injections and two blocks. Its retained result records three passing commands: a proposal and work-log pattern check, a check of three extracted decision lines, and whitespace inspection. This confirms those commands' recorded outcomes; it does not establish preservation review, research accuracy or rendered inspection. The English draft exists. The reviewer reported missing preservation and review evidence in the first task and completed those steps in the new exercise.

Current source inspects complete Markdown files without distinguishing old findings from introduced findings. Earlier synthetic evidence in [Connection diagnostics](connection-diagnostics.md#writing-scope-and-path-limits) already showed why added-lines-only inspection loses mixed endings and newly exposed prose. The new report supports the friction but does not settle a safe automatic baseline policy.

The installed runtime's metadata names the base commit. All 23 installed Python files and 29 kit files match that commit after line-ending normalization; all 16 generated user skills match the installed guides. In the restricted shell, the installed executable could not launch its base Python. Outside that shell, the same executable imported `checks`, passed doctor diagnostics and reported no changes through `check done`. The reported automatic Stop-hook ImportError remains unexplained. These observations do not establish a missing module, installation repair or restoration of automatic execution.

## Decisions and verification

Text summaries distinguish mechanical pattern inspection, unchanged state and a passing run matching the repository tree. They do not change acceptance logic or claim content coverage. Reports distinguish automated evidence, agent or human reading with its method, and required checks omitted with the reason. No new checklist or automatic judgment of prose is added.

The channel is the existing SQLite file named by the owner's handoff. Both roles have acknowledged receipt; posting alone is not delivery evidence. The handoff named an earlier main session; actual tool-call logs identified the current session, and the main corrected its identity through the channel. Both sessions' logs record `gpt-6-astra` with high effort. The main uses `codex_vscode` client `0.162.0-alpha.17.2`; the reviewer uses `Codex Desktop` client `0.163.0-alpha.11`. Review is by an actual user session exposed to the implementation discussion, not a blinded assessment. Usage attributable to this unit remains unverified.

Incremental review of snapshot `5f9d243` found two Minor wording issues and no High or Major findings. Both were accepted: qualify unexamined content as outside this command's scope so a separate review is not denied, and retain the explicit duty to report unchecked work and why. Main self-review found the same issues before receiving the response. The reviewer inspected the frozen diff without repeating the main's tests.

The first focused run failed one new fixture because Windows text output introduced CRLF that Git treated as trailing whitespace. Explicit LF in that fixture fixed the failure; a fresh run passed all 11 focused tests. The first full snapshot run, `.awkit/reviews/review-40scf4j4`, passed 232 of 236 tests with four skips but failed overall because Ruff was absent from the inherited PATH. Later runs supplied the existing local Ruff path without installing anything. Main inspected the six changed document sections rendered from the snapshot at 1200 px: no clipping or broken tables was observed. This is a local Markdown preview, not verification of every renderer or viewport.

Final review of `47402bb` requested changes after a fresh run, `.awkit/reviews/review-zrkhokea`: Ruff passed, and 236 tests yielded 231 passes, one failure and four skips. The failure was deterministic: the every-session guides had 2,010 words against their 2,000-word limit. The main shortened the report paragraph to bring the combined count to 1,993, preserving its duties and the limit. This Major finding came from the reviewer's final check. Eight synthetic writing cases retained by the reviewer have identical JSON reports and exit statuses for the base and candidate; this establishes compatibility for those fixtures, not real document quality.

The reviewer accepted the focused correction in `80b19a` and ran `.awkit/reviews/review-m9dcl770` in a fresh worktree. Ruff passed; 236 tests yielded 232 passes and four skips. All three awkit review findings are resolved in that snapshot. Main compared the eight retained synthetic results directly and confirmed their JSON and exit-code equality.

Requests through correction acceptance: main sent one question, one incremental review, one final review and one focused test request; reviewer sent two questions for the proposal review and its corrections. All six received replies. Main ran its own focused and full checks; the reviewer ran the final and corrected-snapshot checks. No subagent verifier or additional review session participated.

## Review of the live exercise

The reviewer completed an English draft, a twelve-item preservation contract, three reading passes and fifteen screenshots for the proposal exercise. Main read the frozen proposal and evidence, verified all seven retained artifacts and both normalized Markdown hashes, checked selected official sources and inspected four screenshots. The mobile images confirm that an orphaned syllable and a crowded footer link were corrected. The missing-data and driving-state images retain their mock labels and uncertainty. Main's four-image inspection does not replace the reviewer's full rendering pass.

Cross-review found two Minor evidence issues. A schedule detail was described as restored from the preserved original although the original never contained it; the reviewer corrected the attribution. An exact cutoff hour needed a more precise citation. The retained official application form contained the hour, which main verified, and the proposal now cites that form directly. Main accepted both corrections in proposal snapshot `059e585` through M-023, after reading its frozen diff and the corrected review note. A web retrieval failure for another source was resolved by the reviewer's retained HTTP response; main read the relevant notice excerpt. These findings concern the review report and its sources, not an awkit implementation defect.

The original writing requirements already covered preservation and rendering. Applying them with retained evidence yielded specific corrections in this exercise; it does not show that the new summaries enforce those steps or improve productivity. The candidate was tested separately and was not installed in the working project. Historical whole-file writing findings and repository changes outside the proposal remain unresolved there.

Late measurement triage confirmed a separate usage-format gap. The reviewer supplied a sanitized current Desktop record with a user message marked by `content_item_kinds=["user.text"]`; main reproduced `user_messages=0` with `total.complete=true`. The parser counts only the older `payload.type=user_message` representation, while completeness concerns token fields and log parsing. The reviewer also observed repeated turn-context rows; the current `calls` value counts those rows, not proven unique turns or API responses. No token-total error was established. The local `usage-modern-fixture.jsonl` and `usage-triage.json` retain the reproduction. A separate fix needs modern and legacy overlap, generated-message exclusions, missing IDs and repeated-context cases before changing counting semantics. This delivery does not change usage parsing or report whole-session totals as collaboration cost.

The final tree, including these record edits, must pass `checks.toml` before the authorized local commit. Its snapshot, run folder and commit receipt are recorded in `.awkit/handoffs/workflow-review/validation.json`, alongside commands, rendered images and remaining limits. This keeps the checked tree fixed while its receipt is written. Linux, installed candidate behavior and native automatic hook execution remain unverified; the installed runtime remains at the base commit during the trial. Existing versus introduced writing findings still need a separate design decision; this trial changes explanations, not that classification.
