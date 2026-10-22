# Project Profile

Copy this template into a project, fill the relevant fields and remove unused ones. Completing the profile does not establish that implementation or approval is complete.

## Start here

Fill these five fields first. They are enough for an agent to begin a task; add the later sections when a task needs delegation, delivery or deployment settings.

- Desired result:
- Source material and its version:
- Files to change and conditions to preserve:
- How completion is checked (command or inspection):
- Where results and records go:

## Purpose and evidence

- Project name:
- Problem this project solves:
- Kit components to use:
- Authoritative requirements and decisions:
- Document tracking implementation status:
- Document for reporting results to people:
- Writing guide: [Korean Writing Guide](../korean-writing.md), when writing Korean
- Document audience and what readers should understand or do:
- Established terminology and style exceptions:
- Record date:

## Working environment

- Project language and target runtime:
- Runtime used to run the kit CLI, if selected:
- Existing build tools and check configuration:
- Agent environment and how instructions are supplied:
- Selected CLI tools and versions:
- Usage collection command and result location:
- Location linking check reports and execution records:

- Project repository:
- Starting branch and base revision:
- Existing work in progress and owners:
- Build host, operating system and toolchain versions:
- Execution target and required device or service identifiers:
- Dependency installation and required generation steps:
- Focused check commands:
- Integration check commands:
- Manual inspection or device-test method, where needed:
- Resources to isolate (such as DBs, ports, sockets, devices and output directories):
- Process readiness, completion conditions and cleanup procedure:

## Commands

This table records execution settings; it is not configuration read by an automated runner. Separate executables from arguments and name the shell if one is required. Exclude secrets.

| Command name | Working directory | Executable and arguments | Prerequisites | Expected result | Side effects |
|---|---|---|---|---|---|
| | | | | | |

## Data and execution permissions

- Material to read and authorized purpose:
- Material that may be sent to AI and authorized providers:
- Scope that may be passed to subagents:
- Excluded files and data:
- Existing instructions for commits, external publication and deployment:

## Working method

- Tasks handled directly:
- Tasks to delegate and file ownership:
- Conditions requiring independent review:
- Method for freezing the review target:
- Location for results and findings:
- Authoritative location for current task state:
- Locations for review, decision and checkpoint records:
- Material and size limits for session handoffs:
- Task states: [Task Record Protocol](../protocol.md)
- Owner or procedure for execution-environment failures:

## Delegation and models

Complete this section only when delegating to subagents. Follow the [delegation guide](../delegation.md).

- Providers and role-file locations:
- Actual model for each tier (`efficient`, `standard`, `judge`, `top`):
- Project-specific examples of `high` risk:
- Premium-call cap per task (default 3):
- Concurrent independent reading limit (default 3):
- Threshold for scouting first (files outside the main agent's ownership; default 3):
- Handoff and result limits (default exploration 2KB, implementation/judgment 5KB, result 30 lines):
- Checks that must run sequentially because they share resources, such as a test DB:
- Conditions and provider combinations for a review session: [Review Session Collaboration](../review-session.md)
- Location for risk, model, call-count and token records:

## Deliverables and completion

Fill only the stages needed for this project. Use a separate row when outputs have different recipients or completion criteria, such as an application and the documents it produces. Reuse the project's existing release or submission records.

| Deliverable and format | Recipient or destination | Source revision and artifact identifier | Required stage and evidence |
|---|---|---|---|
| | | | |

- Files to include and exclude from the deliverable:
- Recipient's runtime, installation steps or device configuration:
- Commands or manual steps for producing and checking the deliverable:
- Location for retained artifacts, hashes and reports:
- Evidence connecting checked source, build settings and delivered artifact:
- Required stages (such as build, test, install, submit, accept or verify in use):
- Evidence of delivery or receipt, when required by the task:
- State and successful output to preserve on failure:
- Recovery or retry procedure and its verified scope:

For a target whose running version is replaced, also record:

- Target identity and method for reading its actual version:
- Required behavior checks after replacement:
- Data backup and compatibility checks, where applicable:
- Conditions and procedure for restoring an earlier version:

## First application results

- Scope actually applied:
- Passed checks and evidence:
- Failed checks and causes:
- Unverified scope:
- Dependencies requiring configuration or changes:
- Items to fix before the next use:
