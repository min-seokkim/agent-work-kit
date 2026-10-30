# Review preparation failure evidence

## Current status

Independent code review accepted snapshot `e336c296` from `7e82e3f` without correction findings. The unit retains the cause and phase of caught runner exceptions already saved as `uncertain`, reports the run location and documents demonstrated Windows path recovery. Root owns product scope and planning review; the implementation session owns source, checks and delivery. The implementation receipt records the final snapshot, full check, publication and exact installation stages; confirm those stages there before treating delivery as complete.

The starting comparison found installed provenance, 45 source files, 31 kit files and 16 generated user skills aligned with `7e82e3f`. Its existing CI run passed all 21 Windows/Linux jobs. The original local-check and installation-invocation receipts remain unavailable; the new read-only observation does not recreate them.

## Contract and evidence

- Accepted planning contract: `.awkit/handoffs/planning-continuation/failure-evidence-contract.md`, accepted in planning review `M-007/R-004`, with corrections incorporated in `M-009`.
- Starting observation: `.awkit/handoffs/windows-worktree-path/startup-readiness.json`.
- Diagnosis: `.awkit/handoffs/windows-worktree-path/receipt.json`; its raw observations preserve the initial fixture CRLF assertion failures and their correction.
- Implementation evidence: `.awkit/handoffs/windows-worktree-path/implementation.json`. The receipt owns snapshot IDs, focused results, review and delivery stages.
- Independent review: `.awkit/handoffs/windows-worktree-path/code-review/result.json`. Eight isolated probes passed; the reviewer inspected all ten changed files, direct readers and four rendered excerpts. Full-reference and client-specific rendering remain uninspected.

The observed path failure occurred under a measurement-only root; the target already has a short-root mitigation. No ordinary continuation is established as blocked. On the diagnosed host, Git refused long paths despite `LongPathsEnabled=1`, with empty check history, CLI exit 2 and saved `uncertain`. Copied records lacked the cause. Shared records kept it only in incomplete artifact-publication metadata.

## Selected behavior and limits

The optional `result.json` field `failure` contains `phase` and `error` for the existing caught runner exceptions saved as `uncertain`. It covers preparation and later runner operations without inventing steps or changing configured-step failures. CLI diagnostics name the run and distinguish a failure to save the diagnostic from the original error. Existing statuses, exit behavior, cleanup observations, shared publication and reader integrity rules remain.

Shortening `--runs-root` recovered the same synthetic snapshot in both storage modes. Completion lookup and hooks must use that root; another shared root creates another store without migrating history. A disposable repository-local `core.longpaths=true` trial also passed both collection modes and later clean removal. Removing a kept long worktree without that handling failed and left unregistered files. The demonstrated prerequisite was Windows `LongPathsEnabled=1`; this is not qualification of arbitrary tools or runtimes.

Automatic long-path handling, numeric preflight limits, shorter generated names, new status categories and broader filesystem changes remain deferred. Reassess automatic support after an ordinary default-root blockage or a second affected project. Retained evidence was selected because documentation alone leaves copied failure records unexplained; path-support deferral remains defensible while the known target is mitigated.

## Next action

Read the implementation receipt before repeating a check or delivery stage. Resume any incomplete frozen full check, `dev` publication, Windows/Linux CI or exact-commit installation and source/kit/user-skill comparison from its recorded state. Once those stages are complete, this bounded unit needs no further implementation. Preserve the unavailable original delivery receipt and rendering limits.
