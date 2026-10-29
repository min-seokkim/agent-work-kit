# Artifact selection preview

## Current status

Delivered in `83db9707d5ccdc0baad4344e116b0e888130c401`, from source baseline `81f281d`. [CI run 40825634756](https://github.com/min-seokkim/agent-work-kit/actions/runs/40825634756) passed all 21 Windows/Linux jobs, followed by exact-commit installation and source, kit and user-skill alignment. Independent code review accepted final corrected snapshot `6b3c0533206794121e7542d191d5b3a34c427f13`. Root owns scope, acceptance and planning documents; `storage_builder` owns source, tests, shipped guidance, technical checks and delivery. The owner attached Claude for planning collaboration on `.awkit/review-planning-2.sqlite3`; its judgment is separate from technical acceptance. The preceding shared-storage channel remains closed.

Implementation began before the owner attached this planning channel. Its first review therefore assesses work already in progress and was not an upfront approval. The reviewer identifies as Claude Code, configured as Opus 5.5; execution-log confirmation remains unavailable. The builder proposed the enumeration mechanism; root owns the required safety, compatibility and coverage semantics. Review findings and their dispositions belong in the delivery receipt.

The local `.awkit/handoffs/artifact-selection-preview/delivery.json` retains the frozen checks, failed first CI, correction, publication, installation and authorized installed-use evidence. The published commit and successful CI above establish the completed feature boundary without requiring these private records. The receipt and `technical-review.md` beside it are ignored and unavailable in a fresh clone. A later documentation-only delivery has its own stages in the receipt and does not replace this source-feature boundary.

Next planning action: present the prepared current-manuscript collection proposal in `.awkit/handoffs/shared-artifact-storage/adoption-preparation.md` for owner approval. It preserves existing requirements, check commands and copied storage while naming the proposed additional outputs. Only read-only target observation and local metadata recording are authorized so far. Configuration changes, shared-storage adoption and historical recovery remain separate decisions.

## Intended result and reason

A project can inspect which existing files its check configuration would select without executing checks or creating another evidence collection. The preview reports the configured union, current logical bytes and selection limits before the owner considers a configuration change.

The observed high-volume project's current checks read manuscripts absent from its collection patterns. Existing `review storage` reports retained runs, while collection occurs after check execution and writes payloads. Neither exposes current configuration selection before a run. The omission was established by reading the configuration and task requirements; the new command makes that inspection repeatable. It cannot determine which unselected files a task needs. The private source remains in the [shared-storage adoption preparation](shared-artifact-storage.md#adoption-after-technical-delivery).

This supports storage adoption. A bounded collection-maintenance continuation is proposed; broader task evidence and retrieval needs remain undecided. A target-project session is the proposed applying owner after approval and an ownership check. The target configuration and retained records are unchanged.

## Selected contract

`awkit review [--repo DIR] preview --config PATH [--json]` observes the current working folder before setup and checks. It takes no revision argument and creates no snapshot. Configuration identity includes the exact configuration hash; the result identifies the observed base folder and configured storage mode.

Resolve the explicitly supplied base once to its canonical folder, including an old project path reached through a junction or linked ancestor. Report that canonical base. The restriction on linked descendants applies within it; an intentionally supplied project alias is not an unrequested traversal target. Resolve and identify the explicitly supplied configuration consistently.

- Select the union of `artifacts` and `required_artifacts`, deduplicate the selected files and retain pattern associations. Report sorted relative paths, file sizes, unique logical-byte totals and each pattern's matches. Report unmatched optional and required patterns, skipped paths and observation errors separately.
- JSON contains the full observed selection and pattern associations. Default text shows the summary, pattern counts and at most 20 largest selected files, with the displayed/total count and the route to full JSON. Coverage limitations remain explicit.
- Preserve existing collection behavior. A complete preview must match collection selection on the same ordinary portable tree, including wildcard and platform case behavior. Reuse candidate filtering; the builder chooses the traversal mechanism. If safe observation cannot reproduce copied selection, including linked/reparse branches or nonportable names allowed by copied mode, identify the affected path and report partial coverage. Partial totals describe only the observed subset and are not the collector's full selection.
- Read metadata without hashing artifact contents. Do not execute configured commands, create worktrees, run folders or stores, or change Git state and local excludes. Do not traverse linked descendants or access paths outside the selected base. If safe observation cannot reproduce a collector behavior, disclose the limit and settle the discrepancy before claiming parity.
- State that the output covers files currently present. Setup and checks may generate or change artifacts, and the current tree can contain files absent from a later snapshot. Missing current required matches do not predict a future check failure. An empty missing-required list does not establish evidence completeness, consumer compatibility or storage savings.
- This is a live metadata observation, not an atomic tree snapshot. Concurrent additions or changes may be missed. Complete coverage means no selection limitation or observation error was detected; it does not certify that the tree stayed unchanged. Detected unsafe branch or identity changes still require partial coverage.
- Exit 0 for a complete observation, including currently unmatched required patterns. Exit 1 for any partial coverage, including unobserved linked branches, unsupported names, enumeration errors or metadata errors; exit 2 for invalid invocation, configuration or base. Known collector exclusions remain visible and do not by themselves make coverage partial. Machine output has an explicit schema version and preserves these distinctions.

The preview neither estimates content sharing nor measures allocated disk space. Existing storage inspection and post-check artifact verification keep those separate roles. There is no automatic configuration rewrite or new retention policy.

The technical assessment found that copied collection can retain regular files reached through an internal Windows junction and can accept nonportable POSIX names. Replacing both collectors with stricter traversal would change retained outputs and missing-required outcomes. Collector traversal before filtering remains a separate compatibility and safety question. Any later unification must explicitly settle those existing behaviors; this read-only unit does not silently change them.

## Scope and acceptance

Implementation owns the selection helper, the two collectors, CLI wiring, focused tests, CHANGELOG and the narrow shipped command guidance. Root owns this record and the relevant design, roadmap, development and task-directory entries.

Acceptance requires:

1. Existing optional/required union, deduplication, subdirectory behavior and mode-specific selection produce matching preview and collection results on unchanged ordinary portable files. Pattern recursion and platform case behavior are included. Unsafe traversal or naming differences are disclosed as partial coverage.
2. Invalid configuration is rejected without running its commands. Unmatched patterns, duplicate matches, missing files, metadata errors and skipped unsafe paths retain distinct meanings in text, JSON and exit status.
3. Disposable cases establish that preview creates no run, worktree, Git mutation or artifact-content read. Linked/reparse descendants and outside paths remain safe on the supported platforms. An explicitly supplied project alias resolves to the same canonical base and ordinary selection as the collector; test a linked base or ancestor as well as descendant refusal.
4. A bounded read-only use of the observed project's current configuration shows its selection and allows an independently known omitted path to be checked against it. Record complete or partial coverage and name affected patterns/branches in the local receipt. A partial target observation does not satisfy this use acceptance. Private names and contents stay out of public fixtures. This use neither assigns its next task nor changes its configuration.
5. The independent reviewer examines collector regression risk and the limits of the observation. The builder completes the repository's frozen check, CI and installation requirements, retaining failures and explaining any retries in the single receipt.

Use existing tests where they establish behavior; add regression cases for the new interface and shared selector. Do not repeat full checks without a changed input or an unresolved failure.

## Review and use evidence

The first independent technical review found that Windows Unicode wildcard matching could omit selected files, a replaced descendant could escape anchored metadata checks, and repeated resolution of a supplied alias could mix project identities. The reviewer independently verified their corrections on Windows and Linux and established no additional actionable finding. The original failures and corrected results remain in the receipt and technical review.

The first publication, `c043389`, passed its frozen local check but failed the Windows Python 3.12 job in [CI run 40821724461](https://github.com/min-seokkim/agent-work-kit/actions/runs/40821724461): preview and collection returned different spelling for a literal filename. Root reassessed the stop rule and selected one bounded compatibility correction instead of leaving a known failure on the install source. Independent review accepted corrected snapshot `6b3c0533206794121e7542d191d5b3a34c427f13`; its fresh frozen check passed Ruff and all 680 executed tests, with 24 skipped. The initial failure remains part of the evidence.

The authorized observation with the installed `83db970` returned complete coverage for both the target's existing configuration and the proposed maintenance configuration. The candidate included the independently identified omitted path and current manuscript set. The private receipt retains counts, logical bytes and the distinction between current-tree selection and the longer candidate configuration. No target artifact payloads were read or hashed by preview, and no target change was made. This verifies the observation tool's use; it does not establish adoption or storage reduction.
