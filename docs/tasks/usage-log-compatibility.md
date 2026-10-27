# Usage log compatibility

## Current status

Completed format-3 compatibility unit, delivered through `31a1599` with Windows/Linux CI. Ambiguous exact counts remain unknown; token completeness and human-input coverage remain separate.

Next action: Select further accounting work only with suitable client samples and a settled counting unit. Fresh live-client coverage, cross-file identity and task-bounded usage remain open.

## Earlier scope and evidence

The following sections retain the original assignments and observations. Their stage-specific status statements are historical; use the current status above when resuming.

Status: implemented and delivered with Windows/Linux CI. Owner: the implementation session in the [planning trial](planning-implementation.md), with contract and acceptance owned by its planner. Evidence base: `89549b7`, extended by discovery at `12d402a`. Scope: Codex human-input accounting, measurement completeness and regression fixtures. The owner delegated bounded implementation selection to the planner for this trial; the approved first unit is below.

## Reproduced gap and limits

The [proposal trial](workflow-review.md) reproduced one explicitly human-marked Desktop message reported as `user_messages=0`. The record uses `response_item`, a user-role message and `internal_chat_message_metadata_passthrough.content_item_kinds=["user.text"]`; the parser counts only `payload.type=user_message`. Its `total.complete=true` describes token fields and log parsing, so it does not establish successful human-message classification. The retained fictional fixture and result are `.awkit/handoffs/workflow-review/usage-modern-fixture.jsonl` and `usage-triage.json`.

The reviewer also observed thirteen turn-context rows with eleven unique turn IDs. Current `calls` counts context rows. The cause of repetition and correspondence to API responses are unverified; no token-total error was established. Whole-session totals include activity outside the collaboration and cannot be used as its cost.

## Implementation decisions and checks

Inspect `src/awkit/usage.py`, its CLI consumers and `tests/test_usage.py` before choosing a representation. Preserve token accounting and existing Claude Code coverage. Use independently authored fictional fixtures shaped like observed logs; keep private session contents outside this repository.

| Case | Required result or explicit uncertainty |
|---|---|
| Legacy event message; modern marked message; both representations of one input | Count supported human input once, with a documented correspondence rule. Never deduplicate distinct inputs just because their text matches. |
| Injected instructions, hook feedback, tool output and UI answer wrappers | Establish origin from observed metadata and fixtures; do not count every user-role record as human input or assume every client uses the same markers. |
| Repeated or missing message IDs, missing metadata and a partly written log | Expose incomplete classification when identity or origin cannot be established. A measured zero must mean zero supported observations, with coverage stated. |
| Repeated turn/root-turn IDs, model changes and context rows without IDs | Define the unit being counted before deduplicating; context rows, logical turns and API responses are different quantities. Retain unresolved cases. |
| Complete token fields but uncertain human-message coverage | Report token completeness separately from interaction-count coverage; table and JSON output must communicate the same limits. |
| Resumed sessions, cumulative counter resets and a task spanning two logs | Derive task usage only from bounded records with verified counter semantics. Otherwise retain whole-session totals under that label and mark task usage unverified. |

Any schema or behavioral change needs a CHANGELOG entry and compatibility tests. The approved migration below replaces format 2 explicitly. Reliable interaction accounting remains a prerequisite to using counts for a premium-call cap or productivity comparison; the first unit does not establish API-call measurement.

## Approved first implementation unit

Discovery at `12d402a` reproduced the earlier modern-message zero and a message-only log whose entire thread was omitted when no model or token record existed. A bounded sample from the implementing IDE session contains both modern and legacy representations of one visible input. Timestamp and text match, but no shared message or turn identity establishes correspondence. The metadata-only evidence is retained under `.awkit/handoffs/planning-implementation/u1/`; original private records stay in their source location. This sample establishes one IDE shape, not coverage of every client.

The planner approved a default migration to result format 3. There is no parallel legacy-format mode in this unit. Targeted source inspection found the CLI and tests as result consumers; the hook also imports the Claude classification helper, which remains stable. External consumers are unknown, so the CHANGELOG, CLI help and reference must identify the changed nullable input count and counted units. The package version remains unchanged while unreleased.

The implementation retains supported human observations by representation and reports an exact input count only where established. Ambiguous overlap, unknown origin and conflicting identity remain explicit; text or timestamp equality does not authorize deduplication. Distinct modern IDs with identical text remain distinct. Replayed IDs require consistent identity and content, and deduplication stays within one file. The single marked modern fixture must expose its human observation even when its identity coverage is limited.

Token completeness remains separate from interaction coverage in JSON and the table. A thread with human observations survives missing model and token records, with unmeasured tokens shown as missing. Unknown thread counts must not become an unqualified exact aggregate. Codex `calls` and model totals keep their numerical computation and are labeled as model-bearing context rows. Claude accounting and the existing token algorithms stay intact. Resumed logs, cross-file correspondence and cumulative-counter resets remain outside this correction.

Acceptance requires the original reproducer, the discovery fixture matrix, malformed and incomplete records, identity conflicts, separate files reusing IDs, table/JSON agreement and existing Claude/token regressions. The current IDE sample must report its observed representations and ambiguity correctly. No exact count for that mixed stream, new live Desktop coverage or API-call metric is promised. Frozen checks and platform delivery remain required for executable changes.

## Completion and next action

The planner accepted snapshot `438ed17884bd407d2956bf72bd77be042e7b952d` after inspecting the diff, regression cases, retained output and full check record. Local commit `7977b35` has exactly that tree. `.awkit/reviews/review-_ajws8tj` passed Ruff and ran 248 tests on Windows/Python 3.14.7: 244 passed and four were skipped. The first focused run failed on an implementation indentation error; the corrected run and final 20-test usage run are retained. An incorrect local Ruff path was an invocation error, corrected without installation.

The original modern fixture now displays one supported observation and an unknown exact count because its message ID is absent. The bounded IDE sample reports one legacy and one modern observation with ambiguous correspondence. Previously retained token, model, call, effort, elapsed-time and command fields match the base for that sample. The planner read both CLI outputs and inspected rendered reference and CHANGELOG sections from the accepted snapshot at 1200 px; no clipping or horizontal overflow was observed. This is informed planner review, not an independent review.

The five-file product snapshot excluded concurrent planning documents. Cumulative snapshot `98a027b` and [CI run 39899544004](https://github.com/min-seokkim/agent-work-kit/actions/runs/39899544004) verify their integration in `31a1599`. The [planning record](planning-implementation.md#delivery-and-remaining-limits) identifies final environment receipts. Record further client versions and sample boundaries without publishing private messages. Fresh live Desktop and Claude samples, cross-file correspondence, logical/API-call units and reset-aware task usage remain unresolved. Next: select further accounting work only when evidence can settle those meanings.
