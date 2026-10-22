# Work Types and Completion Evidence

Use this guide to decide what counts as done for work that is not a code change: research, writing, data preparation, environment setup, operating an application and learning. The baseline [workflow](workflow.md) still applies. Each section names the inputs to fix before starting, what to preserve, the evidence that establishes completion and the points at which to stop and ask. Record the choices for a task in the [task handoff](templates/task.md) and the project's standing choices in the [project profile](templates/project.md).

## Common rules

Fix the inputs by identifier and version before working, and confirm that everyone involved is looking at the same input: when two sessions or a person and an agent discuss a file, compare its hash or revision rather than its name.

Separate what was produced, what was checked and what a person accepted. Within a result, keep observed values, computed values, the assumptions behind the computation and the interpretation apart, so a reader can tell which part would change if an assumption changed. Mark unverified values as `unverified`.

Keep the result the user accepted. When revising a document, a design or a configuration that the user has approved, identify that version, list what it did well, and change only what the task names. Compare the revision with the accepted version before delivering it; a regression against an accepted version is a defect even when the new version passes its checks. With `awkit review`, keep the accepted run with `accept` and check later runs with `compare`.

Three kinds of record have different jobs and are not merged into one document: the current task record (what is being made and how far it has got), reusable knowledge (writing methods, design principles, lessons from failures that apply across tasks) and the sources and evidence those rest on. Each points to the others. After consolidating or summarising any of them, check that no important decision was dropped and no discarded rule came back.

When the result will be sent outside the project, follow the project's existing authorization rules.

Prevents: F16, F22.

## Research

**Inputs:** the question, the kind of source it needs, the sources allowed, the date range and the form of the answer. Official requirements come from official sources; what people experience comes from first-hand accounts, across different experiences rather than only the ones that support the user's view. Record each source with its location and the date it was read.

**Preserve:** the user's question as asked, direct quotations with their source, and the distinction between a source's claim and your own inference.

**Completion evidence:** every claim in the result cites a source that was actually read, contradictions between sources are shown rather than averaged, and the gaps are listed. The result says what recurs across accounts and what is a single case, and keeps the parent organization, the local office and the specific role apart. A summary of a document carries that document's version or date.

**Stop and ask** when the sources disagree on a fact the answer depends on, when the allowed sources cannot answer the question, or when a source would have to be obtained from outside the authorized scope.

Prevents: F23, F37.

## Writing

**Inputs:** audience, purpose, the facts and decisions that must appear, the authoritative sources and the established terminology. Follow the [Writing Guide](writing.md), and for Korean text the [Korean Writing Guide](korean-writing.md).

**Preserve:** the Writing Guide's preservation list, and accepted wording in a revision unless the task changes it.

**Completion evidence:** the preservation list is checked against the text, the fact review names the source for each claim, and the rendered form (links, headings, tables) was inspected. For a revision, the diff against the accepted version shows only intended changes.

For designed output such as slides or a formatted report, review four things separately: the content, the design, whether the file stays editable in the user's tool, and the final rendered output (line breaks, fonts, export properties). A draft that is good in three of them is not finished.

**Stop and ask** when a fact in the source is missing or contradicted, when a style choice changes meaning, or when the text must state a decision nobody has recorded.

Prevents: F16, F30.

## Data preparation and analysis

**Inputs:** the input files or queries with their identifiers and hashes, the required columns and types, the transformation rules and the expected shape of the output. For an analysis, also the assumptions used to turn raw values into meaningful ones (scales, units, rates, thresholds), each with its source, kept in a file next to the data.

**Preserve:** the original input unchanged, every row that the rules do not explicitly drop, and the rule that produced each change. Record dropped or altered rows with their reason and count.

**Completion evidence:** the output has the expected columns and row count, totals or counts recomputed from the input match the output, and the input, output and the command that produced it are retained together with hashes. With `awkit review check`, list them under `artifacts` and name the output under `required_artifacts`. An analysis report shows observed values, assumptions, computed values and interpretation in separate sections, checks each assumption against the data where it can (a stated sample rate against the observed interval, a stated range against the observed extremes), and leaves the interpretation to a person, marked as such.

**Stop and ask** when input values fall outside the stated types or ranges, when a rule is ambiguous for real rows, when an assumption disagrees with the data, or when a transformation would discard data the task did not mention.

Prevents: F22.

## Environment setup

**Inputs:** the target machine or container, the required tool versions, the configuration files to change, the state that must survive the change, and the conditions the user wants kept (such as a visual quality setting or a startup time they are happy with).

**Preserve:** existing configuration (copy it before editing), credentials outside the record, the order of steps actually performed, and the settings the user has said they like.

Before repeating a procedure from documentation or a forum, confirm that it applies to this program version, this account type and this operating system. Many setup failures come from applying instructions written for a different edition.

When something that worked before a change is to be restored, the wanted end state stays fixed: a solution that needs extra steps each time is reported as an alternative, not as the fix. Use when it last worked, what changed and what did not, and the result under each condition the user tested; after a failed attempt, change the hypothesis rather than repeat the proposal.

**Completion evidence:** each required tool reports the expected version from the shell the user will use, the project's own check command runs there, and the record lists every file changed and every package installed. Restored or copied data counts as usable only when the path the user needs works: the mount is present, the permissions allow access and the program that reads it connects. Separate the setting being applied, the measurement showing its effect and the user saying they are satisfied. A step that was skipped or failed is recorded as such.

**Stop and ask** before changing system-wide settings, before installing software from an unlisted source, and when a step needs credentials or permissions the task did not grant.

Prevents: F24, F25, F39.

## Operating an application

**Inputs:** the application and account, the actions to perform, the expected end state and the actions that must not be taken. Distinguish reading from changing.

**Preserve:** the state before each change, the user's existing data and settings, and a record of each action with its observed result.

**Completion evidence:** the expected end state was observed after the last action, in the application itself rather than inferred from a success message. For a change that sends something or spends money, the confirmation the application shows is recorded.

**Stop and ask** before any action that sends a message, publishes, pays, deletes or changes permissions, and whenever the application shows a state the task did not anticipate.

Prevents: F24.

## Learning

**Inputs:** the goal, what the user already knows, the material to use and which parts the user will do themselves.

**Preserve:** the user's own attempts and wording; do not replace them with a finished answer unless asked. Keep the division between what the user did and what the agent supplied.

Answer a question about what something is or does with the problem it solves, what changes inside, what the user can observe and when to use it. Address a misunderstanding only when the user holds it; a list of caveats is not an explanation.

**Completion evidence:** the user has performed the agreed steps and the result of each is recorded, including mistakes and how they were resolved. A plan or explanation alone does not complete a learning task.

**Stop and ask** when the user is about to skip a step they chose to do themselves, when the material does not cover the goal, or when a check requires knowledge the user has not yet reached.

Prevents: F28, F38.

## Automation

A task that sets up something to run repeatedly also records the trigger, the inputs it reads, the actions it may take, its expiry or stop condition and who is notified when it fails. Confirm whether the user wants it once or every time; "just this once" means a one-shot run and no registered schedule. Record the first real run's result separately from the test run, and record the removal of a schedule as its own step.

Prevents: F27.
