# Task Record Protocol

This protocol gives people and agents a shared interpretation of task records. It is not an executable task queue or an automatic approval mechanism. Existing project policy and the user's current instructions take precedence.

## A task record

Assign each task a stable ID, owner, base revision, change scope, acceptance criteria and next action. Maintain current state in one task record and link related reviews and decisions. Do not copy entire conversations into multiple documents.

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

## Roles and file ownership

The coordinator defines scope and acceptance criteria and assigns file ownership. The implementer makes changes and prepares check evidence. The reviewer examines the specified revision and records issues to resolve.

One session may perform multiple roles when permitted. When work spans sessions, assign ownership to avoid concurrent edits to the same file. Use delegation capabilities authorized in the current environment. This document does not authorize calls to other agents or data transfers.

## Check evidence

Use the commands recorded in the [project profile](templates/project.md). Do not assume a particular test tool exists based on the programming language. Use argument arrays, or specify the shell and command when shell interpretation is required.

Record the working directory, actual command, base revision, exit code, output location and scope of each check. Identify the environment without including secrets. For human checks, state the method and limitations and distinguish them from automated checks.

Reuse existing check evidence when the relevant inputs are unchanged. Record changes made after a review request separately and recheck only the affected scope.

## Reviews and decisions

Each finding in the [review record](templates/review.md) includes reproduction conditions, impact, evidence location and corrective direction. The implementer accepts it or rebuts it with evidence. For unresolved decisions, record who must decide and what the decision affects.

Closing a channel is not a review pass. Resolve findings that block completion or obtain a decision from the project's authorized decision-maker, then explain remaining limitations. Design approval alone does not mean implementation or deployment is complete.

## Resume after interruption

Leave changed files, the base revision, working directory, running processes, completed checks and the next action in the [checkpoint](templates/checkpoint.md). The receiving session verifies actual file and process state before proceeding. Do not repeat an external operation without checking whether it already ran.

Deployment, external publication and changes that are difficult to reverse follow the existing authorization scope. Task state alone is not evidence of permission.

## Connect optional tools

The current `awkit channel` roles are `main` and `reviewer`. A coordinating or implementing session can act as `main` for a review. Use separate channels per review or another delivery mechanism for multiple reviewers. The channel does not automatically manage arbitrary roles and owners.

Values such as `passed` and `failed-restored` from `awkit pipeline` describe one execution. They do not replace task states; a successful deployment alone does not complete the whole task.

Keep task records separate from execution results when connecting automated assignment or check runners. Explicitly configure project-command execution and agent invocation as separate integrations.
