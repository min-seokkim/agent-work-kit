# Changelog

Behavior changes per version. Items to check when moving from an earlier version are listed under "Incompatible changes". The version is not raised per commit; changes until the next release are added to the unreleased section at the top.

## 0.3.0 (unreleased)

Planned as the first public release. 0.2.0 existed only as the version in the source and was never tagged or released. From 0.3.0 the package goes to PyPI and GitHub releases, once the release conditions in [docs/development.md](docs/development.md#release) are met. Changes until then are added here.

### Incompatible changes

- CLI help and error messages changed from Korean to English. Scripts that read message text should check exit codes instead; their meaning is unchanged.
- `awkit usage --json` uses result format 2: unmeasured token fields are `null` instead of `0`, and the result carries `format` and `total.complete`.
- `awkit review` resolves file names, step `cwd` and `artifacts` patterns relative to the folder it runs in. Run from the repository root it behaves as before; from a subfolder, the same subfolder of the worktree is the base, recorded as `subdir` in results and manifests.
- `awkit kit init` and `awkit kit example` commit the folder they create, creating the repository with `core.autocrlf=false` when there is none. Use `--no-git` to only copy.
- People-facing documentation is now the two READMEs only. The command documentation moved to `kit/reference.md` (English, shipped with the kit), and the development documents under `docs/` were merged into `docs/development.md`.

### Added

- `awkit kit example documents|data|analysis`: first-run examples with one deliberate defect.
- `awkit kit scan`: reports a project's manifests, the checks its CI runs, docs folders and Git state, and drafts a check configuration.
- `artifacts` and `required_artifacts` in `awkit review check`: checked outputs retained with hashes in the run folder.
- `awkit review verify`, `accept` and `compare`: re-check retained outputs, keep an accepted version and compare later runs with it.
- `awkit review check HEAD`: check the current commit without its full ID.
- `awkit usage`: user messages, commands and minutes per thread.
- `awkit pipeline`: one-way deliveries (submissions, uploads) without `backup` and `rollback`.
- Kit: work-type completion evidence (`work-types.md`), the "Connect the kit to a project" procedure in the agent instructions, and the command reference.
- Kit: `writing.md`, a writing guide for any language covering the reader, the preservation list, plain style, corrections and the completion check. `korean-writing.md` keeps only what is specific to Korean and is used together with it. The project profile gains a field for per-document requirements.

- `awkit check commit`, `check writing` and `check done`: the author and trailers of a commit compared with the repository's history, the writing patterns from the kit's writing guides found in Markdown files, and a done check that requires a passing `review check` of the current state for files changed in the session. `awkit kit hooks` installs them as a Git `commit-msg` hook and as Claude Code SessionStart and Stop hooks.

### Fixed

- `awkit review` no longer creates a repository in an untracked folder and commits every file in it, `.env` included; such folders are refused.
- An example created inside a repository that already had commits was not committed, so the first command in its README could not find its script.
- Adding the kit to a repository with staged changes no longer bundles those changes into the kit's commit.
- `awkit usage` no longer counts notices, command output and interruption markers as user messages.
- `awkit kit scan` no longer suggests pytest for a bare `tests` folder and puts the checks CI already runs first.
- Two concurrent `awkit review accept` runs could mix accepted versions; a lock prevents it.
- Some tests failed when run from the repository root with `PYTHONPATH=src`.
