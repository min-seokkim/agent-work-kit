# Usage log compatibility

Status: planned. Owner: the implementing session assigned to roadmap item 6. Evidence base: `89549b7`, with the observed parser at `0f41f0b`. Scope: Codex message and turn counting, measurement completeness and regression fixtures. This plan selects no new schema or implementation; the owner chooses the next assignment.

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

Choose whether to preserve existing fields with clearer labels or change the result format after inspecting consumers. Any schema or behavioral change needs a CHANGELOG entry and compatibility tests; the plan does not silently reinterpret format 2. This is a prerequisite to using counts for a premium-call cap or productivity comparison.

## Completion and next action

Accept a fix after the modern-message reproducer, overlap/exclusion cases and existing token/Claude tests pass on a frozen snapshot, and supported client logs agree with a manually classified sample. Record client versions and sample boundaries without publishing private messages. Follow repository Windows/Linux validation and installation-provenance requirements when delivering executable changes. Unsupported formats remain visible. Next: assemble the fixture matrix and propose counting and completeness semantics before editing the parser.
