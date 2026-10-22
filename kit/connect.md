# Connect the Kit to a Project

Use this once, when the kit has just been added to a project and the [project profile](templates/project.md) is still empty. It turns the project's existing commands into a check configuration and records what the agent needs to start a task. [Example profiles](examples/project-profiles.md) show filled profiles for several kinds of project.

Run `awkit kit scan` in the project folder. It reports the manifests, the commands the project already defines (package scripts, test and lint configuration, Makefile targets, CI run lines), the documentation folders and the Git state, and prints a suggested `checks.toml`. Treat every suggestion as unverified: the scan reads file names and manifests, not behavior.

Then do the following, and record each result rather than assuming it:

1. Fill the five "Start here" fields of the profile from the scan and from one question to the user: what counts as done for this project, and who or what receives the result. Do not invent a build or deployment step the project does not have.
2. Write `checks.toml` from the commands the scan found, run `awkit review check HEAD --config checks.toml` once, and keep only the commands that actually run here. List the files a passing run must produce under `artifacts` and `required_artifacts`.
3. Record the delivery stages the project really uses (build, test, install, submit, accept, verify in use) in the profile's "Deliverables and completion" section; [Delivery](delivery.md) says what each needs.
4. Offer the user `awkit kit skills --provider claude` or `--provider codex`, which writes one skill per situation guide so each guide loads when its situation arises instead of every session.
5. Offer the user the hooks from `awkit kit hooks`: `--git` stops commits whose author or trailers differ from the repository's history, and `--claude` stops Claude Code from finishing with changed files that have no passing check.
6. Commit the profile, the check configuration and any skill files. `awkit kit init` has already committed the kit folder, creating the repository if the project had none; say so to the user. The review commands do not create repositories or commits: if `awkit review` reports that the folder is not a Git repository or has no commit, commit the files first.

Ask before touching credentials, remote targets or settings outside the project folder.
