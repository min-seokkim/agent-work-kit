# Development

The single record for developing Agent Work Kit: scope, decisions, current state, next work, release, and what has been verified. The failures the kit prevents are listed in [failures.md](failures.md). Agents working on this repository read and update it; people read the README. Command behavior is documented for agents in [kit/reference.md](../kit/reference.md), which ships with the kit.

## Rules for working in this repository

- Commit as the repository owner, `min-seokkim <raptor210@snu.ac.kr>` (set in `.git/config`). Do not add `Co-Authored-By` or `Claude-Session` lines to commit messages.
- Do not raise the version per commit. Collect changes in the unreleased section of [CHANGELOG.md](../CHANGELOG.md); raise the version only for a release, or once when the first incompatible change goes in after a release.
- Work on `dev`. CI runs on every push to `dev` and `main`; a push is done only when CI is green on Windows and Linux.
- Documentation audience: `README.md` and `README.ko.md` are the only documents written for people, and stay short. Everything else, including this file, the kit and the CHANGELOG, is read by agents and written in English. The kit's Korean writing guide keeps its Korean examples.
- Write plainly. State facts instead of staging them: no "not X but Y" contrasts against claims nobody made, no lead-ins ("here's", "you have probably seen"), no closing lines that repeat the paragraph, no slogans, no bold labels or decorative bold, no em dashes, no sales words. Korean text follows `kit/korean-writing.md`, including the preservation list and the separate fact, sentence and flow reviews.
- Keep the kit short: the instruction text in `kit/` (licenses and `reference.md` excluded) stays within the word limit enforced by `tests/test_kit.py`. Before adding a rule, look for an existing rule that covers the same failure; if the limit is exceeded, shorten something else.

## Scope

Agent Work Kit is a public project. It prevents specific, recurring agent failures instead of prescribing a whole way of working; methodology packs such as superpowers or spec-kit already cover that, and the kit should work alongside them. Each failure is an entry in [failures.md](failures.md) with the situation it occurs in, a recorded occurrence and a check. Where possible the check is mechanical (an `awkit` command, a hook, a test), and kit text is loaded only in the situation it serves.

The tool's core loop supports those checks: fix the input, run the project's checks on it, retain the evidence, compare later results with what was accepted.

The project environment keeps running agents, builds, tests, services, deployment and hosting. awkit connects to the project's existing commands and records identifiers and evidence: which revision was checked, with which command, with what result.

A new feature or piece of kit text needs a failure entry it prevents, with a recorded occurrence, and a check that would have caught that occurrence. It also needs a reason the existing commands cannot be extended, a way to see the target version, the result and the cause of failure, and tests for its important failure paths. Kit text that prevents no listed failure is removed or moved to the reference. Measure effect by time to finish, rework, usage and defects found after acceptance, never by the number of features or roles.

## Decisions

| Decision | Detail |
|---|---|
| Git is required | The review commands work on Git-tracked files. Non-developers get an easy install path instead of a Git-free mode (see next work: `doctor`, install scripts). |
| Web-only tools are extras | `pipeline`, `publish` and `ui` are useful mainly for web projects. They move to `src/awkit/extras/` with their command names unchanged and are not mentioned in the READMEs. If real use does not need them, they leave the package. |
| Public project, failure-driven | The kit is organized around the failure catalogue. Countermeasures are delivered by situation: a small always-read core, guidance loaded when its situation arises (skills where the agent supports them), and hooks or `awkit` checks for what a machine can verify. This replaces the earlier plan to split the kit into `dev` and `work` profiles chosen at install time. |
| One repository, one package | Unchanged. |
| Restrain the kit's length | One word limit for now; separate limits for the always-read core and for each situation's guidance once the kit is restructured. |
| Agents are the readers | See the documentation rule above. |
| Hold the first release | Until the release conditions below are met. |

## Current state

| Area | State |
|---|---|
| Kit | Agent instructions with a "Connect the kit to a project" procedure, task protocol, project profile with five "Start here" fields, work-type completion evidence, delegation guide and five role templates, review-session guide, Korean writing guide, task/review/decision/checkpoint templates, command reference. |
| `kit` commands | `init` and `example` (documents, data, analysis) commit only the folder they create; `scan` reports manifests, CI checks, docs and Git state and drafts `checks.toml`; `roles` writes Claude Code or Codex role files. |
| `review` | `snapshot`, `check` (isolated worktree, setup and checks, artifacts with hashes, paths relative to the run folder), `verify`, `accept` (locked), `compare` (with a note for worktree-only outputs). Refuses untracked folders. |
| `channel` | SQLite message log between `main` and `reviewer`: requests, replies, rebuttals, waits, close. One session per role. |
| `usage` | Claude Code and Codex logs; result format 2 with unmeasured fields as `null`, user messages, commands and minutes. User message filtering checked against a real Claude Code log. |
| Extras | `pipeline` (delivery commands, verification of the running release, rollback history, reconcile, optional backup and rollback), `publish` (static site with link checks and atomic switch), `ui` (multi-width captures with overflow checks). Mock examples only. |
| Version | 0.3.0, unreleased. No tag or release exists. |

## Next work

