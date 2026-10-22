# Delivery

Use this when a result leaves the project: a build is handed over, a package installed, an artifact submitted, documents published or a running version replaced. The baseline in [workflow.md](workflow.md) ends at a checked version; this guide covers getting that version to its recipient and confirming it arrived.

## Identify what is delivered

Use the project profile to name each deliverable, its recipient and the stage at which it counts as complete. Record its source revision, the artifact identifier or hash, the production settings and the check evidence, and keep the files and instructions the recipient needs to reproduce it. A task may finish at build, test, install, submit, accept or verify in use; record only the stages actually completed, under the task's existing authorization.

Prevents: F24.

## Confirm it in its intended context

For a source submission, confirm the required files and the submitted revision. For a package, install and use it in the recipient's environment. For firmware, connect the tested binary to the device and its test conditions. For published documents, check the content and the entry point. For a replaced running version, read the version that actually runs and run behavior checks after the switch.

Publish only the files on an allowlist; being present in a working directory is not permission to publish. Keep previews apart from official publications, and confirm the project and revision when restoring an earlier publication.

Prevents: F7, F24.

## Failure and recovery

Record what remains available after a failure and how to retry or recover. Restoring an earlier executable, restoring data and resubmitting an artifact are separate operations. Reuse the project's existing procedures and state which recovery steps have been verified. A successful deployment is one stage; it does not complete the task by itself.

For web projects, `awkit pipeline` runs the project's own delivery commands, verifies the running release and keeps the history for rollback, and `awkit publish` switches a static site to a checked build atomically. Leave out `backup` and `rollback` when the target cannot be restored. Both are extras described in the [command reference](reference.md).

Prevents: F24.
