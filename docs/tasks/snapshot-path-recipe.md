# Snapshot command path handling

Status: documentation candidate `e8f0529`, accepted in `M-079`, shipped with the [existing-project diagnostic](installed-guide-paths.md#reported-delivery-and-product-consequence) through `2d41ba1`, as reported in `R-048` and the shared receipt. Planning owns scope. Implementation owns execution records, verification and delivery under `M-081`, the named documentation files below and isolated evidence under `.awkit/handoffs/snapshot-path-recipe-preparation/`. The initial Windows CI failure and its test assertion repair remain recorded below; later planning edits are outside that delivered snapshot.

## Observed problem

An authorized application-log inspection showed PowerShell collecting Git's display output and passing its quoted non-ASCII paths to `awkit review snapshot`. The command refused the representation because it was not the actual filename. An invented fixture reproduced this with PowerShell 5.1 and Python 3.14.7. Spaced filenames remained single arguments; this observed failure was Git display quoting, not PowerShell whitespace splitting.

The per-command `core.quotepath=false` control succeeded but selected every cached file, including an unchanged control. The corrected recipe reads NUL-delimited changed paths from `git diff --name-only --no-renames -z HEAD` and untracked paths from `git ls-files --others --exclude-standard -z`, decodes them and passes a direct argument list. It selects two tracked edits, two untracked files and one deletion; the unchanged control is excluded from explicit selection but remains in the snapshot's inherited HEAD content.

## Normal installation refinement

The first recipe invoked the script's Python with `-m awkit`. Planning identified that ordinary Python may not import a pipx-installed awkit. The refinement resolves the installed executable on PATH and stops explicitly if absent. With PYTHONPATH removed and awkit unavailable to that Python's import mechanism, the recipe succeeded. Snapshot `2ea1b33` has the same full tree as source-runtime snapshot `aa1faef`; independently specified blob bytes, selected paths and deletion matched. Actual HEAD, index and status remained unchanged. Both recipes and the original failure are retained.

Planning read both scripts, the reports, discovery evidence and selected-path/tree assertions. No product defect or parser change is established. Only the Windows route was exercised; other platforms, encodings and unusual filename cases remain outside the evidence.

## Assigned documentation unit

Put one runnable installed-CLI recipe in the existing snapshot section of `kit/reference.md`, link to it from `AGENTS.md`, and add one CHANGELOG entry. Preserve additions/deletions, HEAD inclusion, path refusals, unchanged Git state, lack of secret filtering and garbage-collection limits. Recalculate the reference word limit: the earlier source-runtime proposal had no remaining margin. Test the exact documented snippet against the retained fixture and run existing link, kit, word-limit and writing checks. Do not add a command, dependency, persistent Git setting or automatic migration. This preparation establishes no writing-quality improvement or reduction in repeated owner effort.

The accepted diagnostic leaves the reference at 8,959 words. Preserve its explanation and source changes while revising the existing snapshot section. Give an actual PowerShell-compatible invocation or an explicitly external script path so the helper is not accidentally selected as a new project file. The returned documentation snapshot will not supersede the diagnostic's source snapshot; implementation now owns cumulative checks, installation and delivery under `M-081`.

## Candidate verification

`R-044` returned the three-file documentation snapshot. It preserves the accepted diagnostic's source, doctor explanation and CHANGELOG entry; the documentation snapshot itself does not contain or supersede the diagnostic source candidate. The final reference has 8,996 words. `AGENTS.md` links to one PowerShell block that passes Python through standard input, captures the snapshot ID and stops on a nonzero exit, without creating a helper in the project.

Frozen run `.awkit/reviews/review-azo7d9k8` passed five existing guard, link, word-limit and skill-payload checks, writing checks, and extraction/execution of the exact documented block. In Windows PowerShell 5.1 with ordinary Python 3.14.7, PYTHONPATH removed and awkit not importable, the installed CLI produced fixture snapshot `97540ca`. The five-path delta, expected frozen bytes and deletion matched. Unchanged HEAD content remained included; branch, HEAD, index, status and worktree hashes stayed unchanged. Missing-CLI and empty-selection cases stopped explicitly. Reports and per-command logs are under the preparation folder's `documentation/` directory.

Planning read the candidate, helper, preservation and execution records, verified current-file correspondence, and inspected the reference code block, AGENTS instructions and CHANGELOG rendered in Edge. `M-079` accepts the result for cumulative integration. No POSIX route, broader encoding support, parser correction or reduced user effort is established. Full checks, CI and exact installation belong to the shared delivery receipt under `.awkit/handoffs/project-update-delivery/`.

## Cumulative execution and delivery

Commit `335270b` combined this documentation with the diagnostic and planning records after snapshot `5fe139f` passed Ruff and 360 tests with seven skips. [CI run 40068654398](https://github.com/min-seokkim/agent-work-kit/actions/runs/40068654398) failed only in the diagnostic's exact-path assertion on four Windows interpreters. The snapshot recipe itself was not implicated. The [diagnostic record](installed-guide-paths.md#windows-ci-path-identity-and-delivery-ownership) explains the filesystem-identity assertion repair and preserved evidence.

Implementation completed the follow-up checks, CI, normal `dev` delivery and exact installation under `M-081`, reported in `R-048` at `2d41ba1`; planning no longer acts as its routine code-review gate. The checked commit/tree and installation/content comparisons are retained in `.awkit/handoffs/project-update-delivery/validation.json`. Installation was withheld after the original failed CI and performed only after the corrected commit passed. That delivery does not expand the recipe's tested platform/filename scope or establish a writing-quality benefit.
