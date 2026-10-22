# awkit Command Reference

Look things up here when you run `awkit`; you do not need to read it before every task. `awkit <command> --help` lists the options of each command. Commands print JSON on stdout unless noted, and diagnostics on stderr.

Requirements: Python 3.11+, Git for the hooks `kit init` installs and for its `--commit`, `kit example`, `kit hooks --git` and `review`, Playwright for `ui`. The project under work can be in any language.

## doctor

`awkit doctor [DIR] [--json]` checks Python (3.11 or later), Git (2.25 or later), Git `user.name` and `user.email` (commits fail without them) and, in a repository, whether that identity fits its history (the rule of `check commit`), whether `awkit` is on PATH, and in DIR whether there is a repository with a commit, a kit folder or the version recorded in `.awkit/installed.json` (a warning when another awkit wrote it), awkit's skills, and another Git repository inside it (see Git tracking). Each item is `ok`, `missing` or `warning`, with the command that fixes it. Exit 0 when nothing required is missing, 1 otherwise.

It also reports the loaded package path and its installation commit when matching distribution metadata records one. Source execution reports the code checkout's HEAD and whether its source and kit have local changes; another installed distribution's metadata is not attributed to that code. Missing provenance stays explicit, and recorded provenance does not establish file integrity or whether the installation is current. Source URLs and credentials are not printed.

An existing `checks.toml` is validated with the same configuration rules as `review check`, without running commands. Empty or invalid settings produce a warning; valid configuration is reported as execution unverified. The final line reports missing tools or warnings instead of claiming readiness. Exit 0 does not establish passed checks or automatic hook execution; the JSON finding fields and exit codes are unchanged.

## Git tracking

- `review` commands check files that Git tracks. They never create a repository or a commit. In a folder that is not a repository, or a repository with no commit, they exit 2 and say so; commit the files first.
- `kit init` and `kit init --copy` write files and print what they wrote; they commit nothing and never create a repository, and outside one they say so. With `--commit`, in an existing repository, `kit init` commits `checks.toml` and `rules.toml` when it wrote them, and nothing when either had uncommitted changes before it ran; `kit init --copy --commit` commits only the folder it created. `kit example` commits the folder it created, creating the repository when there is none with `core.autocrlf=false`, so committed bytes equal checked bytes; `--no-git` only copies. When the index already has staged changes these commits are skipped with a note on stderr, so the user's work is never bundled in. In a repository that only awkit has committed to they are made as `Agent Work Kit <awkit@localhost>`, which `check commit` does not count as history; in one with history as the configured identity, skipped with the reason when it looks like a coding agent's (`Claude`, an `anthropic.com` or `openai.com` address) or has not committed there before.
- Another Git repository inside the project, such as a clone of awkit, is not supported: a snapshot cannot hold a folder, so changes there can never be checked. `doctor` and `kit scan` list such folders, and `check done` fails while one is present. Move it outside the project or add it to `.gitignore`; ignored folders and submodules are not affected.
- `review` resolves file names, step `cwd` and `artifacts` patterns relative to the folder it runs in (`--repo`, default the current folder), in the same subfolder of the checked worktree. The run records that subfolder as `subdir`.

## kit

