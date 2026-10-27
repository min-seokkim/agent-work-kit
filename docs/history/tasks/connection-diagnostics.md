# Connection diagnostics

> Historical record preserved from `90e2557`. Read [the current record](../../tasks/connection-diagnostics.md) before resuming. Stage-specific statuses and assignments below describe that revision. Local `.awkit/` paths remain relative to the repository root.

## Current status

Deferred investigation. Connection diagnostics and first-check guidance have shipped; unexpected-hook error context shipped in `fa3d50d`. The original automatic-hook failure remains unreproduced.

Next action: Resume the automatic-hook investigation only with the failing invocation and its actual runtime context. Reuse the delivered diagnostics and preserve the unresolved historical cause.

## Earlier scope and evidence

The following sections retain the original assignments and observations. Their stage-specific status statements are historical; use the current status above when resuming.

Status: review. Owner: the current Codex session. Base: `4a7cb6a`. The owner requested further case collection and fixes where the evidence is sufficient, then required the local runtime to follow the latest dev commit. Scope: connection diagnostics, guidance and regression checks. Preserve existing project files, check execution semantics, doctor exit codes and finding fields. Deliver through dev and synchronize the local installation after Windows and Linux CI passes, as recorded in AGENTS.md.

## Evidence and decisions

The owner supplied a connection report from another project: no checks were inferred initially; a manual writing check reported 106 findings in existing documents; Git exclude writes required sandbox permission; and Python path resolution returned a duplicated folder only inside that sandbox. Those are reported observations. The other project's files, original commands and full logs were not inspected here.

This repository supplied two independent observations. The earlier local collaboration record describes doctor printing ready with PATH warnings and unverified hooks. Before the latest reinstall, installed and checkout versions both said 0.3.0, but package metadata identified `f85a1ec` while the delivered code was `4a7cb6a`; three Python files and four kit documents differed after normalizing line endings. Reinstallation and a file comparison established equality at that point. A version string alone did not.

Synthetic cases at the base revision are retained in `.awkit/handoffs/connection-diagnostics/before.json`; the reproducer is `.awkit/probes/connection-diagnostics.py`. A temporary Git project with no recognized manifest produced no suggested commands. Initial init warned; repeated init did not. Both were followed by doctor's ready summary and review's rejection of an empty configuration. Empty lists, malformed TOML and empty command arrays also received the ready summary. A configured command was never executed by doctor.

These cases justify validating configuration through review's existing validator, retaining the repeated-init warning, and distinguishing tool availability from execution evidence. Runtime diagnostics identify the loaded module and use distribution provenance only when its module location matches. Source checkouts use their own Git revision and report local modifications. Missing or malformed metadata stays unknown; URLs and credentials are omitted. Recorded installation provenance is not an integrity check or a remote freshness check.

## Writing scope and path limits

Four synthetic writing comparisons cover an unchanged old finding, a new finding, mixed Korean endings, and removal of a code fence around unchanged text. They reproduce the old-finding burden and show why checking only added lines is insufficient: deleting a fence exposes an unchanged line to prose rules, and mixed endings require the whole document.

No writing-check behavior changes in this task. A later trial needs actual before/after edits and an explicit baseline policy for user edits, renames, repeated edits, newly exposed prose and whole-document findings. Full inspection must remain available, and retained findings must not be described as resolved. The reported 106 findings are not independently classified as mistakes or false positives.

The [proposal trial](../../tasks/workflow-review.md) subsequently reproduced the burden during actual edits. `89549b7` clarifies output scope while retaining full-file inspection and existing exit codes. Before implementing classification, define which revision supplies the baseline and when it may advance; automatic advancement after a failed or partial review could hide unresolved findings. Exercise unchanged errors with clean additions, introduced errors, shifted lines, renames, repeated edits, user edits, removed fences and mixed endings. Findings without reliable correspondence must remain unclassified. Acceptance requires both a reproducible before/after comparison and retained full-file results; an extracted-lines pass is not a full-document pass. Select display and exit-code policy explicitly before implementation.

The original investigation deferred path changes because its executable probes required permission outside the failing sandbox. The exclude-file permission denial remains separate.

### Default scan path follow-up

At base `c08418b`, the owner supplied the missing invocation: `awkit kit scan` failed with the current folder name repeated; specifying the absolute project folder worked. The intended result is for default, explicit-dot and absolute scan inputs to select the same folder. Verification covers those CLI forms, the Windows access-denied fallback, directory links and the frozen repository checks.

