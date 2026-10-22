# Work Types and Completion Evidence

Use this guide to decide what counts as done for work that is not a code change: research, writing, data preparation, environment setup, operating an application and learning. Development keeps the [workflow](workflow.md). Each section names the inputs to fix before starting, what to preserve, the evidence that establishes completion and the points at which to stop and ask. Record the choices for a task in the [task handoff](templates/task.md) and the project's standing choices in the [project profile](templates/project.md).

Common rules apply to every type. Fix the inputs by identifier and version before working. Keep the user's accepted wording, structure and decisions unless the task changes them. Separate what was produced, what was checked and what a person accepted. Mark unverified values as `unverified`. When the result will be sent outside the project, follow the project's existing authorization rules.

## Research

**Inputs:** the question, the sources allowed, the date range and the form of the answer. Record each source with its location and the date it was read.

**Preserve:** the user's question as asked, direct quotations with their source, and the distinction between a source's claim and your own inference.

**Completion evidence:** every claim in the result cites a source that was actually read, contradictions between sources are shown rather than averaged, and the gaps are listed. A summary of a document carries that document's version or date.

**Stop and ask** when the sources disagree on a fact the answer depends on, when the allowed sources cannot answer the question, or when a source would have to be obtained from outside the authorized scope.

## Writing

**Inputs:** audience, purpose, the facts and decisions that must appear, the authoritative sources and the established terminology. For Korean text follow the [Korean Writing Guide](korean-writing.md), including its English draft and three reviews.

**Preserve:** numbers, dates, identifiers, commands, quotations and the degree of certainty in the source. Keep accepted wording in a revision unless the task changes it.

**Completion evidence:** the preservation list is checked against the text, the fact review names the source for each claim, and the rendered form (links, headings, tables) was inspected. For a revision, the diff against the accepted version shows only intended changes.

**Stop and ask** when a fact in the source is missing or contradicted, when a style choice changes meaning, or when the text must state a decision nobody has recorded.

## Data preparation

**Inputs:** the input files or queries with their identifiers and hashes, the required columns and types, the transformation rules and the expected shape of the output.

**Preserve:** the original input unchanged, every row that the rules do not explicitly drop, and the rule that produced each change. Record dropped or altered rows with their reason and count.

**Completion evidence:** the output has the expected columns and row count, totals or counts recomputed from the input match the output, and the input, output and the command that produced it are retained together with hashes. With `awkit review check`, list them under `artifacts` and name the output under `required_artifacts`.

**Stop and ask** when input values fall outside the stated types or ranges, when a rule is ambiguous for real rows, or when a transformation would discard data the task did not mention.

## Environment setup

**Inputs:** the target machine or container, the required tool versions, the configuration files to change and the state that must survive the change.

**Preserve:** existing configuration (copy it before editing), credentials outside the record, and the order of steps actually performed.

**Completion evidence:** each required tool reports the expected version from the shell the user will use, the project's own check command runs there, and the record lists every file changed and every package installed. A step that was skipped or failed is recorded as such.

**Stop and ask** before changing system-wide settings, before installing software from an unlisted source, and when a step needs credentials or permissions the task did not grant.

## Operating an application

**Inputs:** the application and account, the actions to perform, the expected end state and the actions that must not be taken. Distinguish reading from changing.

**Preserve:** the state before each change, the user's existing data and settings, and a record of each action with its observed result.

**Completion evidence:** the expected end state was observed after the last action, in the application itself rather than inferred from a success message. For a change that sends something or spends money, the confirmation the application shows is recorded.

**Stop and ask** before any action that sends a message, publishes, pays, deletes or changes permissions, and whenever the application shows a state the task did not anticipate.

## Learning

**Inputs:** the goal, what the user already knows, the material to use and which parts the user will do themselves.

**Preserve:** the user's own attempts and wording; do not replace them with a finished answer unless asked. Keep the division between what the user did and what the agent supplied.

**Completion evidence:** the user has performed the agreed steps and the result of each is recorded, including mistakes and how they were resolved. A plan or explanation alone does not complete a learning task.

**Stop and ask** when the user is about to skip a step they chose to do themselves, when the material does not cover the goal, or when a check requires knowledge the user has not yet reached.

## Automation

A task that sets up something to run repeatedly also records the trigger, the inputs it reads, the actions it may take, its expiry or stop condition and who is notified when it fails. Record the first real run's result separately from the test run.
