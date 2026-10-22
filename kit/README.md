# Agent Work Kit

Instructions and templates for an agent working in this project. The project's own instructions and the user's current request take precedence over this kit. Nothing here authorizes data access, agent calls, publication or deployment.

Every session, read [workflow.md](workflow.md), the baseline way of working, and the [project profile](templates/project.md). If the profile is still empty, [connect the kit](connect.md) first.

Read a situation guide when its situation arises. `awkit kit skills --provider claude` or `--provider codex` writes each one as a skill, so the agent loads it on its own.

| Guide | Situation | Skill |
|---|---|---|
| [connect.md](connect.md) | The kit was just added or the project profile is still empty | none; workflow.md points here |
| [writing.md](writing.md), [korean-writing.md](korean-writing.md) | Writing or revising text people read, including UI text, CLI output and commit messages | `awkit-writing` |
| [work-types.md](work-types.md) | Work that is not a code change: research, data, environment setup and troubleshooting, operating an application, learning, automation | `awkit-work-types` |
| [checking.md](checking.md) | Setting up checks, shared resources such as databases and devices, results that are hard to interpret | `awkit-checking` |
| [delivery.md](delivery.md) | Handing over, submitting, publishing or deploying a result | `awkit-delivery` |
| [delegation.md](delegation.md), [templates/roles/](templates/roles/README.md) | Splitting work across subagents, choosing models, writing handoffs | `awkit-delegation` |
| [review-session.md](review-session.md) | A separate session reviews the work | `awkit-review-session` |
| [protocol.md](protocol.md) | Task records, states, review and decision records, resuming another session's work | `awkit-records` |

Look up commands, formats and exit codes in [reference.md](reference.md). The failures each guide section and command guards against are in [failures.md](failures.md); read an entry when a guard names it, not every session. Copy the record templates (templates/task.md, review.md, decision.md, checkpoint.md) into the project's record location when a task needs them. [Example profiles](examples/project-profiles.md) show filled profiles for several kinds of project.

To update the kit, never overwrite this folder: it holds the filled-in profile and task records. Install the new version beside it with `awkit kit init --name agent-work-kit-new`, compare the two `VERSION.txt` files and the guides, and carry over only the changes needed.

The kit is MIT licensed ([LICENSE.md](LICENSE.md)). The writing guides adapt third-party material; keep [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) when redistributing.