| Command | Effect | Exit |
|---|---|---|
| `kit init [DIR] [--commit] [--no-git]` | Connects the kit without copying it (see Connecting below): appends the Agent Work Kit section to the instruction files agents already read, writes the self-contained skills for each agent the project uses, and records both in `.awkit/installed.json`. Prints the words added to every session. A section already there is kept, including a filled profile. | 0, or 2 if nothing was added |
| `kit init --copy [DIR] [--name NAME] [--commit]` | Creates `DIR/NAME` (default `agent-work-kit`) with the whole kit and `VERSION.txt`: the awkit version, and when copied from a source checkout its commit and whether `kit/` had uncommitted changes (copied as they were). Never touches an existing folder. | 0, or 2 if the folder exists |
| `kit remove [DIR] [--keep-records\|--delete-records]` | Takes out what `init`, `skills` and `hooks` added (see Removing below). | 0 |
| `kit example documents\|data\|analysis DIR [--no-git]` | Creates a small project with one deliberate defect and a README that walks through fail, fix, re-check, verify, accept. | 0, or 2 if `DIR` exists |
| `kit scan [DIR] [--checks]` | Reports first `session_words`, the words the kit adds (or would add) to every Claude Code and Codex session, also as the first line on stderr; then manifests, languages, check commands, CI run lines, docs folders, Git state, what the project has for its agents (`instructions`, `skills`, `plugins`, `bundles`, `hooks`, `memory`, `gates`) and kit state, plus `suggested_checks_toml`. `--checks` prints only the TOML draft. | 0 |
| `kit roles [DIR] --provider claude\|codex [--model TIER=MODEL[:EFFORT]]...` | Writes role files from the [role templates](templates/roles/README.md). Existing files are kept. | 0, or 2 if every file already existed |
| `kit skills [DIR] --provider claude\|codex [--kit PATH]` | Writes `awkit-workflow` (the workflow with the connect procedure) and one skill per situation guide: `.claude/skills/awkit-*/SKILL.md` for Claude Code, `.agents/skills/awkit-*/SKILL.md` for Codex. Each skill holds its guide, with links to other guides turned into skill names, the record templates in `awkit-records`, and the licenses; its description is one line. With `--kit`, or when `DIR/agent-work-kit` exists, the skills point at the guides in that folder instead and `awkit-workflow` is not written. With a method bundle (see Connecting), the planning, review and delegation skills are left out and the command says why. Skills awkit wrote earlier are regenerated; any other file with the same name is kept. | 0, or 2 if every file already existed and was not awkit's |
| `kit hooks [DIR] [--git] [--claude] [--codex] [--remove]` | Writes `rules.toml` when there is none, runs `awkit hook` from `.claude/settings.local.json` and `.codex/hooks.json`, and adds `check commit` to the `commit-msg` hook; `--remove` takes them out (see kit hooks below). | 0 |

`kit scan` reads file names and manifests only. Its commands come in this order: check steps that GitHub Actions already runs (no shell syntax, install steps dropped), then package.json scripts, ruff and mypy settings, pytest when pytest is configured (`[tool.pytest]`, `pytest.ini`, `conftest.py`), Makefile targets, Go and Rust defaults. Equivalent commands appear once. If the draft has no checks, add a real project check before running it. Run the draft with `awkit review check HEAD --config checks.toml` and keep only what works.

### Connecting

`kit init` reads what the project has before adding anything, the same report `kit scan` prints:

- `instructions`: `CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`, `AGENTS.override.md`, `.github/copilot-instructions.md`, `.cursorrules`, `.cursor/rules/*`, `GEMINI.md`, with the agent that reads each, `@path` imports and the words awkit added.
- `skills` and `plugins`: the skill folders of both agents and the plugins enabled in `.claude/settings*.json`. `bundles`: superpowers (a `superpowers` plugin, or three of its skill names such as `brainstorming` and `writing-plans`), get-shit-done (its plugin) and spec-kit (`.specify/`).
- `hooks`: the handlers in `.claude/settings.json`, `.claude/settings.local.json` and `.codex/hooks.json`, the Git hooks folder and its manager (husky, pre-commit, lefthook).
- `memory`: `MEMORY.md`, `.claude/MEMORY.md`, `.beads/`, `.planning/`, `docs/plans/` and Claude Code's automatic memory folder for the project.
- `gates`: kkamak (`gate.json` with `check`, or its plugin), groundtruth (a hook command or skill named so, in the project or `~/.claude`) and cngx (`.cngx/`, or `cngx verify` in CI or a hook).

The section goes at the end of `AGENTS.md` and of `CLAUDE.md` (or `.claude/CLAUDE.md`) unless `CLAUDE.md` imports `AGENTS.md` or is the same file; with neither, init creates `AGENTS.md` with the section and a `CLAUDE.md` that imports it. It sits between `<!-- awkit:begin -->` and `<!-- awkit:end -->`, says to follow the `awkit-workflow` skill (with a bundle: to plan, review and delegate with the bundle and use the workflow for checks and reports), and holds the project profile's five "Start here" fields. Fields the scan can answer point to what the project has (the gate or the CI files, the memory and record locations) instead of copying it. Skills are written for Claude Code when the project has a `CLAUDE.md` or `.claude/`, and for Codex when it has `AGENTS.md`, `.codex/` or `.agents/`; for both when init creates the files. A project with `AGENTS.md` and `.claude/` but no `CLAUDE.md` gets a note: Claude Code sees the kit only through the skill descriptions there.

