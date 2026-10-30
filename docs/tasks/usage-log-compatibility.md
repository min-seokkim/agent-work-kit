# Usage log compatibility

## Current status

Completed format-3 compatibility unit, delivered through `31a1599` with Windows/Linux CI. Ambiguous exact counts remain unknown; token completeness and human-input coverage remain separate.

An identified live conversation was observed with installed `9fa9a2a`. Its recorded metadata names `codex_vscode`, source `vscode`, CLI `0.164.0-alpha.11.1`. The existing command run on that file returned format 3 with complete `user_message_coverage`: five modern observations, no legacy or unclassified observations, and no reasons. Token completeness was also reported complete, with no missing or invalid token fields. This is one additional sample with IDE metadata; the recorded version may describe session creation rather than the current writer. The planner selected no parser change, and the result does not measure task usage.

The ignored `.awkit/handoffs/current-client-usage/classification-observation.json` retains checks of source identity, the live-file read interval and the earlier unavailable attempts. It contains permitted metadata only; the original log remains in place and private source identifiers are not published here.

Next action: Select further accounting work only with suitable client samples and a settled counting unit. Fresh live Desktop coverage, cross-file identity and task-bounded usage remain open.

## Resume inputs

ID: `usage-log-compatibility`. No new implementation is assigned. The original implementation conclusion is carried from `90e2557`; the later sample used `9fa9a2a`. Earlier owners and execution bases are retained in the history. Confirm ownership, the working revision and changed files before reopening the task.

- [Approved first implementation unit](../history/tasks/usage-log-compatibility.md#approved-first-implementation-unit): retained requirements or evidence for this task.
- [Completion and next action](../history/tasks/usage-log-compatibility.md#completion-and-next-action): retained requirements or evidence for this task.

Local evidence collections: `.awkit/handoffs/planning-implementation/`, `.awkit/handoffs/workflow-review/`, `.awkit/handoffs/current-client-usage/`. Shared collections can contain several tasks; use the cited receipt or subsection before drawing a conclusion.

## History and evidence

<a id="earlier-scope-and-evidence"></a><a id="reproduced-gap-and-limits"></a><a id="implementation-decisions-and-checks"></a><a id="approved-first-implementation-unit"></a><a id="completion-and-next-action"></a>

[Full record and verification history](../history/tasks/usage-log-compatibility.md) preserves the original scope, decisions, failures and evidence paths. The [evidence guide](../evidence.md) explains how to find retained local artifacts.
