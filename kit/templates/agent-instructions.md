# Agent Instructions

Follow existing project instructions and the user's current request first. Before working, read the completed [project profile](project.md) and only the authoritative documents needed for the task. Fill missing profile values from verifiable configuration or mark them unresolved. Do not interpret blank template fields as executable commands. For work other than code changes, such as research, writing, data preparation or environment setup, use the completion evidence in [Work Types](../work-types.md). When running `awkit`, look up formats, rules and exit codes in the [command reference](../reference.md).

## Connect the kit to a project

When the kit has just been added to a project and the [project profile](project.md) is still empty, connect it before the first task. Run `awkit kit scan` in the project folder: it reports the manifests, the commands the project already defines (package scripts, test and lint configuration, Makefile targets, CI run lines), the documentation folders and the Git state, and prints a suggested `checks.toml`. Treat every suggestion as unverified.

Then do the following, and record each result rather than assuming it:

1. Fill the five "Start here" fields of the profile from the scan and from one question to the user: what counts as done for this project, and who or what receives the result. Do not invent a build or deployment step the project does not have.
2. Write `checks.toml` from the commands the scan found, run `awkit review check HEAD --config checks.toml` once, and keep only the commands that actually run here. List the files a passing run must produce under `artifacts` and `required_artifacts`.
3. Record the delivery stages the project really uses (build, test, install, submit, accept, verify in use) in the profile's "Deliverables and completion" section. Where a running target is replaced or a result is transferred, connect the project's own commands to `awkit pipeline`; leave out `backup` and `rollback` when the target cannot be restored.
4. Offer the user the hooks from `awkit kit hooks`: `--git` stops commits whose author or trailers differ from the repository's history, and `--claude` stops Claude Code from finishing with changed files that have no passing check.
5. Commit the profile and the check configuration. `awkit kit init` has already committed the kit folder, creating the repository if the project had none; say so to the user. The review commands do not create repositories or commits: if `awkit review` reports that the folder is not a Git repository or has no commit, commit the files first.

Ask before touching credentials, remote targets or settings outside the project folder.

## Start work

Check the base revision and existing changes. Define the goal, acceptance criteria and files to edit. Preserve work already in progress. Access only the material needed for the task within the authorized scope. Assign file ownership when working alongside other contributors.

## Implement and verify

Use the working directories, preparation steps and commands in the profile. Record actual results and evidence in the [task record](task.md). If the environment prevents a check, report that limitation rather than a pass. Avoid unnecessary full-suite runs for small changes.

Request independent review when the project requires it and it is authorized. Label your own review as self-review. Manage state with the [task protocol](../protocol.md), and record choices in the [decision record](decision.md).

## Report and resume

For text intended for people, follow the [Writing Guide](../writing.md), and for Korean text the [Korean Writing Guide](../korean-writing.md). Before reporting work as done, run `awkit check done`: changed files need a passing check of their current state, or the report says they are unchecked and why. Run `awkit check writing` on changed Markdown. Report changed behavior, verified results and remaining limitations at completion. Leave a [checkpoint](checkpoint.md) when another session needs to continue.

These instructions do not automatically authorize data access, agent invocation, message transmission or deployment. Make routine decisions within the already authorized scope.
