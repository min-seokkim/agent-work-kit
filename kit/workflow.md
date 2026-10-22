# Development Workflow

Follow the project's existing requirements and permissions first. Scale this workflow to the task; it does not add approval steps automatically. On first adoption, follow the kit's getting-started guide. Record state and evidence using the [task protocol](protocol.md). The workflow is independent of programming language and agent product.

## Define the task

Write one sentence for the intended outcome and one for how to verify it. Check the base revision and existing changes, then identify the evidence to use and files to edit. Settle ownership before editing a file another contributor is working on.

Judge risk by the impact of failure rather than file count. Wording changes are often straightforward; permissions, data changes, deployment and publication require an impact assessment. For high-risk work, choose design judgment before implementation or independent review afterward. Do not repeat both by default. Reuse an independent review that covers the same revision, scope and acceptance criteria. Another equivalent review needs a new reason.

## Delegate work

The main agent handles work directly when it has already read the evidence and can readily verify the result. Delegate independent investigation or implementation with non-overlapping file ownership. Fill in the goal, output, evidence and scope in the [task handoff](templates/task.md).

Include only the necessary document locations and decisions. Do not repeatedly pass the full conversation or repository. Separately confirm authorization to send material to another provider or subagent.

Follow the [delegation guide](delegation.md) for when to delegate, role and model selection, premium-call budgets and retries.

## Review independently

Use [Review Session Collaboration](review-session.md) when a separate session acts as reviewer. Include a code revision or immutable snapshot ID in each request. Review that target; changes made after the request belong to a later review. While review is running, the implementer may continue with work whose file ownership does not overlap.

When using Git snapshots, run checks in a separate worktree. For other source layouts, record a stable source identifier and the location of the checked files. Identify the build host, target runtime and toolchain separately from the runtime running the kit. Check dependencies, generated inputs and command working directories before execution. Installed packages or editable environments must load the code under review.

Isolate shared resources used by the checks, such as DBs, ports, Unix sockets, devices and output directories. For multiprocess programs, define readiness, scenario completion and cleanup. Record ownership before stopping processes or removing resources. Keep artifacts and reports needed for review outside disposable worktrees, and connect them to the checked source and build settings.

Each finding states its failure condition, impact, evidence location and corrective direction. The main agent accepts it or rebuts it with evidence, then records any remaining decision. Do not repeat a full review for stylistic preferences or an already verified fix. Recheck the affected scope when behavior or scope changes, important findings remain, evidence conflicts or relevant tests fail. Each side may rebut a disputed issue once; the main agent then records a judgment. If it cannot decide, record the decision needed. This limit does not excuse an unresolved defect or unmet acceptance criterion.

Channel closure and review completion are separate. Apply the final result and explain remaining findings before finishing the task.

## Interpret check results

Distinguish execution-environment problems, product defects and unknown causes. Preserve the initial failure even when a rerun passes. Explain its cause or leave it unresolved.

Distinguish focused checks, full-suite results and human acceptance. Inspect actual rendering after UI changes. For firmware, report host checks, target builds and device observations separately. A command's exit status must be interpreted against the task's expected result; a long-running process may need a scenario runner to determine completion and shut it down.

## Deliver results

Use the project profile to identify each deliverable, recipient and required completion stage. Record its source revision, artifact identifier or hash, production settings and verification evidence. Preserve the files and instructions the recipient needs to reproduce the result. A task may finish at build, test, install, submit, accept or verify-in-use; record only stages actually completed and apply the task's existing authorization rules.

Check the delivered result in its intended context. For a source submission, verify the required files and submitted revision. For a package, check installation and use in the recipient's environment. For firmware, connect the tested binary to the device and test conditions. For published documents, check the content and entry point. For a running-version replacement, read the actual version and run behavior checks after applying it.

Record what remains available after failure and how to retry or recover. Restoring a previous executable, restoring data and resubmitting an artifact are separate operations. Reuse existing project procedures and state which recovery steps have been verified.

## Publish documents and AI summaries

For Korean documents, UI text and handoffs, follow the [Korean Writing Guide](korean-writing.md). Identify the audience and facts to preserve, write an actual English draft, then rewrite it naturally in Korean. Review facts, sentences and overall flow separately. Keep project-specific terminology in the project profile.

Attach a reference revision to both the source and its summary. Restrict AI summaries to the designated inputs and check the response format, evidence references and excluded data. A valid evidence ID does not prove the explanation is true; a person checks important judgments against the source.

Decide whether document rendering must wait for the AI summary. If they run separately, show when the summary is missing or stale. Check revisions and execution order so an older job cannot replace a newer result. Validate the new output before switching the entry point; retain the last successful output on failure.

Publish only allowlisted files. Presence in a working directory is not permission to publish. Distinguish uncommitted previews from official publications, and verify the project and revision when restoring. Apply the project's authorization rules to external transfer and publication.

## Continue across sessions

Link [review results](templates/review.md) and [important decisions](templates/decision.md) from the current task record. On interruption or a change of session, leave changed files, completed checks, running work and the next action in a [checkpoint](templates/checkpoint.md). The receiving session verifies the actual state before continuing.