`session_words` counts the section in each instruction file the agent loads every session and the descriptions of awkit's skills, which agents keep in context to choose a skill; skill bodies load only when used.

What awkit writes: `.awkit/`, the skill files it generated (marked `<!-- awkit:generated`), its section of the instruction files, its handlers in the hook settings and its line or hook in the Git hooks folder. Running `review` and `hook` also adds `.awkit/` to `.git/info/exclude`. Nothing else in the project is written; memory and record files (`MEMORY.md`, `.beads/`, `.planning/`, automatic memory) are only read. `tests/test_connect.py` checks this on every run.

### Removing

`kit init`, `kit skills` and `kit hooks` record every file they write in `.awkit/installed.json`, with a hash of the content before and after and a copy of the original under `.awkit/backup/`. `kit remove` goes through the record: a file still as awkit left it is restored from the copy, or deleted when awkit created it; a file edited since loses only awkit's part (the marked section, the handlers whose command starts with `awkit hook`, the marked Git hook line). Folders awkit created are removed when empty. Without the record, as in another clone, it finds the same parts by their markers. `.awkit/` is deleted, or kept without the record and copies when it holds check runs, accepted versions, the review channel or the hook log: `--keep-records` and `--delete-records` decide, otherwise the command asks, and keeps it without a terminal. The commit `kit init` made stays in the history; commit the removal.

### Three layers

From the three-layer change on, `kit init`, `kit skills` and `kit remove` work as the sections below say; where the table rows above, Connecting or Removing say otherwise (a section in the instruction files, project skills by default, a commit by `init`), these sections apply. The person's computer holds awkit, the guides inside the package and the skills in the user folder. A project commits only `checks.toml`, with its `[kit]` table, and `rules.toml`. The hooks and `.awkit/` stay in the clone, because hooks run code.

### init

`kit init [DIR] [--commit] [--no-git]` installs the project layer and commits nothing unless given `--commit` (see Git tracking).

- `checks.toml`: with none, init writes the draft `kit scan` suggests and the `[kit]` table. An existing file is never rewritten: init appends the table when there is none, or adds the keys the table lacks right after its `[kit]` line. It prints `created`, `added the [kit] table to`, `filled the [kit] table in` or `kept`. A file that does not parse as TOML is left as it is, with a note.
- With no check commands, init warns on both first and repeated installation. An existing empty configuration stays unchanged apart from missing `[kit]` fields; the agent must establish a real check before using `review check`.
- `[kit]` holds four optional keys; `schema` stays 1 and `review check` ignores the table. `version` is the awkit that wrote it, which `doctor` compares with the installed one. `done` is one sentence saying what finishing means in this project, `recipient` who or what receives the result, `records` where the project keeps its state; init fills `records` from the memory and record locations the scan found and leaves `done` and `recipient` empty for the connect procedure.
- Hooks: init runs `awkit kit hooks DIR --git` with `--claude` (for `CLAUDE.md` or `.claude/`) and `--codex` (for `AGENTS.md`, `.codex/` or `.agents/`), both when the project has neither. It prints `running: awkit kit hooks ...` and then that command's own output. A failure becomes a note and init goes on.
- `.awkit/` goes into `.git/info/exclude`. Everything init writes is recorded in `.awkit/installed.json`.
- The project's instruction files get nothing. init prints a line the user can add to `AGENTS.md` or `CLAUDE.md` themselves.
- Outside a Git repository init writes `checks.toml` and the record, skips the hooks and the exclude line, and says to run `git init`. `--no-git` skips the hooks and the exclude line in a repository too.
- Exit 0, or 2 when `checks.toml` already had everything and `.awkit/` was already excluded.

### guide

`kit guide [NAME]` prints a kit file from the installed package on stdout, for an agent without skills and for people. The names are the kit's file names without `.md` (`workflow`, `connect`, `writing`, `korean-writing`, `work-types`, `checking`, `delivery`, `delegation`, `review-session`, `protocol`, `reference`, `failures`, `readme`, `license`, `third-party-notices`), plus `profile` (the long project profile form, `templates/project.md`), `profiles` (the example profiles) and `task`, `review`, `decision` and `checkpoint` (the record templates). Links between kit files are printed as `awkit kit guide NAME`. Without a name it lists the names. An unknown name exits 2 with the list.