The installed Python 3.14.7 implementation explains a reproducible failure mechanism. `realpath('.')` joins the current directory with a trailing dot. When `_getfinalpathname` denies that path, its non-strict fallback uses `_findfirstfile`, which returns the current directory's name for the dot. Splitting the input removes only the dot, so the fallback appends the directory name again. A probe mocking only that OS denial reproduced the duplicated path with the real Python fallback. Making the input absolute before resolving avoided it.

`scan` now anchors its input with `Path.absolute()` before `resolve()`. Resolution of links remains enabled, and no repeated names are removed from paths. The correction is limited to the reported scan entry point. Other commands and the sandbox's original access-denial trigger remain unverified.

Focused Windows checks passed five cases and skipped the directory-link case because Windows denied link creation. The default tool shell could not launch the installed Python; the same interpreter ran outside that sandbox. Native path probes in the reported directory succeeded in the current sandbox, so the original automatic failure was not reproduced end to end. This is a tested correction for the reproduced Python failure mechanism, not evidence that the sandbox's access policy changed. Delivery receipts belong in `.awkit/handoffs/scan-relative-path/`.

The first frozen run, `.awkit/reviews/review-262t8f1i`, could not launch Ruff because its executable was absent from the shell's PATH. Adding the existing `.awkit/tools/ruff/bin` directory made the focused lint check pass. The final Windows fault test checks scan output without requiring every Python version to exhibit the older fallback defect. Records and CHANGELOG received source review and mechanical writing checks; rendered Markdown inspection was omitted for this bounded update.

### Proposed first comparison unit

The [writing-comparison task](../../tasks/writing-comparison.md) now owns the accepted first interface, contract evidence and implementation state. The requirements below retain their planning basis.

The [planning trial](../../tasks/planning-implementation.md) recommends a comparison report before changing enforcement. Its benefit is to show which findings need investigation after an edit; it does not yet remove the burden of existing errors. The candidate's full-file findings and current exit policy remain authoritative.

Use an explicitly selected frozen baseline and candidate. Record both trees and the checker revision, and evaluate both versions with the same checker. A session start, user edit, failed run or successful partial review must not silently advance the baseline. Calling a finding existing means it was also present in that baseline; it does not mean accepted or resolved.

Classify reliable matches as existing and reliable new findings as introduced. Keep ambiguous correspondence unclassified, with the reason. Shifted line numbers alone do not make an error new. Duplicate passages, uncertain rename mappings and whole-document findings require conservative treatment. Removed code fences must expose newly checked prose even when its text was not added. Preserve the original finding fields and the full current report; any machine-readable extension needs a documented compatibility contract.

The first handoff should return a comparison contract and fixture results for the scenarios above, including repeated edits against an unchanged baseline and a checker-version change. It must explain how each classification follows from the retained inputs. Only then implement the bounded report. Changing what blocks a task is a later decision supported by actual use, not a side effect of classification.

The planning trial adds nine fixed-text cases in `.awkit/handoffs/planning-implementation/writing-comparison-cases.json`, evaluated by the current full-file checker at `c0f0801`. Two results constrain the design: changing a contributing Korean-ending passage can leave the whole-document finding object identical, and two errors on one line can have identical line, pattern and excerpt fields. Comparing serialized finding objects alone therefore loses evidence and can collapse occurrences. Retain full inputs and occurrence correspondence; these cases are proposed requirements, not results from an implemented classifier.

## Automatic hook import investigation

The later proposal trial includes a reported Stop-hook `ImportError` for `awkit.checks`. Installed source and kit contents matched their recorded commit; an approved shell imported the module successfully while the restricted shell could not launch the base interpreter. These are different execution conditions and do not explain the automatic failure. Keep this separate from the earlier path-resolution report.

Next, capture a sanitized failing automatic event with the client/version, interpreter and loaded module paths, working directory, execution permissions and traceback. Compare the same invocation in the automatic hook and direct shell, preserving settings and package provenance. Do not reinstall merely to hide the failing state. A correction is accepted only when the original automatic path is reproduced and passes after the change, with unsupported clients or permission contexts still explicit. If reproduction remains unavailable, retain the uncertainty and the minimal next probe instead of claiming restored hooks from a direct import.

