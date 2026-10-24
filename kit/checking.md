# Checking

Use this when setting up checks for a project, when a check needs a database, port, device or long-running process, or when a result is hard to interpret. The baseline in [workflow.md](workflow.md) already says to check a frozen version and keep every run; this guide covers what makes a check trustworthy.

## The checked version

Run checks on a snapshot in a separate worktree (`awkit review check`), so the result belongs to known files and not to whatever the working folder held at the time. For source that is not in Git, record a stable identifier and the location of the checked files. Identify the build host, the target runtime and the toolchain separately from the runtime that runs the kit. Check dependencies, generated inputs and each command's working directory before running; an installed package or editable environment must load the code under review, not an older copy.

Use the project's `[[setup]]` steps for [dependency preparation](reference.md#check); they run for each fresh worktree and expand per-run paths. Keep install or link commands in `checks.toml`. Reused dependencies must match the snapshot's declared inputs and must not load project code or generated outputs from an unreviewed working tree; the configuration hash does not certify dependency contents.

Use the commands recorded in the [project profile](templates/project.md). Do not assume a test tool exists because of the programming language. Use argument arrays, or name the shell when shell syntax is required. Record the working directory, the command, the revision, the exit code, the output location and the scope of each check, without secrets. For checks a person does, state the method and its limits and keep them apart from automated results.

Prevents: F3, F11, F17.

## Shared resources and processes

Isolate what checks share: databases, ports, sockets, devices and output directories. Allocate them per run with the `{run_id}` placeholder, and run checks that need one physical device one at a time; parallel or repeated checks that share a resource fail or pass for the wrong reason. For programs with several processes, define readiness, the end of the scenario and cleanup, and record which processes the check owns before stopping anything. Keep artifacts and reports outside disposable worktrees, connected to the checked source and build settings.

A new or changed lock needs a test with two concurrent executions against a real database, covering the changed operations against each other and against existing operations that lock the same rows. Without it, list the concurrency risk as unverified.

Prevents: F26.

## Interpreting results

Interpret an exit status against the task's expected result; a long-running process may need a scenario runner to decide when it is done and to stop it. Inspect the actual rendering after interface changes. For firmware, report host checks, target builds and device observations separately.

A failure seen once stays unresolved until its cause is explained, even if a rerun passes. Run the rerun in a fresh worktree so the first failure is not hidden by state the first run left behind.

Prevents: F2.