### skills

`kit skills [--provider claude|codex] [--without NAMES] [--project] [DIR] [--kit PATH]` writes `awkit-workflow` and one skill per situation guide, for both agents unless `--provider` names one.

- By default the skills go into the user folders, which the agent reads in every project: `~/.claude/skills/awkit-*/SKILL.md` for Claude Code and `~/.agents/skills/awkit-*/SKILL.md` for Codex. Codex reads `$HOME/.agents/skills` as its user scope and still reads the older `$CODEX_HOME/skills`; this is from the Codex source (`codex-rs/ext/skills/src/host_roots.rs` in openai/codex at `2f3fb11`), since its documentation page could not be fetched when this was written.
- Each skill holds its guide and needs nothing outside its folder. Its front matter has only `name` (lowercase letters, digits and hyphens, at most 64 characters, as both agents require) and a one-line `description`. Its first line after the front matter says which awkit made it and how to update it: ``<!-- awkit:generated by awkit VERSION (kit commit C) from GUIDE. Update with `awkit kit skills`. -->``.
- All eight are written by default. `--without delegation,review-session` leaves the named skills out (with or without the `awkit-` prefix, repeatable) and deletes the file awkit wrote for them earlier. Method bundles are not looked for in the user folder.
- Files awkit wrote earlier are regenerated; any other file with the same name is kept. What was written is recorded in `~/.awkit/installed.json`, which `kit remove --user` reads.
- `--project` writes into `DIR/.claude/skills` and `DIR/.agents/skills` instead, leaving out the planning, review and delegation skills when the project has a method bundle. `--kit PATH` implies `--project` and points the skills at a kit folder inside the project; this repository uses `--project --kit kit`.
- Exit 0, or 2 if every file already existed and was not awkit's.

### remove

`kit remove [DIR] [--user] [--project] [--keep-records|--delete-records]` takes out what the kit added.

- `--project`, the default when `--user` is not given, first runs `awkit kit hooks DIR --remove`, which takes out the hooks and `rules.toml`. When that command fails, awkit's hook entries recorded in `.awkit/installed.json` or found by their markers are taken out instead, and a note says so.
- Then every file in the record is restored as Removing describes. A `checks.toml` that init created is deleted when it is unchanged; edited since, it loses only the `[kit]` table, or only the keys init added to an existing table. Without the record, as in another clone, a `[kit]` table under the `# Agent Work Kit:` comment is taken out and the checks stay.
- The `.awkit/` exclude rule goes when that folder is deleted; it stays while the folder is kept for its records. Hook-settings rules added by `kit hooks` are removed with the hooks. Unchanged exclude files are restored byte for byte; later user edits stay.
- `--user` deletes awkit's skills from the user folders, from `~/.awkit/installed.json` (restoring any file that was there before) or by their marker without it, then the record and the folders it emptied. With both flags it does both.
- Exit 0.

### What awkit writes

awkit writes only to these places, and `WRITES` in `src/awkit/connect.py` lists them:

- in the project: `.awkit/`; the `checks.toml` it created, or the `[kit]` table or keys it added to one; the `.awkit/` line in `.git/info/exclude`;
- through `kit hooks`: `rules.toml`, its handlers in `.claude/settings.local.json` and `.codex/hooks.json`, exact local exclude rules for settings files it created, and its line or hook in Git's hooks folder;
- in the user's home folder: `~/.claude/skills/awkit-*/`, `~/.agents/skills/awkit-*/` and `~/.awkit/`.

