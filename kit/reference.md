# awkit Command Reference

Look things up here when you run `awkit`; you do not need to read it before every task. `awkit <command> --help` lists the options of each command. Commands print JSON on stdout unless noted, and diagnostics on stderr.

Requirements: Python 3.11+, Git for `kit init`, `kit example` and `review`, Playwright for `ui`. The project under work can be in any language.

## doctor

`awkit doctor [DIR] [--json]` checks Python (3.11 or later), Git (2.25 or later), Git `user.name` and `user.email` (commits fail without them), whether `awkit` is on PATH, and in DIR whether there is a repository with a commit, a kit folder and skills. Each item is `ok`, `missing` or `warning`, with the command that fixes it. Exit 0 when nothing required is missing, 1 otherwise.

## Git tracking

- `review` commands check files that Git tracks. They never create a repository or a commit. In a folder that is not a repository, or a repository with no commit, they exit 2 and say so; commit the files first.
- `kit init` and `kit example` commit only the folder they created. They create the repository when there is none and set `core.autocrlf=false` in it, so committed bytes equal checked bytes. When the index already has staged changes they skip the commit and say so on stderr, so the user's work is never bundled in. `--no-git` copies without tracking.
- `review` resolves file names, step `cwd` and `artifacts` patterns relative to the folder it runs in (`--repo`, default the current folder), in the same subfolder of the checked worktree. The run records that subfolder as `subdir`.

## kit

| Command | Effect | Exit |
|---|---|---|
| `kit init [DIR] [--name NAME] [--no-git]` | Creates `DIR/NAME` (default `agent-work-kit`) with the kit. Never touches an existing folder. | 0, or 2 if the folder exists |
| `kit example documents\|data\|analysis DIR [--no-git]` | Creates a small project with one deliberate defect and a README that walks through fail, fix, re-check, verify, accept. | 0, or 2 if `DIR` exists |
| `kit scan [DIR] [--checks]` | Reports manifests, languages, check commands, CI run lines, docs folders, Git state and kit state, plus `suggested_checks_toml`. `--checks` prints only the TOML draft. | 0 |
| `kit roles [DIR] --provider claude\|codex [--model TIER=MODEL[:EFFORT]]...` | Writes role files from the [role templates](templates/roles/README.md). Existing files are kept. | 0, or 2 if every file already existed |
| `kit skills [DIR] --provider claude\|codex [--kit PATH]` | Writes one skill per situation guide: `.claude/skills/awkit-*/SKILL.md` for Claude Code, `.agents/skills/awkit-*/SKILL.md` for Codex. Each holds the guide's situation as its description and tells the agent to read the guide in the kit folder (`--kit`, default `DIR/agent-work-kit`). Existing files are kept. | 0, or 2 if every file already existed |
| `kit hooks [DIR] [--git] [--claude]` | `--git` writes the repository's `commit-msg` hook running `check commit`. `--claude` adds SessionStart and Stop hooks running `check done --hook` to `.claude/settings.local.json`. Both name this machine's Python, so neither is committed. Existing hooks are kept. | 0 |

`kit scan` reads file names and manifests only. Its commands come in this order: check steps that GitHub Actions already runs (no shell syntax, install steps dropped), then package.json scripts, ruff and mypy settings, pytest when pytest is configured (`[tool.pytest]`, `pytest.ini`, `conftest.py`), Makefile targets, Go and Rust defaults. Equivalent commands appear once. Run the draft with `awkit review check HEAD --config checks.toml` and keep only what works.

## review

### snapshot

`awkit review [--repo DIR] snapshot FILE...` prints one commit ID: HEAD plus the current content of the named files only. Added and deleted files count when named. The branch, index and working tree are untouched. Directories, links, ignored files and paths outside the repository are refused. Everything already committed in HEAD is in the snapshot; nothing filters secrets. The commit is unreferenced and `git gc` may remove it later.

### check

`awkit review [--repo DIR] check REVISION --config FILE [--runs-root DIR] [--keep]`

`REVISION` is a full commit ID or `HEAD`. The runner adds a fresh worktree at that commit, runs the setup steps, then the checks, retains artifacts and removes the worktree. The configuration is read from outside the snapshot and its SHA-256 is recorded; it names programs to run, so it must come from a trusted source.

