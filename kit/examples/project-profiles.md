# Project Profile Examples

Use this when filling the [project profile](../templates/project.md) for a kind of project you have not set up before. The rows say what to look at; they are not results of building or deploying in those environments. Take the actual commands and completion criteria from the project's configuration, requirements and records.

## What to record by kind of project

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

Every record names the task ID, goal, files owned and the source identifier that was checked: a commit or review snapshot with Git, otherwise a file list with hashes.

## Execution conditions

Fill only the commands the project uses. The profile's command table is read by people and agents; it is not configuration for a runner. Name the shell when a command needs one.

- Separate the machine that runs the checks from the environment the result runs in: cross compilers, target interpreters, board settings. Confirm the Python running the checks is the one the project expects, and that a reused environment loads the source under review.
- For checks that start several processes, record how readiness and scenario completion are decided, give each check its own sockets, ports and output locations, and say who cleans up what. Run checks that share a single device one at a time.

## Delivery stages

Record only the stages a task needs: produced, checked, installed or applied, submitted or delivered, accepted, verified in use. For example, a source assignment is complete with the required revision or submission bundle; an SDK with an installable package and a working example; firmware is recorded separately for build, board test and field check. Follow the project's existing permissions for anything sent outside.

Decide what to keep when a stage fails and how to retry. Reapplying an earlier program, restoring data and resubmitting a corrected version are different actions; record which recovery was actually verified.

Keep the checked source identifier together with result locations, hashes and the settings that produced them, and copy binaries, bundles and reports out of temporary folders before they are cleaned. With `awkit`, list them under `artifacts` in the check configuration and keep runs with `--runs-root` ([reference](../reference.md)). A target whose running version is replaced can connect its own commands to `awkit pipeline`; restore conditions remain the project's decision.
