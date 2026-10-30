# Windows review path recovery

For checkout errors naming a long path, choose a shorter absolute `DIR` outside cloud-sync folders and retry the same snapshot:

```text
awkit review check REVISION --config checks.toml --runs-root DIR
awkit check done --runs-root DIR
awkit review storage --runs-root DIR
```

Completion lookup and the project's `done-check` hook need that root. In `rules.toml`, append `"--runs-root", "DIR"` to the existing rule's `command` array, replacing `DIR` with the absolute path using `/`; preserve its other fields, including `command_protocol`. A different shared root starts a separate collection/store without reuse or migration. Keep prior history in place.

Alternatively, choose repository-local Git handling with `git config --local core.longpaths true`. This passed checkout, Python file reads, copied/shared collection and removal on Windows with `LongPathsEnabled=1`; awkit does not set it. Keep the setting through later removal of retained worktrees: check `git -C WORKTREE status --porcelain`, preserve needed evidence and work, then use `git worktree remove WORKTREE` from the repository. Ordinary removal without long-path handling can leave files after removing the registration.

Measured UTF-16 limits apply only to that host. Directory and auxiliary paths can fail earlier; external tools, component limits and other runtimes remain unqualified.
