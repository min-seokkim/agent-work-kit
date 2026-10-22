# Project Profile Examples

Use these examples when filling the `[kit]` table in `checks.toml` through [Connect the kit](../connect.md). Record what counts as done, who receives the result and where task state is kept. Keep `version` as `awkit kit init` wrote it. Use the longer [project profile](../templates/project.md) only for details the project needs, and point to existing instructions and records instead of copying them.

The examples below are illustrative settings, not completed work. Adapt their paths, recipients and completion criteria to the project. A `done` sentence records the agreed outcome; the runner executes the configured checks and does not evaluate that sentence or confirm delivery.

## Filled examples

Each TOML block supplies only the `[kit]` table. Merge its fields into the existing table in `checks.toml`, preserving the generated `version` and the project's check configuration. The named record locations are examples of places a project might already use; awkit does not create them from these values.

### Documents for internal review

```toml
[kit]
done = "The revised guide passes link checks, its facts and rendering are reviewed, and the checked files are available in the team's review folder."
recipient = "the editor reviewing the guide"
records = "docs/editorial.md"
```

Record the source revision, intended reader and facts to preserve in the editorial record. Configure the existing link checker under `checks`; keep the checked documents under `artifacts` and require the intended entry document through `required_artifacts`. Record the editor's factual review and the rendered inspection separately from the command result. Confirm which files reached the review folder before recording delivery.

The bundled `awkit kit example documents` exercise demonstrates title and local-link checks with retained Markdown files. Its passing result covers those checks; factual review, rendering and delivery need their own evidence. See the [command reference](../reference.md) for creating an exercise in a separate folder.

### CSV summary for an analyst

```toml
[kit]
done = "The summary contains one row per item, its quantities and amounts match the input orders, and the checked input and output are retained with hashes."
recipient = "the analyst using the summary"
records = "analysis/decisions.md"
```

For the bundled `awkit kit example data` exercise, the input is `input/orders.csv` and the output is `output/summary.csv`. Its configuration runs `process.py` in `setup`, then `check_output.py` in `checks` to recompute totals. It retains both CSV files through `artifacts` and requires the summary through `required_artifacts`. Copy that configuration only with the scripts and input it uses.

For a real dataset, record the input version, units, missing-value policy and permitted changes before processing. Keep assumptions and interpretation in the analysis record. Decide which inputs may be retained with the report; artifact retention copies the files that match its patterns. A successful calculation establishes agreement with the supplied data and rules, while source accuracy requires separate evidence.

### Service update

```toml
[kit]
done = "The service passes the checks in the release procedure, the target reports the intended version, and the required behavior checks pass after deployment."
recipient = "the service operator"
records = "docs/releases.md"
```

Point to the project's existing release procedure for build, deployment and recovery commands. Record the build host and target separately, along with the source revision, artifact hash and target identity. A passing worktree check covers the source and configured checks; deployment evidence must identify the artifact applied and the version observed on the target. Record recovery as verified only when it was exercised. This profile contains no tested service configuration; use the project's commands within its existing authorization.

## What to record by kind of project

Use this table to choose additional fields for the longer profile. These are preparation prompts, not claims of support or verified builds in each environment.

| Project | Read first | Record in the profile | Completion evidence |
|---|---|---|---|
| System program or CLI | Compiler settings, arguments, process and IPC layout | Build environment, start order, when a scenario is complete, how sockets and child processes are cleaned up | Binary or source bundle, scenario result, confirmed shutdown and cleanup |
| Library or SDK | Package configuration, supported runtimes, install and usage examples | Tool runtime versus target runtime, test folders, installing into a fresh environment | Package identifier, a usage example run after installing, check results |
| Firmware | Target MCU, toolchain, build, flash and debug settings | Board and equipment identifiers, how binaries are produced, device test conditions | Hashes of sources and ELF files, result on the board, observation notes |
| Browser extension | Manifest, permissions, target pages, packaging and store rules | Test browser, how the extension is loaded, settings that must survive, submission target | Package contents and version, browser check, any submission or approval record |
| Batch processing or data analysis | Input data version, parameters, runtime, output format | Input identifiers, settings needed to reproduce, output location, how to rerun after failure | Output file, references to inputs and settings, format and content checks |
| Running service | Runtime, build and deploy commands, health checks, recovery procedure | Target identity, how to read the running version, behavior checks, data compatibility | Version actually applied, behavior check results, confirmed recovery when needed |
| Documents or content | Authoritative source, audience, generator, files to publish | Fact review, writing guide, rendering checks, delivery location | Versions of source and result, content review, link and rendering checks |

A project with several deliverables gets one row each: an application release and the articles it publishes have different completion criteria. Do not add build or deployment stages a project does not have.

In the project's existing task record, name the goal, files owned and checked source identifier; keep its task ID when it has one. The review commands require a Git repository with a commit. For work checked outside those commands, a file list with hashes can identify the checked material.

## Execution conditions

Fill only the commands the project uses. The profile's command table is read by people and agents; it is not configuration for a runner. Name the shell when a command needs one.

- Separate the machine that runs the checks from the environment the result runs in: cross compilers, target interpreters, board settings. Confirm the Python running the checks is the one the project expects, and that a reused environment loads the source under review.
- For checks that start several processes, record how readiness and scenario completion are decided, give each check its own sockets, ports and output locations, and say who cleans up what. Run checks that share a single device one at a time.

## Delivery stages

Record only the stages a task needs: produced, checked, installed or applied, submitted or delivered, accepted, verified in use. For example, a source assignment is complete with the required revision or submission bundle; an SDK with an installable package and a working example; firmware is recorded separately for build, board test and field check. Follow the project's existing permissions for anything sent outside.

Decide what to keep when a stage fails and how to retry. Reapplying an earlier program, restoring data and resubmitting a corrected version are different actions; record which recovery was actually verified.

Keep the checked source identifier together with result locations, hashes and the settings that produced them, and copy binaries, bundles and reports out of temporary folders before they are cleaned. With `awkit`, list retained files under `artifacts` and files whose absence must fail the run under `required_artifacts`; keep runs with `--runs-root` ([reference](../reference.md)). A target whose running version is replaced can connect its own commands to the optional `awkit pipeline` command; restore conditions remain the project's decision.
