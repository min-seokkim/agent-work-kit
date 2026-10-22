# Task Record Protocol

Use this when a task needs a record that another session or person will read: task states, review and decision records, or work resumed after an interruption. It gives people and agents a shared reading of those records. It is not an executable task queue or an approval mechanism. Existing project policy and the user's current instructions take precedence.

## A task record

Assign each task a stable ID, owner, base revision, change scope, acceptance criteria and next action. Maintain current state in one task record and link related reviews and decisions. Do not copy entire conversations into multiple documents.

That one place is where the project already keeps state: its issue tracker, Beads, a `.planning` folder, `MEMORY.md` or its own task documents (`awkit kit scan` lists what it finds). Use the kit's task, review, decision and checkpoint templates only when the project has none, or for the fields its own records lack. A second record in the kit's format splits the state in two, and the next session reads the one that went stale.

Prevents: F1, F29.

## States

| State | Meaning | Next action |
|---|---|---|
| `planned` | Goal and scope are being defined. | Confirm required inputs and acceptance criteria. |
| `ready` | Scope and verification are clear enough to start. | Confirm the owner and begin. |
| `running` | Implementation or checks are in progress. | Prepare results and evidence. |
| `review` | The result and evidence are ready for the required review. | Review the specified revision. |
| `changes-requested` | Review found changes that are needed. | Return to `running` while addressing findings. |
| `done` | Acceptance criteria and agreed checks and reviews are satisfied. | Report the outcome and remaining limitations. |
| `blocked` | An external condition must be resolved. | Record the blocker and the condition for resuming. |
| `cancelled` | The task has been cancelled. | Record the decision and changes to retain. |

A small task that does not require independent review may go directly from `running` to `done`. Label self-review accurately. Resume a `blocked` task as `ready` or `running` only after checking that its blocker is resolved. Cancellation is distinct from completion; an agent ending its session does not make a task `done`.

Prevents: F1.

## Roles and file ownership

The coordinator defines scope and acceptance criteria and assigns file ownership. The implementer makes changes and prepares check evidence. The reviewer examines the specified revision and records issues to resolve.

One session may perform multiple roles when permitted. When work spans sessions, assign ownership to avoid concurrent edits to the same file. Use delegation capabilities authorized in the current environment. This document does not authorize calls to other agents or data transfers.

Prevents: F19.

## Reviews and decisions

Each finding in the [review record](templates/review.md) includes reproduction conditions, impact, evidence location and corrective direction. The implementer accepts it or rebuts it with evidence. For unresolved decisions, record who must decide and what the decision affects.

Closing a channel is not a review pass. Resolve findings that block completion or obtain a decision from the project's authorized decision-maker, then explain remaining limitations. Design approval alone does not mean implementation or deployment is complete.

Prevents: F18.

## Resume after interruption

Leave changed files, the base revision, working directory, running processes, completed checks and the next action in the [checkpoint](templates/checkpoint.md). The receiving session verifies actual file and process state before proceeding. Do not repeat an external operation without checking whether it already ran.

Deployment, external publication and changes that are difficult to reverse follow the existing authorization scope. Task state alone is not evidence of permission.

Prevents: F29.
