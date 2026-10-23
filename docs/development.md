# Development

Start here when developing Agent Work Kit. This file owns the current-state summary and routes readers to each topic's source. Read the linked document when its task applies. The [roadmap](roadmap.md) lists remaining work; the owner decides what to build before implementation.

## Document map

<a id="scope"></a>
<a id="decisions"></a>
<a id="next-work"></a>
<a id="independent-session-collaboration-plan"></a>
<a id="current-local-collaboration-trial"></a>
<a id="using-awkit-in-the-coordinator-session"></a>
<a id="measurement-record"></a>
<a id="release"></a>
<a id="testing-and-building"></a>
<a id="verification-record"></a>

| Document | Owns | Read or update when |
|---|---|---|
| [Design](design.md) | Scope and accepted decisions | Changing architecture or adding capabilities |
| [Roadmap](roadmap.md) | Remaining work, prerequisites and completion criteria | Choosing the next task |
| [Task plans and records](roadmap.md#task-plans) | Detailed plans, owners, progress and handoffs | Starting or resuming a specific task |
| [Evidence](evidence.md) | Completed milestones, measurements and verification limits | Assessing results or recording a check |
| [Release](release.md) | Test, build and release procedures | Verifying or publishing a version |
| [CHANGELOG](../CHANGELOG.md) | Changes users need when updating | Changing behavior |

Update the document that owns the information and link to it from other documents. Move completed roadmap items into a task or evidence record, keeping their identifiers and unresolved limits. Older section links to this file land at this map.

## Rules for working in this repository

The working rules (commit identity, versions, dates, documentation audience, writing style, kit length) are in [AGENTS.md](../AGENTS.md) at the repository root, where coding agents read them automatically. `CLAUDE.md` imports it for Claude Code.

The READMEs address people. The shipped [command reference](../kit/reference.md) defines CLI behavior, and the [failure catalogue](../kit/failures.md) records what the kit prevents.

## Current state

| Area | State |
|---|---|
| Kit | Baseline workflow (`workflow.md`) and project profile read every session; situation guides read on trigger, written as Claude Code and Codex skills in the user folders by `awkit kit skills` and printed by `awkit kit guide`: connecting the kit, writing (with a Korean supplement), work types, checking, delivery, delegation with five role templates, review sessions, task records. Record templates and the command reference. |
| `kit` commands | `init` installs the project layer without committing: `checks.toml` with the `[kit]` table, the hooks through `kit hooks`, `.awkit/` excluded, `.awkit/installed.json`; `--copy` copies the folder as before. `skills` writes the user folders (`--project` for a project), `guide` prints a guide, `remove` takes out the project layer (`--project`) or the user folder (`--user`). `scan` reports the words the kit adds to every session first, then what the project has for its agents (instructions, skills and bundles, hooks, memory, completion gates), manifests, CI checks, docs and Git state, and drafts `checks.toml`. `example` (documents, data, analysis) commits only the folder it creates; `roles` writes Claude Code or Codex role files. |
| Setup | `install.ps1` and `install.sh` run `awkit kit skills` and `awkit doctor` after installing. Doctor checks Git identity, skills, kit version, hook configuration and copied kit folders. It reports the loaded code's origin and validates existing check configuration without executing it. [Connection diagnostics](tasks/connection-diagnostics.md) records the cases and verification limits. This repository is developed with its own kit (AGENTS.md). |
| `check` | `commit` (author and trailers against history, also on a `git commit` command before it runs), `writing` (patterns from the writing guides), `writing-compare` (findings at explicit frozen revisions, with conservative occurrence correspondence and complete-file policy preserved), `done` (changed files need a passing check of their current state); `kit hooks` adds the check to the project's commit-msg hook (after its own commands, through husky or pre-commit's legacy hook) and a handler running `awkit hook` beside the project's own, keeping each settings file's format, and leaves out the done check when the project has a completion gate. |
| `hook` | One runner for Claude Code and Codex hooks: `block`, `verify` and `inject` rules from `rules.toml`, matched on event, tool, shell command, edited paths and text; a log of every firing and `hook report`. The kit's example rules (`kit/rules.toml`) cover commit identity, the done check, the writing check and one line each for Korean text, research, delivery and delegation; this repository uses them from `rules.toml`, and a project without one gets them through `--kit-rules`. The commit rule follows `cd` and skips heredoc bodies fed to a program. Local Codex SessionStart and writing-request execution were observed after restarting the client; see the [trial record](tasks/local-collaboration.md#after-restarting-the-local-client) for the evidence and limits. |
| `review` | `snapshot`, `check` (isolated worktree, setup and checks, artifacts with hashes, paths relative to the run folder), `verify`, `accept` (locked), `compare` (with a note for worktree-only outputs). Refuses untracked folders. |
| `channel` | SQLite message log between `main` and `reviewer`: requests, replies, rebuttals, waits, close. One session per role. |
| `usage` | Claude Code and Codex logs; format 3 from `7977b35` separates token/log completeness from human-input coverage. Modern human observations remain visible; uncertain exact counts are `null`, with representation counts and reasons. Codex calls retain model-bearing context-row counts, not unique turns or API calls. The [compatibility record](tasks/usage-log-compatibility.md) identifies tested cases and remaining client/identity limits. Delivered through `31a1599` with Windows/Linux CI; final environment receipts are linked from the task record. |
| Extras | `pipeline` (delivery commands, verification of the running release, rollback history, reconcile, optional backup and rollback), `publish` (static site with link checks and atomic switch), `ui` (multi-width captures with overflow checks). Mock examples only. |
| Version | 0.3.0, unreleased. No tag or release exists. |

The [proposal trial](tasks/workflow-review.md) delivered local commit `89549b7`: writing and done summaries clarify scope, and reporting guidance separates commands, reading and omitted reviews. The existing-error blocking policy remains unchanged, and the automatic Stop-hook failure remains unresolved. The [roadmap follow-up](roadmap.md#follow-up-from-the-document-trial) connects those findings and reported small-edit overhead to bounded planning work; the broader document and collaboration workflows remain planned.

The [planning and implementation trial](tasks/planning-implementation.md) delivered corrections for usage coverage, guide-access evidence, fresh-install Python selection, bundled hook execution errors and collaboration waiting. The bundled protocol preserves custom command behavior and requires deliberate migration of existing project rule copies after a capability check. The expanded CI includes Python 3.14 on Windows and Linux. All 17 Windows/Linux CI jobs passed for `31a1599`; the task record owns the accepted snapshots, final environment receipts and remaining scope.

The [writing-comparison task](tasks/writing-comparison.md) owns the new report's contract, candidate verification and delivery state. It follows the separately accepted [scoped document trial](tasks/scoped-document-trial.md), which exercised partial-edit evidence reuse and explicit reporting of missing review. Neither establishes a measured productivity gain or intended-reader acceptance.