### Unexpected hook error context (M-141)

Status: implementation resumed by the owner's explicit commit-and-main-merge request after earlier deferral under M-142/M-145. Base: `116f2c3`; original work from `c3dd1bf` is preserved on local branch `preserved/pre-main-progress` at `29a06d6`. Scope: `hooks.run`'s existing unexpected-exception
row, relevant hook tests, the hook-log reference, CHANGELOG and this section.
The generalized planning changes are already integrated in `116f2c3`; this unit preserves that history.
No real hook settings, native client or historical failure is changed or forced.

R-033 retained a different `awkit.process` ModuleNotFoundError with only summary
fields. Research R-035 inspected the boundary; neither establishes its stack,
cause or automatic origin. The older reported `awkit.checks` import failure is
also unresolved. Read-only metadata and contract review are not a reproduction.

The schema and limits below are fixed before editing implementation. The new
optional row key is `context`; absence remains valid for legacy rows. On newly
caught unexpected exceptions it defaults to this schema-1 object:

- `schema`: integer 1.
- `executable`, `cwd`, `awkit_file`, `hooks_file`: current process executable/cwd
  and already loaded module origins, each a string of at most 512 characters.
- `python_version`: current `sys.version`, at most 256 characters.
- `exception_type`: class module/qualified-name identifier, at most 128 characters.
- `frames`: at most eight awkit traceback identifiers, each with `file` (512),
  `function` (128) and positive signed-32-bit integer `line`. Inspect at most 64 traceback links,
  keeping the last eight matching awkit module frames within that inspected range.

Unavailable scalar fields are null and unavailable frames are an empty list.
Only string values are retained; no object repr is used for diagnostic values.
Read already loaded state without importing the missing module, scanning packages
or resolving provenance. Exclude selected roots and payload-derived client or
permission labels, payloads/prompts/tool input, argv, environment and sys.path,
traceback source lines and locals. Process facts do not authenticate the sender,
automatic origin, installed commit integrity or a child process's environment.
Paths can identify users/projects: keep logs local and sanitize before sharing.
The legacy reason keeps its existing 160-character trimming and is not newly
certified free of sensitive text.

Initialize unavailable context before collection. A collector failure leaves that
context and the original legacy error reason available for the existing best-effort
logger. Collection/cwd/log-write failures must not print diagnostics, recurse into
logging, replace the original error or block the agent. Expected rule errors,
malformed input and ordinary firing rows keep their existing shapes; output,
decisions and report counts remain unchanged. Interpreter/executable startup,
imports before `hooks.run` and its initial cwd lookup remain outside this handler.

Check the actual `_run` exception boundary in isolated fixtures with an invented
ModuleNotFoundError. Verify one augmented row and empty output, process facts
versus fake payload claims, excluded secret sentinels, unavailable fields,
frame/string bounds, collector failures, unwritable logging and report counts
with legacy rows. Retain expected-rule-error and ordinary-firing shapes. Then run
existing hook compatibility/kit checks and the cumulative required checks before
normal dev delivery, Windows/Linux CI and exact installation. Offline capture
can demonstrate debugging context; it cannot repair either historical failure.

The first focused snapshot `29a3f4ed742ebf9cd98c6d29ab40ccf8198608d2`, run
`.awkit/reviews/review-zhrt5j3_`, passed lint and thirteen tests. One collection
fixture failed: globally mocking cwd also broke existing Windows root resolution
before the injected `_run` boundary. The corrected fixture holds its known root
fixed while failing context observations. No production root-resolution behavior
was changed; the initial run remains retained. The reference's hook introduction
and error/log prose are shortened with existing conditions preserved to fit the
additive schema contract within the current word limit.

The resumed unit keeps the original collection contract. Its test helper no longer shadows unittest.TestCase.fail, so failed assertions retain their ordinary diagnostics. Self-review also found that an exception class can have non-string module metadata; the collector now leaves that identifier unavailable without invoking its string representation. A sentinel regression checks this exclusion. Implementation self-review distinguishes process observations from payload claims and preserves legacy output/report behavior. Final snapshot, checks, dev/main delivery and installation receipts are retained in `.awkit/handoffs/commit-and-main-merge/delivery.json`. Historical automatic-hook failures remain unresolved; synthetic capture establishes only the documented handler boundary.

## Selecting the first checked revision