Memory and record files (`MEMORY.md`, `.beads/`, `.planning/`, Claude Code's automatic memory) and the project's instruction files and own skills are only read. `tests/test_layers.py` runs `kit skills`, `kit init` and `kit remove` with the real `kit hooks` and fails when anything else changes, including the modification time of a read-only file, or when the project and home folder differ from before after removal.

## review

### snapshot

`awkit review [--repo DIR] snapshot FILE...` prints one commit ID: HEAD plus the current content of the named files only. Added and deleted files count when named. The branch, index and working tree are untouched. Directories, links, ignored files and paths outside the repository are refused. Everything already committed in HEAD is in the snapshot; nothing filters secrets. The commit is unreferenced and `git gc` may remove it later. To include every change, tracked and new, in a POSIX shell: `awkit review snapshot $(git diff --name-only --no-renames HEAD; git ls-files --others --exclude-standard)` (paths with spaces need another form).

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
- A step passes when its command exits 0. The runner trusts that exit code: a test that was changed to pass (an assertion removed, a test skipped or deleted, an expected value edited) passes here too. Review the diff of test files separately; `check done` inherits the same limit.
- Worktrees share DBs, ports, sockets and devices. Allocate them per `{run_id}` in the project's commands.

Run folder (default `.awkit/reviews/` in the repository, which `review check` excludes from Git locally when nothing ignores it yet; `--runs-root` puts it elsewhere):

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
| `check commit --message FILE \| --rev REV \| --hook [--history N]` | Reports an author that looks like a coding agent's identity, and compares the author and the trailer keys (`Key: value` lines Git recognizes at the end of the message) with the last N commits (default 50). An author whose email is not among them, or a trailer key none of them use, is reported with how to fix it. A repository without earlier commits passes. Allow a new contributor with `git config --add awkit.allowAuthor EMAIL` and a trailer with `git config --add awkit.allowTrailer KEY`. `--hook` reads a hook event on stdin and checks each `git commit` in its shell command before it runs (see hook). | 0 consistent, 1 not |
| `check writing PATH... [--json]` | Searches Markdown files, and folders recursively, for the patterns in the [Writing Guide](writing.md). Errors: em dashes, a middle dot joining Korean words, `-세요` and `-시오` endings in one document. Warnings: lead-ins, contrasts against a claim nobody made, sales words, Korean stock phrases. Code blocks, blockquotes, inline code, quoted spans and link targets are skipped. Inside a repository a folder means the Markdown files Git tracks or would track there, so ignored folders and other repositories are left out. | 0 no errors, 1 errors |
| `check done [--session ID] [--mark] [--runs-root DIR] [--hook]` | `--mark` records the current state (HEAD plus every working-tree change and non-ignored untracked file, excluding `.awkit/` runtime state) as the session's starting point in `.awkit/done/`. User settings follow Git's tracked and ignored paths. Without it: passes when nothing changed since that point (or since HEAD when none was recorded), or when a passing `review check` run checked exactly the current state; otherwise lists the changed files. Runs are looked up in `--runs-root`, `.awkit/reviews` and the system temp folder older versions used. | 0 yes, 1 no |

The text summaries state their scope. Writing checks complete files and does not classify findings as existing or introduced; it does not inspect content or rendering. Done matches repository states, not task ownership or check coverage: a task-only snapshot can pass while other changes keep the repository state unmatched. An unchanged state establishes no verification. A matching passing run establishes success of its configured commands, not document review. Exit codes and JSON fields do not change with these explanations.

With `--hook`, `check done` reads the Claude Code hook input from stdin: SessionStart marks the starting point (a resumed or compacted session keeps the one it has), Stop exits 2 with the reason on stderr so the agent continues, and a second stop in the same turn (`stop_hook_active`) passes, so the agent can report work it could not check and say why.

## hook

`awkit hook [EVENT] [--root DIR] [--kit-rules] [--skip RULE]... [--kit-hooks]` is the command Claude Code and Codex run on hook events. `kit hooks` registers one handler per event, `awkit hook <EVENT> --kit-hooks`; `EVENT` is SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop or SubagentStop and is used when the input does not name its event, and `--kit-hooks` only marks the handler as one `kit hooks` added. It reads the event JSON on stdin, applies the rules in `rules.toml` and prints the decision JSON on stdout, or nothing. It always exits 0. The project root is the nearest folder at or above the event's `cwd` that has `rules.toml`. `--kit-rules` applies the kit's default rules when the project has none, with `{kit}` naming a kit folder in the project or else the installed kit; `--skip` leaves out a rule by name.

Both agents send the same input fields (`hook_event_name`, `tool_name`, `tool_input`, `cwd`, `session_id`, `transcript_path`; `prompt` on UserPromptSubmit; `stop_hook_active` and `last_assistant_message` on Stop) and read the same output: on PreToolUse `hookSpecificOutput.permissionDecision` (`allow`, `deny`, `ask`) with `permissionDecisionReason` and `additionalContext`; on UserPromptSubmit, PostToolUse and Stop `decision: block` with `reason`, or `hookSpecificOutput.additionalContext`. Codex's schemas are in `codex-rs/hooks/schema/generated/` of the `openai/codex` repository. What differs is handled in one place: Codex edits files with `apply_patch` and starts subagents with `spawn_agent`, which match rules for `Edit`, `Write` and `Agent`, and the two keep their hook files in different places (see kit hooks).

- Quiet by default: nothing fired prints nothing. A rule that cannot be judged allows the call.
- Once per session: an `inject` rule adds its line once, and a `verify` rule on Stop or SubagentStop blocks once; the session's state is `.awkit/hooks/SESSION.json`. A second stop in the same turn (`stop_hook_active`) skips `block` and `verify` rules, so the agent can report what it could not fix. A `verify` rule on other events blocks once per distinct output.
- Messages: a rule's `message` is at most 200 characters as written (before `{kit}` is filled in) and ends with what to do. Every reason and context starts with `awkit NAME (ENTRIES): `; a block also ends with `(KIT/failures.md: ENTRIES)`, so the entry stays in view after a long command output. Several firings on one event are joined, and `deny` wins over `ask`.
- Errors allow the call and leave one log line: unreadable input, an unreadable rules file (no rule runs), a wrong rule (only that rule is skipped; reported once per session), a command that runs past its timeout (its process tree is stopped) or cannot start. Without `rules.toml` and `--kit-rules`, a project that has `.awkit/` gets one log line per session; a folder without `.awkit/` gets nothing written.
- Files: awkit writes only `.awkit/`: the session state and the log `.awkit/hooks.ndjson`, one line per firing or error with `time`, `session`, `event`, `tool`, `rule` and `decision` (`deny`, `ask`, `block`, `context`, `error`). `.awkit/` is excluded from Git locally when the runner creates it. Transcripts and memory files are only read.

`awkit hook report [DIR] [--json]` prints per session how often rules fired, blocked (`deny` and `block`), asked, injected and failed, with counts per rule, and any problems in `rules.toml`.

`awkit hook reply [--hangul N]` and `awkit hook kit-version` are the commands behind the default `writing-reply` and `kit-version` rules. Each reads the event on stdin, prints a line and exits 1 when its rule should fire, and otherwise prints nothing and exits 0.

- `reply` takes the final reply from `last_assistant_message`, or else from the transcript. It fires when the reply has more than N Hangul syllables (default 500), a Markdown heading outside code blocks or a turn whose request asked for a prompt, instructions or a document, and when no tool call in the session read the writing guide (a `writing.md` or `korean-writing.md` path, the `awkit-writing` skill, or a `/awkit-writing` command). Its output lists what `awkit check writing` finds in the reply. Without a readable transcript it passes.
- `kit-version` fires when `checks.toml` has a `version` key in its `[kit]` table that differs from the installed awkit's version. Without the key it prints nothing.

Transcripts, as the two agents document and write them: Claude Code passes `transcript_path` on every event, a JSON lines file under `~/.claude/projects/`; `user` and `assistant` records carry `message.content` with `text` and `tool_use` blocks, and the file may lag the current turn, so the documentation points hooks to `last_assistant_message` on Stop. Codex passes `transcript_path`, which may be null, and `last_assistant_message` on Stop; its rollout file has `response_item` records (`message`, `function_call`, `custom_tool_call`, `local_shell_call`) and `event_msg` records (`user_message`, `agent_message`).

`check commit --hook` is the command behind the `commit-identity` rule. It reads the message from `-m`, `--message`, `-F` (a file, or `-` with a heredoc) and `$(cat <<'EOF' ...)` substitutions, and the author from `--author`, `GIT_AUTHOR_*` assignments before `git`, `-c user.*` or Git's configuration. The repository is the event's `cwd` moved by `cd` commands earlier in the same command line and by `git -C`. The body of a heredoc that feeds a program, such as a script for `python3 - <<'EOF'`, is input and never read as commands. A command it cannot split, such as one with an unclosed quote, passes.

## Rule format

`rules.toml` at the project root declares the rules. The kit's default rules are `rules.toml` and `rules-session.toml` in the kit; the second holds only `[[rules]]` tables, and `kit hooks` writes both into one file.

```toml
schema = 1
kit = "agent-work-kit"        # {kit} in messages and commands
timeout_seconds = 20          # default for each rule command, at most 600

[[rules]]
name = "commit-identity"      # letters, digits, . _ -
prevents = ["F9"]             # entries in failures.md, cited in every message
kind = "block"                # block, verify or inject
events = ["PreToolUse"]
tools = ["Bash"]              # tool names; * and ? allowed
shell = '\bgit\b[^\n]*\bcommit\b'   # regular expression searched in the shell command
command = ["{python}", "-m", "awkit", "check", "commit", "--hook"]
# also: paths = ["*.md"], text = '[가-힣]', prompt = '문서', message = "...", decision = "ask", timeout = 10
```

| Kind | Events (default first) | Fires | Output |
|---|---|---|---|
| `block` | PreToolUse, UserPromptSubmit, PostToolUse, Stop, SubagentStop | The conditions match and, with `command`, the command fails | PreToolUse: `permissionDecision` `deny` (or `ask` with `decision = "ask"`) and the reason; other events: `decision: block` |
| `verify` | Stop, PostToolUse, PreToolUse, UserPromptSubmit, SubagentStop, SessionStart | The command fails; on Stop once per session, elsewhere once per distinct output | `decision: block` with the message and the output; on SessionStart, `additionalContext` |
| `inject` | PreToolUse, PostToolUse, UserPromptSubmit, SessionStart | The conditions match and, with `command`, the command fails; once per session | `additionalContext` |

- Conditions: every condition given must match. `events` and `tools` name the event and the tool; `tools` also matches Codex's `apply_patch` as `Edit` and `Write`, `spawn_agent` and Claude Code's `Task` as `Agent`. `shell` is a regular expression searched in `tool_input.command`, leaving out the body of a heredoc fed to a program (a file being written is not a command). `paths` are globs for the edited files (`file_path`, `notebook_path`, or the file headers of an `apply_patch` patch); a pattern without `/` matches the file name in any folder. `text` searches the text being written (`content`, `new_string`, `edits`, `new_source`, added patch lines). `prompt` searches the user's message on UserPromptSubmit, without pasted material marked `<pasted_content>`, and only `inject` rules may use it: the situation is judged from tool calls, and the user's words only add a line.
- `command`: for a rule these conditions cannot express. An argument array, never a shell, run in the project root with the event JSON on stdin. Placeholders: `{python}` (the interpreter running awkit), `{kit}`, `{root}`, and an element `{paths}` that becomes the matching edited files that exist (the rule is skipped when none does). Exit 0 with no output is no opinion; exit 0 with a JSON object `{"decision": "deny"|"ask"|"block"|"allow", "reason": TEXT, "context": TEXT}` is that decision; any other exit fires the rule with the output (stdout and stderr, first 1,000 characters).

The default rules, each with the entries it guards:

| Rule | Kind, event | Fires on | Entries |
|---|---|---|---|
| `commit-identity` | block, PreToolUse | `git commit` with an author or trailers the history does not have (`check commit --hook`) | F9 |
| `done-check` | verify, SessionStart and Stop | changed files without a passing check of their current state (`check done --hook`) | F1 |
| `writing-check` | verify, PostToolUse | an edited Markdown file with writing errors (`check writing`) | F13, F14, F32 |
| `korean-writing` | inject, PreToolUse | the first Markdown edit with Korean text | F14 |
| `writing-request` | inject, UserPromptSubmit | the first request for a prompt, instructions, a document or a report | F14 |
| `writing-reply` | verify, Stop | a final reply that is a long Korean document written without the guide (`hook reply`) | F14 |
| `research` | inject, PreToolUse | the first web search or fetch | F23, F37 |
| `delivery` | inject, PreToolUse | `git push`, a release or an upload command | F24 |
| `delegation` | inject, PreToolUse | starting a subagent | F19, F21 |
| `kit-version` | inject, SessionStart | `[kit] version` in `checks.toml` other than the installed awkit (`hook kit-version`) | F25 |

## kit hooks

`awkit kit hooks [DIR] [--git] [--claude] [--codex]` connects the hook runner to the project at the repository's top folder (or `DIR` outside a repository). Without a choice it does all three; each choice limits it to that part. Every part also writes `rules.toml` when there is none.

- `rules.toml`: the kit's default rules, starting with the line `# Written by \`awkit kit hooks\``, with `kit` set to a kit folder in the project or the installed kit.
- `--claude`: a handler `awkit hook <EVENT> --kit-hooks` for SessionStart, UserPromptSubmit, PreToolUse, PostToolUse and Stop in `.claude/settings.local.json`. An event that already runs `awkit hook` there or in `.claude/settings.json` gets no second handler.
- `--codex`: the same handlers in `.codex/hooks.json`, Codex's project hook file. Codex loads the project's `.codex/` layer only for a trusted project, and runs a hook from it only after the person approves it under `/hooks`; changing a handler's command asks again. The handler settings may carry `timeout`, `statusMessage`, `commandWindows` and `additionalContextLimit` (tokens before Codex moves a hook's `additionalContext` to a file, 2,500 by default); awkit generates commands without shell operators so they also parse in Windows PowerShell 5.1. A missing executable is reported as a launch failure; run `pipx ensurepath` and restart the app that runs hooks after installing. Reinstalling hooks upgrades exact commands generated by earlier awkit versions and preserves custom commands.
- `--git`: `check commit` in the repository's `commit-msg` hook: a new hook, or one line after the commands of an existing hook (before its last line when that line is `exit` or `exec`). With husky the line goes into `.husky/commit-msg`; with pre-commit into `commit-msg.legacy`. It prints `connected:` with the file when it added to an existing hook.

