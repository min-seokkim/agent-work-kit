# Development

The single record for developing Agent Work Kit: scope, decisions, current state, next work, release, and what has been verified. The failures the kit prevents are listed in [failures.md](failures.md). Agents working on this repository read and update it; people read the README. Command behavior is documented for agents in [kit/reference.md](../kit/reference.md), which ships with the kit.

## Rules for working in this repository

The working rules (commit identity, versions, dates, documentation audience, writing style, kit length) are in [AGENTS.md](../AGENTS.md) at the repository root, where coding agents read them automatically. `CLAUDE.md` imports it for Claude Code.

## Scope

Agent Work Kit is a public project. It has three layers:

| Layer | Content | Why it exists |
|---|---|---|
| Baseline workflow | A short default procedure for any task: define it, do it, check a frozen version, report with evidence. Written as what to do, with the reason. | The kit needs a coherent way of working, and new situations have nothing else to fall back on. Overlap with other projects is fine. |
| Situation guards | Guidance loaded only when its situation arises (skills where the agent supports them), hooks, and `awkit` checks. | Each prevents an entry in [failures.md](failures.md) and needs a recorded occurrence and a check. |
| Failure catalogue | [failures.md](failures.md). A design document, not given to agents. | Chooses the guards, measures whether they catch anything, and shows what to remove. |

Overlap with other projects such as superpowers or spec-kit is decided by whether the kit's users need the piece, not by whether another project has it. Overlapping text is kept short and written so it does not conflict when used together with those projects.

The tool's core loop supports the workflow and the guards: fix the input, run the project's checks on it, retain the evidence, compare later results with what was accepted.

The project environment keeps running agents, builds, tests, services, deployment and hosting. awkit connects to the project's existing commands and records identifiers and evidence: which revision was checked, with which command, with what result.

A new situation guard needs a failure entry it prevents, with a recorded occurrence, and a check that would have caught that occurrence. Baseline workflow text needs a step of the default procedure it describes and stays within the every-session word limit. Any new feature also needs a reason the existing commands cannot be extended, a way to see the target version, the result and the cause of failure, and tests for its important failure paths. Kit text that is neither baseline workflow nor a guard for a listed failure moves to the reference or is removed. Measure effect by time to finish, rework, usage and defects found after acceptance, never by the number of features or roles.

## Decisions

| Decision | Detail |
|---|---|
| Git is required | The review commands work on Git-tracked files. Non-developers get an easy install path instead of a Git-free mode (see next work: `doctor`, install scripts). |
| Web-only tools are extras | `pipeline`, `publish` and `ui` are useful mainly for web projects. They move to `src/awkit/extras/` with their command names unchanged and are not mentioned in the READMEs. If real use does not need them, they leave the package. |
| Public project; baseline workflow plus failure guards | See Scope. The failure catalogue chooses and measures the guards; agents receive the baseline workflow and the guards, written as what to do. This replaces the earlier plan to split the kit into `dev` and `work` profiles chosen at install time. |
| One repository, one package | Unchanged. |
| Restrain the kit's length | Limits by when a file is read, in `tests/test_kit.py`: the files read at the start of every session (kit README, agent instructions, project profile) together stay within 2,000 words, which is what Claude Code's documentation recommends for CLAUDE.md (about 200 lines); every other file is read when its situation arises and stays within 3,500 words, about the 5,000 tokens that survive a context compaction whole. There is no total: an agent never reads the whole kit at once, and the number of rules is held down by requiring each section to serve the baseline workflow or a failure entry. |
| Agents are the readers | See the documentation rule above. |
| Hold the first release | Until the release conditions below are met. |

## Current state