Status: implemented for M-129/M-133; cumulative delivery is recorded in `.awkit/handoffs/first-check-revision/executor/delivery.json`. Base: `3c771e8`. Scope: connection step 3, the reference's scan paragraph, the checking guide's dependency pointer, this record and the unreleased CHANGELOG entry. CLI/source behavior and commit policy are unchanged.

Research M-028/R-024 found a retained initial check against an old tree without the new task input, followed by a passing snapshot containing it. Tree-presence queries support that distinction; the historical command trace, elapsed recovery and causal role of kit guidance were not inspected. The application incident was already recovered. Only the sanitized research memo and metadata were read for this unit; no private project files were reopened.

The connection and reference guides now use HEAD only when it contains the intended source and command dependencies. Otherwise they route to the existing explicit-file snapshot procedure. Configuration remains read outside the snapshot and separately hashed; an uncommitted configuration alone does not require a snapshot unless a check reads it as an input. This does not advance a baseline, commit files automatically or suppress a genuine failure.

The checking guide now points to the existing `[[setup]]` mechanism for each fresh worktree and per-run path expansion. Project-specific install/link commands stay in `checks.toml`. Reused dependencies must match the snapshot's declared inputs and cannot load project code or generated outputs from an unreviewed working tree. A configuration hash does not verify dependency contents. Existing isolation/concurrency guidance remains in place. Research R-026 found the contract sufficient; it did not reproduce the application's dependency suitability.

### Synthetic route and preservation

The invented fixture in `.awkit/handoffs/first-check-revision/executor/corrected/` checks committed input against HEAD successfully, retains a failed HEAD check when a new task input is absent, then passes an explicit snapshot containing only that new input over HEAD. Both configurations are uncommitted and absent from both checked trees; the runner records their hashes separately. The committed baseline and current validation remain distinct. `fixture-result.json` records full revisions, config hashes and all three run folders.

The exercise verifies unchanged branch, HEAD, raw index bytes, worktree files and unrelated staged/unstaged/untracked edits. The snapshot excludes those unrelated edits. No real project source or private material was copied into the fixture. This supports the documented route, not historical causation or a measured benefit.

The first invented fixture failed unexpectedly because Windows text writes produced CRLF while its assertion expected LF. Retain `runs/review-xb3wrezy` and `reproduce-first-attempt.py`; the corrected fixture uses explicit LF in a new directory. This is an executor fixture error, separate from the intentional missing-input failure and from a product defect. A prior edit helper also stopped on the system encoding while reading UTF-8; subsequent reads use explicit UTF-8 and the error record remains.

The first focused run, `.awkit/reviews/review-6qs5p9he`, caught a guide-packaging defect in the new pointer: nested brackets in its Markdown link label prevented the existing skill-link rewriter from converting that relative target. The label now uses plain words, with `[[setup]]` outside the link. The original focused run and corrected run remain separate. No parser or command behavior changed.

Focused corrected snapshot `f271686b84dc93800c1790198c19d84a64f9c47c` passed in `.awkit/reviews/review-oqgi5aa9`: 17 kit tests and six snapshot/setup tests, with one Windows directory-link skip. The reference remains at 8,995 words under its 9,000-word limit. The later cumulative full check and CI/install identity belong to `delivery.json`.

Existing kit/link/word-limit/guard tests and focused snapshot/setup tests cover the changed passages and reused contracts. No wording-matching tests, new command, dependency, detector, cache manager or universal linking recipe were added. The guard table was regenerated; its mapping is unchanged. Source/diff and preservation review are executor self-review. Rendered Markdown inspection is omitted for this bounded unit under the retained browser/native limits; passing commands do not establish intended-reader quality or owner acceptance.

The five planning files transferred in M-135 are included in the cumulative delivery with their exact transfer hashes verified first. Their originating session's source reading, mechanical checks and rendering limits remain distinct from the executor's checks. Preserve other-session commit `3c771e8`; no further main merge is assigned.

## Verification and next action

Acceptance requires regression cases for empty and invalid settings, repeat installation, configured-but-unexecuted commands, matching and mismatched metadata, missing provenance, and a source checkout with local edits. The frozen snapshot must pass `checks.toml`; record its result outside the snapshot in `.awkit/handoffs/connection-diagnostics/validation.json`. Inspect documentation and generated guard mappings. Record failures and environment limits separately. Then retain this task as the source of the deferred writing and path investigation.
