# Connect the Kit to a Project

Use this once, after `awkit kit init`, while the [project profile](templates/project.md) is still empty. In a project connected by `kit init` the profile is the Agent Work Kit section at the end of `AGENTS.md` or `CLAUDE.md`; with a copied kit folder (`kit init --copy`) it is `templates/project.md` in that folder. Connecting fills the profile with pointers to what the project already has and sets up checks from commands the project already runs. [Example profiles](examples/project-profiles.md) show filled profiles for several kinds of project.

Read before adding anything. Run `awkit kit scan` in the project folder. Its first line is the number of words the kit adds to every session. The report lists the project's instruction files, skills and method bundles, hooks, memory and record locations, completion gates, manifests, the commands CI already runs and the Git state, and drafts a `checks.toml`. Treat every suggested command as unverified: the scan reads file names and manifests, not behavior.

Then do the following, and record each result rather than assuming it:

1. Fill the empty profile fields from the scan and from one question to the user: what counts as done for this project, and who or what receives the result. Point to where the project already states a command, convention or decision (a section of its instructions, a CI file, a Makefile) instead of copying it: a copy goes out of date and doubles what agents read every session. Do not invent a build or deployment step the project does not have.
2. Keep state where the project keeps it. When the scan lists a tracker, a memory file or a planning folder, task state, decisions and checkpoints go there; the record templates in [task records](protocol.md) are for a project without one. Do not write to memory that the agent's own tools manage, such as Claude Code's automatic memory.
3. Write `checks.toml` from the commands the scan found, run `awkit review check HEAD --config checks.toml` once, and keep only the commands that actually run here. List the files a passing run must produce under `artifacts` and `required_artifacts`. When the project has a completion gate, use the gate's check command here too, so the gate and `awkit review check` judge the same thing.
4. Record the delivery stages the project really uses (build, test, install, submit, accept, verify in use) in the profile; [Delivery](delivery.md) says what each needs.
5. Offer the user the hooks from `awkit kit hooks`. `--git` adds the commit identity check to the commit-msg hook, after any hook the project has. `--claude` or `--codex` adds a handler running `awkit hook` beside the project's own handlers: it blocks commits whose author or trailers differ from the history, stops the agent from finishing with changed files that have no passing check (left out when the project has a completion gate), and gives one line of the matching guide when a search, an upload, a subagent or a Markdown edit starts. Show the user the rules and remove those they do not want. With a copied kit folder, also offer `awkit kit skills --provider claude` or `--provider codex`, which `kit init` without `--copy` has already run.
6. Commit the profile and the check configuration. `awkit kit init` has already committed its section and the skills unless it said otherwise; tell the user. The review commands do not create repositories or commits: if `awkit review` reports that the folder is not a Git repository or has no commit, commit the files first.

`awkit kit remove` takes out everything `kit init`, `kit skills` and `kit hooks` added and restores the files they changed. For a newer kit, update awkit and run `awkit kit skills` again: it regenerates the skills awkit wrote and leaves the profile as it is.

Ask before touching credentials, remote targets or settings outside the project folder.

Prevents: F7, F9, F11, F12, F29.
