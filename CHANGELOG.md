# Changelog

Behavior changes per version. Items to check when moving from an earlier version are listed under "Incompatible changes". The version is not raised per commit; changes until the next release are added to the unreleased section at the top.

## 0.3.0 (unreleased)

Planned as the first public release. 0.2.0 existed only as the version in the source and was never tagged or released. From 0.3.0 the package goes to PyPI and GitHub releases, once the release conditions in [docs/development.md](docs/development.md#release) are met. Changes until then are added here.

### Incompatible changes

- `awkit kit skills` without `--kit` and without an `agent-work-kit` folder writes skills that hold the guides instead of pointing at a kit folder, and adds `awkit-workflow`. Descriptions are one line. Skills awkit wrote earlier are regenerated instead of kept. With a method bundle such as superpowers in the project, `awkit-work-types`, `awkit-delegation`, `awkit-review-session` and `awkit-records` are left out.
- `awkit kit hooks --claude` writes `awkit hook` entries for every hook event to `.claude/settings.json`, which can be committed, and writes `rules.toml` when there is none; it no longer writes the done check to `.claude/settings.local.json` and removes the entries earlier versions put there. `--codex` writes the same to `.codex/hooks.json`.
- CLI help and error messages changed from Korean to English. Scripts that read message text should check exit codes instead; their meaning is unchanged.
- `awkit usage --json` uses result format 2: unmeasured token fields are `null` instead of `0`, and the result carries `format` and `total.complete`.
- `awkit review` resolves file names, step `cwd` and `artifacts` patterns relative to the folder it runs in. Run from the repository root it behaves as before; from a subfolder, the same subfolder of the worktree is the base, recorded as `subdir` in results and manifests.
- `awkit kit init` and `awkit kit example` commit the folder they create, creating the repository with `core.autocrlf=false` when there is none. Use `--no-git` to only copy.
- The kit is a baseline workflow plus situation guides. `templates/agent-instructions.md` is gone: `workflow.md` is the baseline read every session, and the connect procedure, check setup and delivery have their own guides (`connect.md`, `checking.md`, `delivery.md`). Instructions that pointed agents at the old file should point at `agent-work-kit/README.md`.
- The web extras moved to the `awkit.extras` package (`awkit.extras.pipeline`, `awkit.extras.publish`, `awkit.extras.ui`); the commands are unchanged.
- People-facing documentation is now the two READMEs only. The command documentation moved to `kit/reference.md` (English, shipped with the kit), and the development documents under `docs/` were merged into `docs/development.md`.

### Added

- `awkit hook`: one command for Claude Code and Codex hooks that applies the rules in the project's `rules.toml`. A rule blocks a tool call, verifies the result with a command and blocks once with its output, or injects one line of guidance once per session, matched on the event, the tool, the shell command, the edited paths and the text written. Every firing and error goes to `.awkit/hooks.ndjson`; `awkit hook report` counts them per session. Failures allow the call. The kit's example `rules.toml` checks commit identity before `git commit`, the done check when the agent stops and the writing check after a Markdown edit, and gives one line of guidance for Korean text, research, delivery and delegation. Each rule names the failure entries it guards, and the guard table in `kit/failures.md` lists them.
- `awkit check commit --hook`: the commit identity check on a `git commit` command before it runs.
- `awkit kit example documents|data|analysis`: first-run examples with one deliberate defect.
- `awkit kit scan`: reports a project's manifests, the checks its CI runs, docs folders and Git state, and drafts a check configuration.
- `artifacts` and `required_artifacts` in `awkit review check`: checked outputs retained with hashes in the run folder.
- `awkit review verify`, `accept` and `compare`: re-check retained outputs, keep an accepted version and compare later runs with it.
- `awkit review check HEAD`: check the current commit without its full ID.
- `awkit usage`: user messages, commands and minutes per thread.
- `awkit pipeline`: one-way deliveries (submissions, uploads) without `backup` and `rollback`.
- Kit: work-type completion evidence (`work-types.md`), the "Connect the kit to a project" procedure in the agent instructions, and the command reference.
- Kit: `writing.md`, a writing guide for any language covering the reader, the preservation list, plain style, corrections and the completion check. `korean-writing.md` keeps only what is specific to Korean and is used together with it. The project profile gains a field for per-document requirements.

- `install.ps1` and `install.sh`: install Git and Python when missing (winget, Homebrew), then awkit with pipx, then run `awkit doctor`.
- `awkit doctor`: checks Python, Git, the Git identity, PATH and the project folder, and prints how to fix each missing item.
- Another Git repository inside the project, such as a clone of awkit, is reported by `awkit doctor` and `awkit kit scan` and fails `awkit check done` with how to fix it; such repositories are not supported. `awkit check writing` reads only the Markdown files Git tracks or would track.
- `awkit kit init` writes `VERSION.txt` into the kit folder: the awkit version, and for a kit copied from a source checkout its commit and whether `kit/` had uncommitted changes. `awkit doctor` warns when it differs from the installed awkit.
- Kit: `failures.md`, the catalogue of agent failures the kit guards against, with a generated table of which guide section and which `awkit` command guards each entry. Each guide section ends with a `Prevents:` line naming its entries. It is a reference, not read every session.
- `awkit kit skills --provider claude|codex`: one skill per situation guide, so a guide loads when its situation arises.
- `awkit check commit`, `check writing` and `check done`: the author and trailers of a commit compared with the repository's history, the writing patterns from the kit's writing guides found in Markdown files, and a done check that requires a passing `review check` of the current state for files changed in the session. `awkit kit hooks` installs them as a Git `commit-msg` hook and as Claude Code SessionStart and Stop hooks.

### Fixed

- The `commit-identity` hook rule judged a commit made after `cd` into another repository by the session's repository, and read the body of a heredoc fed to a program (a Python script holding a `git commit` string) as commands. It follows `cd` and skips such heredoc bodies.
- `awkit doctor` passed a coding agent's Git identity such as `Claude <noreply@anthropic.com>` as fine. It now checks the configured identity against the repository's history, and `kit init` and `kit example` commit into a repository with history only as an identity that fits it, skipping the commit with the reason otherwise.
- The hooks from `awkit kit hooks` named the Python interpreter awkit was installed with and broke when that environment moved; they call `awkit` by name.
- `awkit check done` counted `.claude/settings.local.json`, which `kit hooks --claude` writes, as unchecked work and blocked every turn. Files local to the machine are left out, and the file is excluded from Git locally.
- `awkit review check` kept run folders in the system temp folder by default, outside the project; the default is now `.awkit/reviews` in the repository, excluded from Git locally.
- `awkit review snapshot` refused a file removed with `git rm` or moved away with `git mv`, since it looked for the file in the index; it now also accepts a file HEAD has.
- `awkit usage` did not count messages typed while a turn was running, which Claude Code records only as queued-command attachments.

- `awkit review` no longer creates a repository in an untracked folder and commits every file in it, `.env` included; such folders are refused.
- An example created inside a repository that already had commits was not committed, so the first command in its README could not find its script.
- Adding the kit to a repository with staged changes no longer bundles those changes into the kit's commit.
- `awkit usage` no longer counts notices, command output and interruption markers as user messages.
- `awkit kit scan` no longer suggests pytest for a bare `tests` folder and puts the checks CI already runs first.
- Two concurrent `awkit review accept` runs could mix accepted versions; a lock prevents it.
- Some tests failed when run from the repository root with `PYTHONPATH=src`.
