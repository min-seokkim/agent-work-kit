# Development

> Historical record preserved from `90e2557`. Read [the current record](../development.md) before resuming. Stage-specific statuses and assignments below describe that revision. Local `.awkit/` paths remain relative to the repository root.

Start here when developing Agent Work Kit. This file owns the current-state summary and routes readers to each topic's source. Read the linked document when its task applies. The [roadmap](../roadmap.md) lists remaining work; the owner decides what to build before implementation.

## Document map

<a id="scope"></a>
<a id="decisions"></a>
<a id="next-work"></a>
<a id="independent-session-collaboration-plan"></a>
<a id="current-local-collaboration-trial"></a>
<a id="using-awkit-in-the-coordinator-session"></a>
<a id="measurement-record"></a>
<a id="release"></a>
<a id="testing-and-building"></a>
<a id="verification-record"></a>

| Document | Owns | Read or update when |
|---|---|---|
| [Design](../design.md) | Scope and accepted decisions | Changing architecture or adding capabilities |
| [Roadmap](../roadmap.md) | Remaining work, prerequisites and completion criteria | Choosing the next task |
| [Task plans and records](roadmap.md#task-plans) | Detailed plans, owners, progress and handoffs | Starting or resuming a specific task |
| [Evidence](../evidence.md) | Completed milestones, measurements and verification limits | Assessing results or recording a check |
| [Release](../release.md) | Test, build and release procedures | Verifying or publishing a version |
| [CHANGELOG](../../CHANGELOG.md) | Changes users need when updating | Changing behavior |

Update the document that owns the information and link to it from other documents. Move completed roadmap items into a task or evidence record, keeping their identifiers and unresolved limits. Older section links to this file land at this map.

## Rules for working in this repository

The working rules (commit identity, versions, dates, documentation audience, writing style, kit length) are in [AGENTS.md](../../AGENTS.md) at the repository root, where coding agents read them automatically. `CLAUDE.md` imports it for Claude Code.

The READMEs address people. The shipped [command reference](../../kit/reference.md) defines CLI behavior, and the [failure catalogue](../../kit/failures.md) records what the kit prevents.

## Current state

The delivered product baseline is `a2a0c43`. Start with [current work](roadmap.md#current-work), or find a task under [deferred work](roadmap.md#deferred-and-blocked) and [completed units](roadmap.md#completed-units). Each task opens with its current conclusion and next action; earlier assignments and evidence follow it. The index describes recorded work, not live session activity.

| Area | Available behavior and owning reference |
|---|---|
| Kit and project setup | Baseline workflow, situation guides, generated skills, project checks and hooks. `init`, `scan`, `guide`, `skills`, `roles` and `remove` preserve the project's existing setup. See [the command reference](../../kit/reference.md) and [connection diagnostics](../tasks/connection-diagnostics.md#current-status). |
| Checks and frozen review | Commit identity, writing patterns, conservative writing comparison and completion checks; isolated snapshots, runs, retained artifacts, verification, acceptance and comparison. See [writing comparison](../tasks/writing-comparison.md#current-status), [checking](../../kit/checking.md) and [release procedures](../release.md). |
| Hooks | Shared Claude Code/Codex rule runner with block, verify and inject rules and a firing report. Delivered error-context collection does not establish the cause of the historical automatic-hook failure; see [its investigation](tasks/connection-diagnostics.md#automatic-hook-import-investigation). |
| Channels | Persisted requests, replies, rebuttals and closure between registered roles; read-only status separates protocol observations and declared obligations. See [the collaboration record](../tasks/independent-session-collaboration.md#current-status). |
| Sessions | Project-local controller, human screen and CLI for owned Codex/Claude conversations; bounded exact-ID Codex enrollment, recovery, decision input, exact-turn updates and retained current-work reading. See [session use](../../kit/sessions.md) and [delivery and limits](../tasks/session-orchestration.md#current-status). Existing IDE attachment, broad discovery and general native-platform coverage remain unfinished. |
| Usage | Format 3 separates token/log completeness from human-input coverage and preserves unknown counts. See [the compatibility record](../tasks/usage-log-compatibility.md#current-status) for tested clients and unresolved counting units. |
| Writing and examples | Source preservation, scoped revisions, correction carry-forward and purpose-dependent drafting; public review/revision and optional cross-provider continuation examples. See [delivered writing units](../tasks/writing-revision-workflow.md#current-status) and [remaining outcome evaluation](../tasks/writing-outcome-evaluation.md#current-status). |
| Extras | Configured delivery pipelines, static publishing and UI captures, with mock examples. See [the command reference](../../kit/reference.md); real-use evidence remains scoped to each task. |
| Release | Version 0.3.0 is unreleased; users install from dev. [Release prerequisites](../release.md#release) remain open. |

Keep current task state in its owning record and link evidence from there. The [earlier development overview](evidence.md#earlier-development-overview) retains the previous entry-point summary and its qualifications.