Handlers and lines carry awkit's markers (`--kit-hooks`, `# awkit: commit identity check`). Existing handlers, keys, indentation and line endings stay as they were. When the project has a completion gate (`kit scan`), the handlers add `--skip done-check` and the command says why. Nothing goes into the user's own folders: hooks run code, so they run only in a project that chose awkit. Running it again changes nothing. It prints `installed`, `connected`, `kept existing hook` per file and `note:` lines, and exits 0.

Settings files this install created get exact root-relative rules in `.git/info/exclude`, keeping them out of ordinary commit candidates. Pre-existing files, tracked files and unrelated settings keep their Git treatment. Reinstallation repairs missing rules for files recorded as created. `check done` therefore agrees with the documented snapshot recipe without filtering settings by name.

What it writes is recorded in `.awkit/kit-hooks.json`, with a copy of each file it changed under `.awkit/kit-hooks/`. It reads no other install state. `kit hooks --remove` takes it out: a file still as it was written is restored from the copy, or deleted when `kit hooks` created it; a file changed since loses only the marked handlers or line. An edited generated Git hook is kept if its original block cannot be identified. Without the record, as in another clone, it finds the same parts by their markers. `rules.toml` is deleted while unchanged; a changed one is deleted only when the person at the terminal agrees, and kept without a terminal. Settings exclude rules are removed even when check records remain; user-added or edited rules stay. Folders it created go when empty, and `.awkit/` when it created it and nothing else is there.

## Optional rules

Rules the default bundle leaves out, to add to `rules.toml` where they fit.

A model reads the reply against the guide. The default `writing-reply` rule judges by length, shape and the session's use of the guide, which a script can see. A project that wants the writing itself judged can let a small model read the final reply and the guide; it costs a model call at every stop, so it is not a default:

```toml
[[rules]]
name = "writing-review"
prevents = ["F13", "F14"]
kind = "verify"
events = ["Stop"]
timeout = 120
command = ["{python}", "scripts/review_reply.py", "{kit}/writing.md", "{kit}/korean-writing.md"]
message = "A reviewer model found writing the guide removes. Revise the reply and read it once more before sending."
```

`scripts/review_reply.py` is the project's own: it reads the event on stdin, takes `last_assistant_message`, sends it with the two guides to a small model (for example with `claude -p --model haiku` or the API), and exits 1 with the model's findings, or 0 when there are none.

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
