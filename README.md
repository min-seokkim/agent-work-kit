# Agent Work Kit

English | [한국어](README.ko.md)

Agent Work Kit provides working instructions, a Korean writing guide, and verification tools for development with coding agents.

Start with the Markdown kit for task instructions, handoffs and document writing. Add the `awkit` CLI to create review snapshots, run project checks, exchange review messages, and record release results.

Agent instructions and templates are in English. The kit setup guide and the guides under `docs/` are in Korean.

## Korean document writing

The [Korean Writing Guide](kit/korean-writing.md) gives agents a process for writing readable Korean development documents. It covers preserving facts and conditions, drafting in English before writing natural Korean, and reviewing facts, sentences and overall flow. It addresses translation artifacts, abstract wording and strings of nouns, with rules for technical terminology and document structure.

## Development and review

You copy the kit into your project and fill in one page: how to build it, which checks prove a change works, and where task records go. The agent reads that page before it starts. Every task gets a short record of its goal, the files it may touch and the checks that will decide whether it is done.

When a change is ready, `awkit review snapshot` writes exactly the files you name into a Git commit object. Your branch, index and working tree stay as they were. `awkit review check` checks out that commit in a separate worktree, runs your project's own test commands there and keeps the logs. A second agent session reviews the same commit. Requests, replies and rebuttals go through `awkit channel`, and a reply can only answer a message the other side actually sent.

For deployment verification, `awkit pipeline` calls five commands your project supplies (read the current version, back up, deploy, verify, roll back) and checks what is really running. A deploy command that exits 0 while the old version is still live counts as a failure. If a step times out and the target's state is uncertain, `reconcile` checks it before the next deploy.

For delegated work, the kit defines five roles: scout, analyst, builder, verifier and writer. Its guide covers task risk, handoffs and review budgets. `awkit kit roles` generates role files for your agent environment, and `awkit usage` reports models and tokens from session logs.

Each project defines its completion criteria and connects its build, test and deployment commands. See [Role and scope](docs/scope.md) for the product's responsibilities and [Development plan](docs/roadmap.md) for upcoming work.

## Install

The `awkit` CLI needs Python 3.11 or later on Windows or Linux. The project you build with it can be in any language.

Download the wheel from [Releases](../../releases) and install it into a virtual environment:

```sh
python -m venv .venv
.venv/bin/pip install agent_work_kit-0.2.0-py3-none-any.whl
.venv/bin/awkit --version
```

On Windows the scripts are under `.venv\Scripts\`. Screen capture needs Playwright: install the wheel with the `[ui]` extra and run `python -m playwright install chromium`. If you only want the Markdown kit, unzip `agent-work-kit-0.2.0.zip` from the same release into your project; no Python is needed.

## Quick start

Add the kit to a project:

```sh
awkit kit init path/to/project
```

This creates `agent-work-kit/` and stops without touching anything if that folder already exists. Fill in `agent-work-kit/templates/project.md`, then start your agent with something like:

> Before you start, read `agent-work-kit/templates/agent-instructions.md` and the filled-in `agent-work-kit/templates/project.md`. The project's existing rules take precedence.

Freeze a change and check it in isolation:

```sh
snap=$(awkit review snapshot src/auth.js tests/auth.test.js)
awkit review check "$snap" --config review-checks.toml
```

Ask another session to review that exact commit:

```sh
awkit channel post main reviewer review --snap "$snap" --body "Please review the permission check."
awkit channel wait reviewer request                 # reviewer: wait for open requests
awkit channel post reviewer main re --reply-to M-001 --body-file review.md
awkit channel wait main reply M-001                 # author: wait for the answer
```

Both sessions read the same `.awkit/channel.sqlite3` in the current folder, or the file you pass with `--db`.

Try the release runner on the bundled mock target, which only rewrites a JSON file:

```sh
awkit pipeline --config examples/local-release/pipeline.toml deploy aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
awkit pipeline --config examples/local-release/pipeline.toml deploy ffffffffffffffffffffffffffffffffffffffff
```

The second release is built to fail its health check. The runner rolls back to the first one, records the run as `failed-restored` and exits with 1.

## Commands

| Command | What it does | Extra requirement |
|---|---|---|
| `awkit kit init` | Copies the Markdown kit into a new project folder. | |
| `awkit kit roles` | Writes five subagent role files with a model per tier, preserving existing files. | |
| `awkit usage` | Reads Claude Code and Codex session logs and totals the real model, calls and tokens per thread. | |
| `awkit review` | Freezes selected changes as a Git commit and runs the project's checks against it in a separate worktree. | Git |
| `awkit channel` | Passes review requests, replies and rebuttals between two local sessions through a SQLite file. | |
| `awkit publish` | Checks the links in a static site build, switches the entry page atomically and can restore an earlier version. | |
| `awkit ui` | Captures chosen pages at several widths and collects them on one review sheet. | Playwright and a browser |
| `awkit pipeline` | Runs your deploy commands in a fixed order and verifies the release that is actually live. | Your deploy commands |

## How the release runner handles failure

| Situation | What `awkit pipeline` does |
|---|---|
| The deploy command exits 0 but the old version is still running | Records a failure. A run passes only when the verifier reports the requested release and every check it returns is passing. |
| The deploy fails and automatic rollback succeeds | Records `failed-restored` and exits 1, so the failed request is not lost. |
| A step times out | Stops the step and every local process it started, records `uncertain`, and blocks further deploys until `reconcile` has checked the target. |
| The current release is already failing its checks | Stops before changing anything. To ship a fix anyway, pass `--allow-unhealthy-current`. It never rolls back to a release that was already broken. |
| You run `rollback` more than once | Walks back through releases that passed verification, one step at a time, instead of flipping between the last two. |
| A second run starts on the same state folder | Refuses to start. |

Every run keeps each step's exit code, duration, stdout and stderr under its own folder.

## Validation

The release, review and publishing commands have been checked against mock projects. Usage reporting has also been checked against real Claude Code logs. [Validation coverage](docs/validation.md) records the tested environments, failure cases and remaining checks for real-world use.

## Documentation

- [kit/README.md](kit/README.md): applying the kit to a project
- [kit/korean-writing.md](kit/korean-writing.md): instructions for writing and reviewing Korean development documents
- [kit/delegation.md](kit/delegation.md): when to delegate, roles, risk levels, the strong-call budget, retries and measurement
- [kit/review-session.md](kit/review-session.md): running a separate review session alongside the main one
- [docs/cli.md](docs/cli.md): installation, role files, usage totals, the review channel and the release runner
- [docs/tools.md](docs/tools.md): change snapshots, isolated checks, publishing and screen capture
- [docs/scope.md](docs/scope.md): the product's role, responsibilities and extension criteria
- [docs/validation.md](docs/validation.md): what the tests cover and what remains unverified
- [docs/roadmap.md](docs/roadmap.md): current features and implementation priorities

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/build_release.py        # needs setuptools>=68 and wheel
```

The browser test is skipped unless `AWKIT_UI_TEST=1` is set with Playwright installed. GitHub Actions runs the suite on Windows and Linux with Python 3.11 to 3.13. Pushing a tag that matches the package version, such as `v0.2.0`, builds the wheel and the kit ZIP and attaches them to a release.

## License

No license has been chosen yet.