| Order | Work | Done when |
|---|---|---|
| 1 | Complete the failure catalogue | The owner's collected writing patterns merged; every "needs evidence" entry either gets a recorded occurrence or is marked for removal. |
| 2 | First mechanical checks | For entries with no kit text and clear evidence: run documented commands in CI (F4, F5); a commit identity check (F9); a writing check for the listed English and Korean patterns (F13, F14); a done-report check that requires a passing run for the current snapshot (F1). Each check comes with the occurrence it would have caught as a test. |
| 3 | Restructure the kit by situation | Always-read core within its own word limit; situation guidance loaded on trigger, generated as skills for agents that support them (confirm Codex support first); sections mapped to no entry in `failures.md` removed or moved to the reference; extras moved to `src/awkit/extras/`. |
| 4 | Easy setup for non-developers | `awkit doctor` checks Python, Git and Git user name and email (without them awkit's commits fail) and says how to fix each; `install.ps1` and `install.sh` install missing Git or Python with winget or brew, then awkit with pipx. |
| 5 | Run real tasks and compare | One document, one data and one code task, each also done without the kit and with a methodology pack alone where practical. Record minutes, tokens, user messages (`awkit usage`), defects found after acceptance and which catalogue failures occurred or were caught. Checks that catch nothing are fixed or removed. Also connect one existing project with `kit scan` and record how many drafted commands were right. |
| 6 | Check usage against current logs | Compare format 2 values with what Claude Code and Codex show, using current log files; mismatched fields must surface as `missing` or `invalid`. |
| 7 | One-shot automation example | A mock example whose trigger and stop condition live in a config file, recording setup and the actual firing separately, using the existing check runner and artifacts. |
| 8 | Task start lookup | After 5 settles the record format: extend `kit scan` to read runs, accepted versions and checkpoints and summarize state and the next action. |
| 9 | Channel receipts | Only if 5 shows several sessions reading as one role, or a need to separate "read" from "handled": per-consumer positions and explicit acknowledgement. |
| 10 | Hand-off to another environment | Export and import of request ID, base revision, retained artifacts and replies, with repeated-input and version-mismatch checks. Remote transport after two real environments are chosen. |

Small items: the example folders have no `.gitignore`, so `.awkit/` run folders show up as untracked files (the wheel's package data must include the dot file). Work that does not fit the fix-check-retain-compare loop, such as presentations or speaking practice, stays guidance in `work-types.md`.

## Release

Release conditions, all required before the first tag:

1. The kit is restructured by situation, the extras are moved, and no further change to command names or file locations is planned.
2. The real tasks (next work 5) have been run and their findings applied.
3. No change is planned to formats other tools read: check configuration, `result.json`, artifact manifests, usage results.

Until then users install from `dev`: `pipx install "git+https://github.com/min-seokkim/agent-work-kit@dev"`.

Procedure: confirm CI is green, finalize the CHANGELOG section, push a tag matching the version (`v0.3.0`). `.github/workflows/release.yml` tests, builds the wheel, the kit ZIP and `SHA256SUMS` with `scripts/build_release.py`, creates the GitHub release and uploads the wheel to PyPI through a trusted publisher. One-time setup before the first tag: create a `pypi` environment in the GitHub repository settings (add a required reviewer to approve uploads), and add a pending publisher on PyPI for project `agent-work-kit`, this repository, workflow `release.yml`, environment `pypi`. Without it only the PyPI job fails. A version uploaded to PyPI can never be reused. The name `agent-work-kit` was free on PyPI on 2026-10-22.

## Testing and building

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
ruff check .
python -m pip install "setuptools>=77" wheel && python scripts/build_release.py
```

Tests use only the standard library, need Git and no network. `tests/support.py` gives child processes an absolute `PYTHONPATH`. The browser test runs only with `AWKIT_UI_TEST=1` and Playwright (`AWKIT_BROWSER_CHANNEL=msedge` for Edge). Symbolic link tests skip where the OS refuses links.

## Verification record

| Environment | Code | Result |
|---|---|---|
| GitHub Actions, Windows and Linux, Python 3.11 to 3.13 | `dev` from 2026-10-22 | Full suite, Ruff, Windows wheel install with the mock release and the data example: green. The first `dev` run found two Linux-only assumptions in tests (Windows path ordering and 8.3 short names), since fixed. |
| Linux, Python 3.13.16 | 2026-10-22, through the release hold | 105 tests, 104 passed, browser test skipped. 0.3.0 wheel and a `git+https` install from GitHub both report `awkit 0.3.0`; the data example fails as designed. |
| Windows, Python 3.14.7, and WSL, Python 3.12.3 | step `cwd` support | 79 tests; Windows skipped two symlink tests and the browser test. |
| Windows, Python 3.12.14, Playwright 1.64.0 with Edge | snapshot, publish and capture | 320 px and 1440 px captures of local pages; normal pages, overflow and blocked requests told apart. |
| Real Claude Code logs | `usage` | 376 lines grouped into 156 calls; a later log gave 13 typed messages and 1 command, excluding notices, command output, interruptions and hook feedback. |

Not verified: Codex parsing against a current log; `release.yml` (never run); real server deployment, real devices, external submission; any database or external agent call. Known limits: worktrees do not isolate DBs, ports or devices; a timeout stops local processes but not remote work; snapshots do not filter secrets; `publish` trusts its HTML and its lock is local only; `ui` judges only overflow and off-screen controls.
