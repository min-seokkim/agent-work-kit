# Documentation restructuring

Status: review. Owner: the current Codex session. Base: `f85a1ec`, with existing uncommitted installation, hook and documentation changes preserved. The document split is prepared for local verification; publication and CI remain pending. The owner requested the split and observation of awkit during the work.

## Outcome and scope

Separate current state, accepted design, future work, task details, evidence and release procedures. Keep `docs/development.md` as the entry point and `checks.toml`'s records path. Move existing material with its identifiers, numbers, commands, decisions, qualifications and sources intact. Preserve old heading anchors through the entry point and update incoming references.

Change `docs/`, the document pointers in `AGENTS.md`, the READMEs, the CHANGELOG and comments pointing at moved sections. Existing code and hook edits belong to earlier work. No runtime behavior change is part of this task.

Acceptance: all original sections and work items are accounted for, local links and anchors resolve, rendered Markdown is inspected, the writing check passes and a frozen snapshot passes the configured checks. Record automatic hook observations separately from manual commands. Local verification does not establish publication or Windows/Linux CI for these changes.

## awkit observations

- The resumed session created its SessionStart baseline without a manual mark command. The automatic `writing-request` injection is visible in the conversation and `.awkit/hooks.ndjson`, under session `01a16464-849a-7401-911b-11ad674f16a9`.
- PATH now resolves the installed awkit. The restricted tool shell cannot open its base Python executable; execution with permission succeeds. That shell limitation is separate from the observed native hook execution.
- The documents are moved through filesystem operations, and pointers are edited through `apply_patch`. A manual writing check must not be reported as an automatic PostToolUse check. The hook report records interventions and errors, not every successful no-op execution.
- Automatic `korean-writing` guidance fired on the README pointer edit. A deliberate em dash in `.awkit/probes/document-writing-hook.md` then caused the automatic PostToolUse `writing-check` to reject the tool result with the file, line and correction. Fixing that probe passed. This controlled probe establishes detection and recovery; it is not a defect prevented in the delivered documents. The observed report has two injections, one expected block and zero runner errors.
- Token use and repeated-instruction counts for this task are unmeasured. This session includes earlier planning and troubleshooting, so whole-session totals cannot be attributed to document editing.

## Verification and next action

The original 7,610-word development record became an 862-word entry point and topic records. All 13 work items are retained: nine in the roadmap and four completed or absorbed items in evidence. Every original inline literal, external source URL and failure ID remains present. Paragraphs that changed beyond relocation were checked against the original; they update navigation, historical tense or the newly observed hook status. The original and the preservation report remain in `.awkit/handoffs/documentation-restructure/`.

The first manual writing check covered 12 Markdown files with zero errors or warnings; the first link pass checked 71 local links and anchors with no failures. These counts precede the final observation notes. Markdown previews use Marked and headless Edge at 1280 pixels; inspect the retained screenshots with the final check record. The earlier direct headless Edge command produced no screenshot and is not counted as a successful visual check.

Final check metadata, snapshot ID and run folder belong in `.awkit/handoffs/documentation-restructure/validation.json`, outside the checked documents so recording results does not invalidate the snapshot. The check includes the existing shared-tree changes; it does not transfer ownership of their implementation to this task. Check for later edits before reusing a run. The [evidence record](../evidence.md) links this task; publication requires a separate commit/push and Windows/Linux CI.

The first aggregate snapshot, `eac9fbb8f640df74e582cd9ac44092232c741307`, is retained in `.awkit/reviews/review-h4qmghvh`. Ruff passed; the tool session ended before unittest produced a final result. The record still says running, but its runner process was absent when checked. Treat it as incomplete, not as a test pass or a reproduced code failure. The replacement run uses a new snapshot including the final navigation and observation notes.
