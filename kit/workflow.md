# Workflow

Read this every session. It is the default way of working for any task in this project: define it, do it, check a frozen version, report with evidence. The project's own instructions and the user's current request come first. [README.md](README.md) lists the situation guides and the [command reference](reference.md); while the [project profile](templates/project.md) is empty, [connect the kit](connect.md) first.

## Define the task

Write one sentence for the intended outcome and one for how it will be checked. Check the base revision and the changes already in progress, then name the files to change and the material to read. Settle ownership before editing a file someone else is working on. Judge risk by what a failure would affect, not by the number of files: permissions, data changes, deployment and publication need an impact assessment.

Settle the form of help: the agent does the work, the user does it with hints, or the agent prepares a briefing the user acts on. Project instructions that assign work, such as a list of ready items, settle it: start and say which item. A user saying what they plan to do themselves, or asking whether something is acceptable, is not delegating it or confirming it.

Read each statement from the user as a hypothesis, a constraint or a decision. A user new to a field often proposes an approach to have it evaluated: give the standard approach, the strengths and weaknesses of theirs and the alternatives, and name the premise or step you disagree with. Building on every idea as a requirement produces a design that follows the conversation instead of the problem.

Prevents: F8, F19, F28, F35.

## Do the work

Use the working directories, preparation steps and commands in the profile. Check the current state before installing, moving or reviewing anything, and open files rather than judging them by name. Mark inferences as inferences, and run a suggested command once before relying on it. Access only the material the task needs within the authorized scope.

Prevents: F11.

## Check a frozen version

Check the version that will be delivered, not the working files while they change. Name the changed files to `awkit review snapshot`, run `awkit review check` on the snapshot, and keep its run folder: the folder ties the result to the exact files and command. Later edits need a later check. Reuse a passing run only when its inputs are unchanged.

Keep every run. When a check fails and a rerun passes, explain the first failure or report it as unresolved. Separate environment problems, product defects and unknown causes, and separate focused checks, full runs and a person's acceptance. Name the environments a claim covers and run all of them before claiming support. [Checking](checking.md) covers check configuration, shared resources and multiprocess programs.

A tool's success is not the result. A message counts as delivered when the recipient can see it, a setting as applied when the program reports it, a release as live when its running version answers. Record which was observed and which inferred.

Prevents: F1, F2, F3, F17, F24.

## Report

Before reporting work as done, run `awkit check done`: session changes need a passing check of their current state; otherwise report them as unchecked and explain why. Distinguish the checked task snapshot from the repository state. Lead with what changed and what comes next, then the checks with run folders and scope and the review method. Name a required check that was not run and why. Mention what a result does not show only where the reader would otherwise assume it, or the report buries what was done. State what each number covers. When facts do not settle a question, give candidate explanations, their assumptions and a provisional judgment, with the observation that would change it.

Text people read follows the [Writing Guide](writing.md); run `awkit check writing` on changed Markdown.

Prevents: F1, F6, F13, F36.

## Continue across sessions

Keep the current state of the work in one place, where the project already keeps state, and link reviews and decisions from it ([task records](protocol.md)). On interruption or a change of session, put the changed files, completed checks, running work and the next action in that place ([checkpoint fields](templates/checkpoint.md)); a new file per task or per session splits the state and the next session reads a stale copy. The session that continues verifies the actual files and processes first and does not repeat an external operation without checking whether it already ran.

This kit authorizes nothing by itself; the project's instructions say what is authorized, including standing permissions such as pushing to a working branch. Ask before touching credentials, remote targets or settings outside the project folder that those instructions do not cover, and decide routine matters inside them without asking. Waiting for an answer the instructions already give costs the user as much as acting without one.

Prevents: F28, F29.