| Area | State |
|---|---|
| Kit | Agent instructions with a "Connect the kit to a project" procedure, task protocol, project profile with five "Start here" fields, work-type completion evidence, delegation guide and five role templates, review-session guide, writing guide with a Korean supplement, task/review/decision/checkpoint templates, command reference. |
| `kit` commands | `init` and `example` (documents, data, analysis) commit only the folder they create; `scan` reports manifests, CI checks, docs and Git state and drafts `checks.toml`; `roles` writes Claude Code or Codex role files. |
| `check` | `commit` (author and trailers against history), `writing` (patterns from the writing guides), `done` (changed files need a passing check of their current state); `kit hooks` installs them as Git and Claude Code hooks. |
| `review` | `snapshot`, `check` (isolated worktree, setup and checks, artifacts with hashes, paths relative to the run folder), `verify`, `accept` (locked), `compare` (with a note for worktree-only outputs). Refuses untracked folders. |
| `channel` | SQLite message log between `main` and `reviewer`: requests, replies, rebuttals, waits, close. One session per role. |
| `usage` | Claude Code and Codex logs; result format 2 with unmeasured fields as `null`, user messages, commands and minutes. User message filtering checked against a real Claude Code log. |
| Extras | `pipeline` (delivery commands, verification of the running release, rollback history, reconcile, optional backup and rollback), `publish` (static site with link checks and atomic switch), `ui` (multi-width captures with overflow checks). Mock examples only. |
| Version | 0.3.0, unreleased. No tag or release exists. |

## Next work

| Order | Work | Done when |
|---|---|---|
| 1 | Complete the failure catalogue | Done for the owner's records: their writing corrections (F1, F13 to F15, F29 to F34) and their corrections from research, explanation, troubleshooting and purchase conversations (F11, F12, F28, F35 to F39) are merged. The thirteen entries still marked "needs evidence" (F2, F16 to F27) concern review sessions, delegation, data work and operations, which those records do not cover; they get occurrences from the real tasks in 5 or are removed then. |
| 2 | First mechanical checks | Done. `awkit check commit` (F9, a Git hook here and a CI step on every pushed commit), `awkit check writing` (F13, F14, F32, run over every document by the test suite), `awkit check done` (F1, a Claude Code Stop hook), `awkit kit hooks` to install them, and a test that runs the example READMEs' commands as written (F4, F5). Each test replays the recorded occurrence. |
| 3 | Restructure the kit into baseline and guards | Baseline workflow within the every-session limit; situation guidance loaded on trigger, generated as skills for agents that support them (confirm Codex support first); each section mapped to no entry in `failures.md` either kept as baseline workflow, moved to the reference or removed; extras moved to `src/awkit/extras/`. |
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

Procedure: confirm CI is green, finalize the CHANGELOG section, push a tag matching the version (`v0.3.0`). `.github/workflows/release.yml` tests, builds the wheel, the kit ZIP and `SHA256SUMS` with `scripts/build_release.py`, creates the GitHub release and uploads the wheel to PyPI through a trusted publisher. One-time setup before the first tag: create a `pypi` environment in the GitHub repository settings (add a required reviewer to approve uploads), and add a pending publisher on PyPI for project `agent-work-kit`, this repository, workflow `release.yml`, environment `pypi`. Without it only the PyPI job fails. A version uploaded to PyPI can never be reused. The name `agent-work-kit` was free on PyPI when last checked; check again before the first tag.

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
| GitHub Actions, Windows and Linux, Python 3.11 to 3.13 | `dev` from `b5d78ba` | Full suite, Ruff, Windows wheel install with the mock release and the data example: green. The first `dev` run found two Linux-only assumptions in tests (Windows path ordering and 8.3 short names), since fixed. |
| Linux, Python 3.13.16 | `dev` through `5a2ad25` | 105 tests, 104 passed, browser test skipped. 0.3.0 wheel and a `git+https` install from GitHub both report `awkit 0.3.0`; the data example fails as designed. |
| Windows, Python 3.14.7, and WSL, Python 3.12.3 | step `cwd` support | 79 tests; Windows skipped two symlink tests and the browser test. |
| Windows, Python 3.12.14, Playwright 1.64.0 with Edge | snapshot, publish and capture | 320 px and 1440 px captures of local pages; normal pages, overflow and blocked requests told apart. |
| Real Claude Code logs | `usage` | 376 lines grouped into 156 calls; a later log gave 13 typed messages and 1 command, excluding notices, command output, interruptions and hook feedback. |

Not verified: Codex parsing against a current log; `release.yml` (never run); real server deployment, real devices, external submission; any database or external agent call. Known limits: worktrees do not isolate DBs, ports or devices; a timeout stops local processes but not remote work; snapshots do not filter secrets; `publish` trusts its HTML and its lock is local only; `ui` judges only overflow and off-screen controls.
