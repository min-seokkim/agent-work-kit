# Project Profile

Copy this template into a project, fill the relevant fields and remove unused ones. Completing the profile does not establish that implementation or approval is complete.

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

- Project language and runtime:
- Existing build tools and check configuration:
- Agent environment and how instructions are supplied:
- Selected CLI tools and versions:
- Usage collection command and result location:
- Location linking check reports and execution records:

- Project repository:
- Starting branch and base revision:
- Existing work in progress and owners:
- Operating system and execution environment:
- Dependency installation and required generation steps:
- Focused check commands:
- Integration check commands:
- UI inspection method:
- DBs, ports and output directories to isolate:

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

## Publication or deployment

- Publication target and allowed files:
- Reference revision displayed for documents and summaries:
- Successful output to retain on failure:
- Data backup before deployment:
- Deployment-result verification:
- Conditions for restoring an earlier revision:
- Method for checking DB restoration and compatibility:

## First application results

- Scope actually applied:
- Passed checks and evidence:
- Failed checks and causes:
- Unverified scope:
- Dependencies requiring configuration or changes:
- Items to fix before the next use:
