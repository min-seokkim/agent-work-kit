# Documentation restructuring

> Historical record preserved from `90e2557`. Read [the current record](../../tasks/documentation-restructure.md) before resuming. Stage-specific statuses and assignments below describe that revision. Local `.awkit/` paths remain relative to the repository root.

## Current status

The owner-requested navigation refresh is implemented over `a2a0c43`. Development summaries, task categories and current conclusions now precede the retained history; validation and delivery are tracked in the receipt below.

Next action: use the refreshed entry point and task categories. Consult the receipt for completed verification and delivery stages; finish any stage it still records as pending. The [navigation refresh](#current-navigation-refresh) owns this work; earlier split and README records remain historical.

## Current navigation refresh

Base: `a2a0c43`. Owner: the current implementation session. The owner requested the navigation changes after inspecting the accumulated records. Scope: `docs/development.md`, `docs/roadmap.md`, `docs/evidence.md`, the document workflow plan, all 21 existing task records and the unreleased CHANGELOG. No new task document or product behavior is added.

Acceptance: the development summary names shipped session controls and current limits; the roadmap separates current work, deferred/blocked outcomes and completed units; every task opens with a conclusion and next action. Preserve earlier assignments, acceptance conditions, failures, artifact paths and heading anchors. Historical status text must not appear to be a fresh assignment. The prior development overview is retained in the existing evidence record.

Verification and delivery receipts belong in `.awkit/handoffs/documentation-restructure/current-navigation.json`, outside the frozen files. Compare task bodies and moved summaries with the base, check local links and anchors, run writing and frozen `checks.toml` checks, and inspect the changed Markdown rendering. Source reading is implementation self-review; neither a mechanical pass nor historical review establishes human acceptance of this revision. Publication and exact-installation results are recorded in the receipt, without rewriting the checked files to add their own result.

## Earlier scope and evidence

The following sections retain the original assignments and observations. Their stage-specific status statements are historical; use the current status above when resuming.

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

Final check metadata, snapshot ID and run folder belong in `.awkit/handoffs/documentation-restructure/validation.json`, outside the checked documents so recording results does not invalidate the snapshot. The check includes the existing shared-tree changes; it does not transfer ownership of their implementation to this task. Check for later edits before reusing a run. The [evidence record](../../evidence.md) links this task; publication requires a separate commit/push and Windows/Linux CI.

The first aggregate snapshot, `eac9fbb8f640df74e582cd9ac44092232c741307`, is retained in `.awkit/reviews/review-h4qmghvh`. Ruff passed; the tool session ended before unittest produced a final result. The record still says running, but its runner process was absent when checked. Treat it as incomplete, not as a test pass or a reproduced code failure. The replacement run uses a new snapshot including the final navigation and observation notes.

## README current-state refresh

The introduction refresh at base `9e17bdb` covers `README.md` and `README.ko.md`. Its outcome is a concise introduction that explains the current capabilities and product direction. Acceptance requires source consistency, equivalent English and Korean meaning, independent reading, rendered inspection, link checks and the configured frozen-snapshot checks. Existing roadmap and application-trial edits belong to other work.

The preservation list covers the instructions/CLI identity, supported work types, Git and Python requirements, development-install status, basic installation and agent-reference routes for maintenance, existing-project preservation, local cross-provider channels, license and attribution. Sources are the development, design, roadmap and writing-outcome records, with command and installer claims checked against source. The English README is the full draft used for the Korean rewrite. Previous wording remains in Git.

The editorial correction preserves the original five sections and their headings, explains current use and sends development plans to the roadmap. Preserving sections does not freeze their content: Why must reflect the broader existing scope, including task definition, research and analysis, meaning and accepted-result preservation, session coordination and delivery confirmation. Reference READMEs are [Superpowers](https://github.com/obra/superpowers/blob/main/README.md) for the practical workflow explanation, [Spec Kit](https://github.com/github/spec-kit/blob/main/README.md) for its task/outcome table, and [OpenSpec](https://github.com/Fission-AI/OpenSpec/blob/main/README.md) for the install-to-first-use sequence. Their product claims are not evidence about awkit. These references support content updates within the existing structure; no new top-level section or development-plan inventory is needed.

The expanded introduction explains built-in capabilities through the problems they address and the results a person can inspect. Detailed command operation belongs to the agent-facing kit; the README retains only the basic setup commands. Document writing gets a subsection within the existing work-types section, covering source fidelity, Korean drafting, scoped revision, carrying corrections forward and mechanical comparison. Guidance, executable checks and editorial judgment remain distinct. This additional scope justifies a focused follow-up review of the new explanations.

The main agent compared facts with the sources, read Korean independently, and checked order and terminology. A read-only `readme_review` subagent found no material issues in the first draft after spot-checking implementation. The owner then corrected its editorial scope as described above; the main agent checked the affected passages. The same reviewer checked the expanded scope against the guides and reference and found no material issues. Both reviews were source-text reviews; the main agent inspected the rendered documents. The reviewer's actual execution model and bounded token usage are unavailable; no efficiency benefit is claimed. Local previews use Marked and headless Edge at 1280 pixels. Screenshots and final receipts record the inspected revision; a local preview does not establish GitHub rendering or human acceptance.

Validation receipts are retained under `.awkit/handoffs/readme-refresh/`, outside the checked files. The initial restricted-shell Python failure was resolved by running the installed CLI with permission; its provenance matched `origin/dev`, as did 26 source files, 29 kit files and 16 user-skill payloads after line-ending normalization. The first preview invocation lacked Node on PATH; the explicit runtime path rendered successfully. The first full run, `review-tp0c_6c5`, could not launch Ruff because it was absent from PATH. Its logs are retained; the replacement uses the existing Ruff installation. Frozen checks and delivery receipts in that folder determine final verification status; this record alone does not establish a pass or publication.

## Documentation system delivered through 26e2d34

> The following task record is preserved from `26e2d34`; the documentation system was delivered in `cb2a385` with a Windows test-path correction in `26e2d34`. Its receipt records the passing rerun and unresolved intermittent Git cleanup failure.

## Documentation restructuring

### Current status

The owner selected an agent-first development system: short current task records, separate historical records and task-based access to validation evidence. This revision replaces the navigation-only refresh in `90e2557`.

Next action: read `.awkit/handoffs/documentation-restructure/structure.json` for the exact snapshot, checks and delivery stages. Finish any pending stage against that revision. Once delivery is complete, select further product work with the owner from the roadmap.

### Scope and acceptance

ID: `documentation-restructure`. Owner: the implementing session until delivery. Base: `90e2557`. Scope: development documents, their incoming references, a repository-only evidence catalogue script and its tests. Product commands and raw evidence retain their existing formats and locations.

Acceptance: an agent can find the selected task, its next action, source requirements and evidence without reading execution history. Preserve prior records, identifiers, heading anchors, failures and qualifications in `docs/history/`. Keep one current record per task. Catalogue local evidence by document references, identify shared and unreferenced collections, and report absent or unreadable sources without inferring a pass. Retain dirty workspaces and run artifacts.

### Verification and delivery

The receipt above records preservation and link checks, catalogue tests, reading and rendered inspection, frozen `checks.toml` results, commit, Windows/Linux CI and exact-installation comparison. Keep it outside the frozen files. Main-agent reading is self-review; mechanical checks and historical reviews do not establish human acceptance of this rewrite.

Earlier navigation, cleanup and split receipts remain in `.awkit/handoffs/documentation-restructure/`; this revision uses new filenames. Run `python scripts/evidence_catalog.py` to refresh `.awkit/evidence/index.md` and `catalog.json` from the local checkout. Generated lists describe availability and references; verification claims require the cited run and its snapshot.

### History and evidence



[Full record and verification history](documentation-restructure.md) preserves the original scope, decisions, failures and evidence paths. The [evidence guide](../../evidence.md) explains how to find retained local artifacts.
