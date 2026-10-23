# Connection diagnostics

Status: review. Owner: the current Codex session. Base: `4a7cb6a`. The owner requested further case collection and fixes where the evidence is sufficient, then required the local runtime to follow the latest dev commit. Scope: connection diagnostics, guidance and regression checks. Preserve existing project files, check execution semantics, doctor exit codes and finding fields. Deliver through dev and synchronize the local installation after Windows and Linux CI passes, as recorded in AGENTS.md.

## Evidence and decisions

The owner supplied a connection report from another project: no checks were inferred initially; a manual writing check reported 106 findings in existing documents; Git exclude writes required sandbox permission; and Python path resolution returned a duplicated folder only inside that sandbox. Those are reported observations. The other project's files, original commands and full logs were not inspected here.

This repository supplied two independent observations. The earlier local collaboration record describes doctor printing ready with PATH warnings and unverified hooks. Before the latest reinstall, installed and checkout versions both said 0.3.0, but package metadata identified `f85a1ec` while the delivered code was `4a7cb6a`; three Python files and four kit documents differed after normalizing line endings. Reinstallation and a file comparison established equality at that point. A version string alone did not.

Synthetic cases at the base revision are retained in `.awkit/handoffs/connection-diagnostics/before.json`; the reproducer is `.awkit/probes/connection-diagnostics.py`. A temporary Git project with no recognized manifest produced no suggested commands. Initial init warned; repeated init did not. Both were followed by doctor's ready summary and review's rejection of an empty configuration. Empty lists, malformed TOML and empty command arrays also received the ready summary. A configured command was never executed by doctor.

These cases justify validating configuration through review's existing validator, retaining the repeated-init warning, and distinguishing tool availability from execution evidence. Runtime diagnostics identify the loaded module and use distribution provenance only when its module location matches. Source checkouts use their own Git revision and report local modifications. Missing or malformed metadata stays unknown; URLs and credentials are omitted. Recorded installation provenance is not an integrity check or a remote freshness check.

## Writing scope and path limits

Four synthetic writing comparisons cover an unchanged old finding, a new finding, mixed Korean endings, and removal of a code fence around unchanged text. They reproduce the old-finding burden and show why checking only added lines is insufficient: deleting a fence exposes an unchanged line to prose rules, and mixed endings require the whole document.

No writing-check behavior changes in this task. A later trial needs actual before/after edits and an explicit baseline policy for user edits, renames, repeated edits, newly exposed prose and whole-document findings. Full inspection must remain available, and retained findings must not be described as resolved. The reported 106 findings are not independently classified as mistakes or false positives.

The [proposal trial](workflow-review.md) subsequently reproduced the burden during actual edits. `89549b7` clarifies output scope while retaining full-file inspection and existing exit codes. Before implementing classification, define which revision supplies the baseline and when it may advance; automatic advancement after a failed or partial review could hide unresolved findings. Exercise unchanged errors with clean additions, introduced errors, shifted lines, renames, repeated edits, user edits, removed fences and mixed endings. Findings without reliable correspondence must remain unclassified. Acceptance requires both a reproducible before/after comparison and retained full-file results; an extracted-lines pass is not a full-document pass. Select display and exit-code policy explicitly before implementation.

No path-resolution replacement is justified yet. The reported standalone Python comparison narrows the condition to a sandbox, but does not identify the responsible implementation. The shell used for executable probes here required execution permission, so it does not reproduce that sandbox condition. Preserve link resolution and containment checks until a minimal reproducer establishes a safe correction. The exclude-file permission denial is not treated as a product failure.

### Proposed first comparison unit

The [planning trial](planning-implementation.md) recommends a comparison report before changing enforcement. Its benefit is to show which findings need investigation after an edit; it does not yet remove the burden of existing errors. The candidate's full-file findings and current exit policy remain authoritative.

Use an explicitly selected frozen baseline and candidate. Record both trees and the checker revision, and evaluate both versions with the same checker. A session start, user edit, failed run or successful partial review must not silently advance the baseline. Calling a finding existing means it was also present in that baseline; it does not mean accepted or resolved.

Classify reliable matches as existing and reliable new findings as introduced. Keep ambiguous correspondence unclassified, with the reason. Shifted line numbers alone do not make an error new. Duplicate passages, uncertain rename mappings and whole-document findings require conservative treatment. Removed code fences must expose newly checked prose even when its text was not added. Preserve the original finding fields and the full current report; any machine-readable extension needs a documented compatibility contract.

The first handoff should return a comparison contract and fixture results for the scenarios above, including repeated edits against an unchanged baseline and a checker-version change. It must explain how each classification follows from the retained inputs. Only then implement the bounded report. Changing what blocks a task is a later decision supported by actual use, not a side effect of classification.

The planning trial adds nine fixed-text cases in `.awkit/handoffs/planning-implementation/writing-comparison-cases.json`, evaluated by the current full-file checker at `c0f0801`. Two results constrain the design: changing a contributing Korean-ending passage can leave the whole-document finding object identical, and two errors on one line can have identical line, pattern and excerpt fields. Comparing serialized finding objects alone therefore loses evidence and can collapse occurrences. Retain full inputs and occurrence correspondence; these cases are proposed requirements, not results from an implemented classifier.

## Automatic hook import investigation

The later proposal trial includes a reported Stop-hook `ImportError` for `awkit.checks`. Installed source and kit contents matched their recorded commit; an approved shell imported the module successfully while the restricted shell could not launch the base interpreter. These are different execution conditions and do not explain the automatic failure. Keep this separate from the earlier path-resolution report.

Next, capture a sanitized failing automatic event with the client/version, interpreter and loaded module paths, working directory, execution permissions and traceback. Compare the same invocation in the automatic hook and direct shell, preserving settings and package provenance. Do not reinstall merely to hide the failing state. A correction is accepted only when the original automatic path is reproduced and passes after the change, with unsupported clients or permission contexts still explicit. If reproduction remains unavailable, retain the uncertainty and the minimal next probe instead of claiming restored hooks from a direct import.

## Verification and next action

Acceptance requires regression cases for empty and invalid settings, repeat installation, configured-but-unexecuted commands, matching and mismatched metadata, missing provenance, and a source checkout with local edits. The frozen snapshot must pass `checks.toml`; record its result outside the snapshot in `.awkit/handoffs/connection-diagnostics/validation.json`. Inspect documentation and generated guard mappings. Record failures and environment limits separately. Then retain this task as the source of the deferred writing and path investigation.