```toml
schema = 1
timeout_seconds = 300            # per step, default 300, at most 86400
artifacts = ["dist/*.whl", "reports/**/*.html"]
required_artifacts = ["dist/*.whl"]

[env]                            # added to the inherited environment
APP_MODE = "test"

[[setup]]                        # any failure skips the checks
name = "build"
argv = ["{python}", "-m", "build"]

[[checks]]                       # every check runs even when one fails
name = "sdk-tests"
cwd = "packages/sdk"             # relative to the base folder, "/" separators
argv = ["python", "-m", "pytest", "-q"]
```

- Step names are distinct. `argv` is an argument array and never goes through a shell.
- `cwd` defaults to the base folder (see Git tracking). Absolute paths, `..`, `.git` and empty paths are refused before running. A `cwd` that is missing or resolves outside the worktree fails that step.
- Placeholders in `argv` and `env` values: `{python}` (the interpreter running awkit, not necessarily the project's), `{worktree}`, `{run_dir}`, `{run_id}`. Steps also get `AWKIT_WORKTREE`, `AWKIT_RUN_DIR`, `AWKIT_RUN_ID`.
- Artifact patterns are relative to the base folder and accept `*`, `?`, `**`. Matches are copied after all steps, even when checks failed. Links and paths outside the worktree are skipped and listed under `skipped_artifacts`. A `required_artifacts` pattern with no match turns a passing run into `failed`.
- A timeout or interruption kills the step's whole process tree, records `uncertain` and keeps the worktree. Remote work the step started is not stopped.
- Worktrees share DBs, ports, sockets and devices. Allocate them per `{run_id}` in the project's commands.

Run folder (default under the system temp folder; use `--runs-root` to keep it):

| Path | Content |
|---|---|
| `result.json` | `snapshot`, `config_sha256`, `subdir`, `status`, `steps` (name, phase, cwd, argv, exit code, status, log), `artifacts` (size, sha256), `missing_artifacts`, `worktree_retained` |
| `config.toml` | The configuration used |
| `NN.log` | Output of step NN |
| `artifacts/` | Retained files and `manifest.json` (snapshot, config hash, subdir, run ID, files) |

`status` is `passed`, `failed`, `uncertain` (a timeout) or `cleanup-failed`. Exit codes: 0 passed, 1 failed or uncertain, 2 configuration or Git error.

### verify, accept, compare

| Command | Effect | Exit 0 when |
|---|---|---|
| `review verify RUN_DIR` | Rehashes each retained file: `ok`, `changed`, `missing`; lists extra files under `unexpected`; `interrupted` when `result.json` still says `running`. | `verified` is true |
| `review accept RUN_DIR [--label L]` | Verifies the run, then copies its artifacts to `.awkit/accepted/<label>/` (default `accepted`) with `accepted.json` recording run, commit, config hash and hashes. Replaces an earlier version with the same label. One accept at a time per repository (lock `.awkit/accept.lock.sqlite3`). | accepted |
| `review compare [--label L] [--run RUN_DIR] [--diff]` | Compares each accepted file with the working tree, or with a run's artifacts given `--run`: `same`, `changed`, `missing`. `--diff` adds unified diffs for changed text files. | every file is `same` |

Files a check produced exist only in its worktree, so comparing with the working tree reports them `missing` and adds a `note`; compare a later run with `--run` instead. A matching hash shows the bytes are unchanged; whether the content is right is for the review record to say.

## check

Checks meant to run without anyone choosing to: from a Git hook, a Claude Code hook or CI.

| Command | Effect | Exit |
|---|---|---|
| `check commit --message FILE \| --rev REV [--history N]` | Compares the author and the trailer keys (`Key: value` lines Git recognizes at the end of the message) with the last N commits (default 50). An author whose email is not among them, or a trailer key none of them use, is reported with how to fix it. A repository without earlier commits passes. Allow a new contributor with `git config --add awkit.allowAuthor EMAIL` and a trailer with `git config --add awkit.allowTrailer KEY`. | 0 consistent, 1 not |
| `check writing PATH... [--json]` | Searches Markdown files, and folders recursively, for the patterns in the [Writing Guide](writing.md). Errors: em dashes, a middle dot joining Korean words, `-세요` and `-시오` endings in one document. Warnings: lead-ins, contrasts against a claim nobody made, sales words, Korean stock phrases. Code blocks, blockquotes, inline code, quoted spans and link targets are skipped. | 0 no errors, 1 errors |
| `check done [--session ID] [--mark] [--runs-root DIR] [--hook]` | `--mark` records the current state (HEAD plus every working-tree change, untracked files included, `.awkit/` excluded) as the session's starting point in `.awkit/done/`. Without it: passes when nothing changed since that point (or since HEAD when none was recorded), or when a passing `review check` run checked exactly the current state; otherwise lists the changed files. Runs are looked up in `--runs-root`, `.awkit/reviews` and the system temp default. | 0 yes, 1 no |

With `--hook`, `check done` reads the Claude Code hook input from stdin: SessionStart marks the starting point (a resumed or compacted session keeps the one it has), Stop exits 2 with the reason on stderr so the agent continues, and a second stop in the same turn (`stop_hook_active`) passes, so the agent can report work it could not check and say why.

## channel

A message log in SQLite shared by two local sessions: `main` (implements) and `reviewer`. Both use the same `--db` (default `.awkit/channel.sqlite3`). Keep the file on a local disk, outside sync folders; there is no authentication. The workflow is in [Review Session Collaboration](review-session.md).

`awkit channel [--db FILE] post SENDER RECEIVER KIND [--reply-to ID] [--snap ID] [--body TEXT | --body-file FILE]` prints the new message ID (`M-001` from main, `R-001` from reviewer). Without `--body` or `--body-file` the body is read from stdin. Empty bodies are refused.

| Kind | Rules |
|---|---|
| `review`, `scout`, `test`, `draft`, `question`, `final` | Requests. |
| `notice` | No reply expected. |
| `re`, `rebut` | Need `--reply-to` naming a message the other side sent. |
| `close` | Main only. No further posts; start a new file for new work. |

`--snap` takes 7 to 64 lowercase hex characters.

`awkit channel wait ROLE MODE [ID] [--max SECONDS] [--json]` (default 120 s, `--max 0` checks once):

| Mode | Returns |
|---|---|
| `request` | Requests and rebuttals to ROLE not yet answered by ROLE |
| `new` | Messages to ROLE after its read position, then moves the position (shared by sessions using the same role) |
| `reply ID` | Replies and rebuttals to message ID |

Exit codes: 0 found, 1 timed out, 2 usage or storage error, 3 the reviewer received `close`. `awkit channel export [--json]` prints the whole log; bodies are quoted so they cannot imitate headers.

## usage

`awkit usage PATH... [--since YYYY-MM-DD] [--json]` reads Claude Code and Codex `.jsonl` session logs (folders recursively) and reports per thread: provider, models, effort, calls, user messages, commands, minutes, fresh input, cache write, cache read and output tokens. It prints models and counts, never message content.

- Claude Code: one response written over several lines counts once; subagent records form `subagent <ID>` threads; calls are responses. A user message is text a person typed (`origin.kind = human` when present). Tool results, notices (`isMeta`), compaction summaries, command output, interruption markers and hook messages are not counted. Slash and shell commands count under `commands`.
- Codex: one file is one thread; models from `turn_context`, tokens from the last cumulative `token_count`, user messages from `user_message` events; calls are turns. Codex parsing follows field names from real files but has not been checked against a current one.
- `--json` result `format` is 2. A token field is `null` when any record lacked it or held an invalid value; `missing` and `invalid` count the affected records. `total` sums known values, and `total.complete` is true only when every field was measured and nothing was skipped. `skipped_lines` counts `damaged_lines` and a `partial_line` per file; `unrecognized_files` lists files of unknown format.

## Extras for web projects

### pipeline

`awkit pipeline --config FILE plan|deploy RELEASE|rollback|status|reconcile|history [--allow-unhealthy-current] [--json]` runs the project's delivery commands in a fixed order and verifies the target's actual state. Its statuses (`passed`, `failed-restored` and the rest) describe one run, not the state of a task. Release IDs are 7 to 64 lowercase hex characters; use full commit or artifact hashes.

```toml
schema_version = 1

[pipeline]
target = "web"                   # letters, digits, . _ -
state_dir = ".awkit/releases"    # relative to this file
timeout_seconds = 120            # per command
required_checks = ["service"]
auto_rollback = false            # needs a rollback command

[commands]                       # argument arrays, no shell
preflight = ["{python}", "{project}/adapter.py", "preflight", "{target}", "{release}"]
backup    = ["{python}", "{project}/adapter.py", "backup", "{target}", "{release}"]    # optional
deploy    = ["{python}", "{project}/adapter.py", "deploy", "{target}", "{release}"]
verify    = ["{python}", "{project}/adapter.py", "verify", "{target}", "{release}"]
rollback  = ["{python}", "{project}/adapter.py", "rollback", "{target}", "{release}"]  # optional
```

Placeholders: `{python}`, `{project}` (the config folder), `{target}`, `{release}`, `{previous}`, `{run_dir}`. The command contract:

- `preflight` prints `{"target": T, "release": ID or null}` without changing anything.
- `deploy` and `rollback` finish all work before exiting; nothing left in the background.
- `verify` reads the release actually running and prints `{"target": T, "release": ID, "checks": [{"name": N, "ok": true}]}`, exiting 0 even when a check fails. Every `required_checks` name must appear. A wrong target, a release other than the requested one, or malformed JSON fails the step. Echoing the requested release defeats verification.
- Omit `backup` and `rollback` for one-way deliveries (submissions, uploads). Then `rollback` and `auto_rollback` are refused, and a failure after the target changed is `failed-unrecovered`.

Order: preflight, verify-current, backup, deploy, verify. A deploy stops at `verify-current` when the current release fails its checks, unless `--allow-unhealthy-current`. Deploying the running healthy release only verifies (`outcome: already-current`). `rollback` takes no release; it walks back one healthy release from `history.json` per run.

| Status | Meaning |
|---|---|
| `passed` | The requested release runs and every check passes. |
| `failed` | Failed before the target changed. |
| `failed-restored` | Deploy failed; automatic rollback restored and verified the previous release. Exit 1. |
| `failed-unrecovered` | Failed after the target changed; recovery not confirmed. |
| `rollback-failed` | Automatic rollback or its verification failed. |
| `uncertain` | Timeout or interruption; state unknown. |

After `running`, `uncertain`, `rollback-failed` or `failed-unrecovered`, every deploy and rollback is blocked. Inspect the real target, recover it, then run `reconcile`: it records `reconciled` (exit 0) or `reconciled-unhealthy` (exit 1) and lifts the block. Do not delete records to skip this. One run per `state_dir` at a time (SQLite lock); there is no lock on the target itself. State: `last-run.json`, `history.json`, `runs/<id>/result.json`, `runs/<id>/logs/`. Logs keep raw output, so keep secrets out of arguments and output. Exit codes: 0 passed, reconciled or healthy (`status`); 1 any other outcome; a project command's own code when it fails with 1 to 125; 2 cannot run; 130 interrupted. A file-only mock is in `examples/local-release/` of the awkit repository.

### publish

`awkit publish --output DIR --project NAME build --source DIR --files LIST.json` publishes a trusted static HTML build. `LIST.json` is a JSON array of relative paths and must include `index.html`; only listed files are copied. Before publishing, every HTML link, anchor and simple CSS `url()` must point at a listed file; external pages may be linked, external resources may not. `@import`, `srcset`, `srcdoc` and `base` are refused. Each version goes to `versions/<content hash>/`, is verified, and only then the entry `index.html` is replaced atomically. `restore VERSION` re-verifies and switches back. The output folder must be empty on first use. One publisher per output folder at a time; the lock does not work across machines or sync folders.

### ui

`awkit ui --config pages.json --output DIR [--channel chrome|msedge|chromium]` captures full-page PNGs of the listed pages at each width and builds `index.html`, `sheet.png` and `result.json` in an empty output folder.

```json
{"base_url": "http://127.0.0.1:8765", "widths": [320, 1440], "timeout_ms": 15000,
 "pages": [{"name": "Home", "path": "/index.html"}]}
```

`base_url` is an origin without credentials or path; 1 to 20 pages, 1 to 6 distinct widths between 240 and 3840. Only same-origin GET and HEAD requests are allowed; other requests, service workers and WebSockets are blocked. Findings per page and width: `horizontal-overflow`, `control-outside-viewport`, `http-error`, `capture-error` and `resource-blocked`. Any finding makes the exit code 1. Judge layout and content from the images yourself.
