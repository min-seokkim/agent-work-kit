# Writing comparison report

Status: implementation accepted at `aa821a64248103b6ebe3e97c424745106bddc365`; cumulative delivery is tracked in the receipt below. Base: `ccea298`. The planner owns scope, contract acceptance and repository records; the existing implementation session owns the assigned command, tests and reference changes. Channel `.awkit/scoped-document-trial.sqlite3` continues the same pairing. `M-006` assigned the disposable contract experiment, returned in `R-007`; `M-008` assigned the product implementation, returned in `R-010`. Review is informed, not independent.

## Problem and chosen scope

The [proposal trial](workflow-review.md) encountered existing findings while making a local edit. A full-file report preserves the errors but leaves the agent to determine their relationship to the edit. The [diagnostic cases](connection-diagnostics.md#proposed-first-comparison-unit) show that added-line checks and finding-object equality are insufficient: removing a fence exposes unchanged prose, and different whole-document causes can produce the same summary.

Add a comparison report that directs attention to introduced and uncertain findings while retaining the complete candidate result. Existing means present in the selected baseline; it conveys no acceptance or resolution. This is a diagnosis aid. Reducing blocks, changing prose rules and measuring productivity are separate decisions. The [scoped document trial](scoped-document-trial.md) used clean inputs and did not reproduce the existing-finding burden.

This unit precedes the larger presentation trial because it has retained failure cases and a bounded command contract. The presentation plan still requires its audience, source bundle and editable-format trial. Automatic Stop-hook repair still needs the failing invocation; successful direct imports do not supply it.

## Accepted interface and policy

```text
awkit check writing-compare BASELINE CANDIDATE PATH... [--repo REPO] [--json]
```

Both revisions and the relative Markdown file scope are explicit. Resolve revisions to full commits once and read regular blobs without changing the checkout or index. The first interface compares the same selected paths. Directories, worktree input, automatic baseline advancement and inferred renames are outside this unit. Known absence from a tree is distinguished from missing comparison evidence; a path absent from both trees is an error. Unmatched added-path findings remain unclassified.

The report uses a separate format-1 envelope. Preserve each full-file finding's fields, severity and multiplicity, with occurrence IDs and source evidence alongside them. Show complete candidate status first, then introduced and unclassified occurrences and the changed regions. Retain existing findings, the full reports and a baseline inventory. Source diffs aid navigation; diff alignment alone does not establish finding identity.

| Condition | Comparison result and exit |
|---|---|
| Complete candidate contains errors | Exit 1, including when every error is existing. |
| Complete candidate has no errors | Exit 0; warnings remain visible. Unclassified correspondence is still reported. |
| Required evidence is unavailable or invalid | Exit 2. Available candidate findings remain visible where possible; incomplete coverage cannot imply zero findings. |
| Candidate has no selected file | Report no file checked; do not describe a document as passed. |

Legacy `check writing` output, JSON and exit policy remain unchanged, as do hooks and `check done`. Neither command success nor an edit selects a new baseline. Exact introduced totals remain unknown while correspondence is unresolved. Strict supported decoding and valid repository-relative paths are required; unsupported data and nonregular blobs produce comparison errors.

## Correspondence and contract evidence

Identical complete bytes under the same checker support occurrence-order correspondence. Otherwise, line-local findings can match on a raw line unique in both sources with the same rule and occurrence span/order. This handles line shifts while preserving duplicate occurrences. Full-file checking detects newly exposed prose after a fence change. Changed or duplicate passages with unresolved prior occurrences remain unclassified.

A whole-document finding absent from the baseline is introduced. If both versions have it and the input changes, correspondence remains unclassified in this first scope. The selected baseline stays fixed across successive candidates and fictional user edits. Baseline absence is an observation, not proof of an accepted correction.

The disposable probe under `.awkit/handoffs/scoped-document-trial/comparison-contract/` uses the installed `ccea298` checker on both complete inputs. Final `run-04` matches 27 prewritten expected classifications and reproduces the nine earlier raw finding payloads under the current checker. It retains raw reports, source identities, occurrence witnesses and fixed-baseline groups. The actual legacy CLI exits 1 on the old-error/clean-addition case. Earlier runs remain available; later runs added coverage fields, navigation evidence and two cases before the mapping correction below. No productivity improvement was measured.

The prototype supports explicit unchanged rename and new-file metadata to explore their semantics. Those mappings are excluded from the first product interface. Product tests must use the narrower interface's unclassified fallback. Controlled read failures and checker-identity mismatch exercise reporting decisions; they do not establish a Windows permission reproducer or execution of a second checker version. No historical-report import is assigned merely to support the mismatch fixture.

Planner feedback `M-007` required one-to-one correspondence. Executor inspection found that the prototype did not reject overlapping explicit and implicit mappings. The corrected probe rejects that overlap and retains both candidate findings as unclassified; `mapping-negative/result.json` records the post-fix execution. The pre-fix overlap was identified by inspection, not executed. The 27 cases were rerun after this correction. Contract prose was read and passed mechanical checks, but its separate rendered layout was not inspected; no contract-layout acceptance is claimed.

## Implementation and acceptance

The executor owns comparison helpers, CLI wiring, focused tests, the command reference, CHANGELOG and generated guard mapping. The planner owns this record, roadmap, design, development and evidence. No new dependency, agent, standing writing rule or policy waiver is assigned.

Acceptance requires a frozen candidate, meaningful regressions for context and multiplicity, legacy compatibility, accurate CLI reports and proof that reads leave the real index and checkout untouched. Run focused tests before the final cumulative repository check. Planner inspection covers the report's usefulness and stated uncertainty as well as the implementation diff. Root commit, push, Windows/Linux CI and exact-commit installation follow as one delivery assignment after acceptance.

Task cost, manual attribution effort and productivity remain unmeasured. Detailed execution and final delivery receipts belong under the same handoff folder; `delivery/validation.json` will identify delivered revisions separately from the tree being checked.

The accepted seven-file candidate is `aa821a64248103b6ebe3e97c424745106bddc365`. It adds a separate comparison module and CLI entry, 16 command tests, reference and CHANGELOG entries, and the generated F13/F14 mapping. Focused verification passed 28 tests covering the new command, legacy writing and kit installation, followed by four documentation/guard checks. Ruff, changed-document writing and diff whitespace checks passed. The final two affected display tests passed after the later corrections; unaffected evidence was reused. Full repository verification remains a separate delivery gate.

Planner review found two display defects after an initial 15-test pass: missing terminal newlines joined removed and added rows, and the first correction mislabeled CR line endings as absent. Actual CLI before/after records and LF/CRLF/CR/unterminated-input tests cover the fixes with original hashes preserved. The planner also corrected an overbroad reference statement about changed spans. Executor review distinguished known absent paths from unavailable source evidence in the display. These are review findings on the new command, not evidence of changed writing rules.

Planner inspection covered the source, regression cases and final CLI outputs. The old-error/clean-edit and old/new-error examples both exit 1; warning-only exits 0; unavailable baseline exits 2 while preserving the current error and unknown introduction count. Frozen-blob and index audits tie the examples to the accepted seven files. The whole-tree done check correctly remained unmatched before cumulative validation; focused success was not reported as repository completion. Product evidence is under `executor/writing-compare/`, with all earlier attempts retained.

The cumulative check, published commit, Windows/Linux CI and exact installed-content comparison belong in `.awkit/handoffs/scoped-document-trial/delivery/validation.json`. The same executor handles delivery after planner record and rendered-output review, preserving the owner's identity and existing Python. Further report-use measurements and the presentation trial remain separate work; this unit adds no broader task automation.
