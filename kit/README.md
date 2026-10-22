# Agent Work Kit

Instructions and templates for an agent working in this project. Start with [Agent Instructions](templates/agent-instructions.md); it says what to read for each task. If the [project profile](templates/project.md) is still empty, follow its "Connect the kit to a project" section first.

| File | Read when |
|---|---|
| [templates/agent-instructions.md](templates/agent-instructions.md) | Every session |
| [templates/project.md](templates/project.md) | Every session, once filled in |
| [workflow.md](workflow.md), [protocol.md](protocol.md) | Doing development work or keeping task records |
| [work-types.md](work-types.md) | Research, writing, data, environment setup, operating an application, learning, automation |
| [korean-writing.md](korean-writing.md) | Writing Korean text for people |
| [delegation.md](delegation.md), [templates/roles/](templates/roles/README.md) | Splitting work across subagents |
| [review-session.md](review-session.md) | A separate session reviews the work |
| [reference.md](reference.md) | Running an `awkit` command and needing its formats, rules or exit codes |
| [examples/project-profiles.md](examples/project-profiles.md) | Filling the profile for a kind of project you have not set up before |
| templates/task.md, review.md, decision.md, checkpoint.md | Copy into the project's record location when the task needs that record |

The project's own rules and the user's current instructions take precedence over this kit. Nothing here authorizes data access, agent calls, publication or deployment.

To update the kit, never overwrite this folder: it holds the filled-in profile and task records. Install the new version beside it with `awkit kit init --name agent-work-kit-new`, compare, and carry over only the changes needed.

The kit is MIT licensed ([LICENSE.md](LICENSE.md)). The Korean writing guide adapts third-party material; keep [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) when redistributing.
