# Review storage inspection

## Current status

The selected additive [summary view](#summary-view) is implemented with passing focused checks. It shares a cumulative frozen-check and delivery receipt with [channel wait sleep prevention](channel-keep-awake.md): `.awkit/handoffs/channel-keep-awake/implementation.json`. Root owns both contracts; the implementation session owns checks and delivery. Read that receipt for completed and pending stages before repeating work.

### Original inspection

The bounded command is implemented. The owner delegated subsequent product selection while retaining root as planning coordinator. The coordinator selected read-only storage inspection after an independent upfront assessment. `storage_implementation` owns checks and delivery; root owns scope. The preceding session-status receipt now records its successful CI, exact installation and source/kit/skill alignment.

Next action: consume `.awkit/handoffs/review-storage/implementation/delivery.json` for the frozen check, CI and exact-installation stages before repeating execution work. The receipt also owns focused checks, document inspection and the read-only real-store trial. Intended-user acceptance remains unverified.

## Evidence and selection

The source baseline is `0953a627`. A read-only observation of one real project's 147 review runs found 2,553,783,089 logical bytes, including 2,541,686,655 bytes under artifact directories and no retained worktrees. There were 115 passed and 32 failed runs. Existing manifests declared 2,534,187,591 payload bytes; grouping their recorded hashes once gave 111,887,223 bytes. Payload hashes were not independently revalidated, and these figures do not measure allocated disk space or tested migration savings. The private receipt is `.awkit/handoffs/scope-input/storage-assessment.json`.

Current collection writes selected artifacts separately for each run. Broad collection patterns in the observed project repeatedly retained unchanged outputs. Normal completion removes temporary worktrees. This supports an inventory and a later storage design; it does not establish that every project copies its entire source tree permanently.

The independent assessment rejected immediate hardlink deduplication because a later file edit can alter several runs. Existing verify, accept, compare and external evidence readers consume ordinary artifact paths. A shared-object format or filesystem-specific copy mechanism needs its own compatibility and failure contract.

## Selected command and acceptance

Extend `review` with `awkit review storage [--runs-root DIR] [--json]`. Inspect only direct `review-*` directories under the selected store. Report observed logical bytes by run and category, recorded statuses, largest runs, metadata coverage and inspection errors. Keep filesystem totals separate from manifest-declared payload, unique-hash and duplicate-declaration estimates. Label recorded hashes as unverified and the walk as non-atomic.

The command never initializes a project, writes evidence, removes files or follows linked descendants. A missing default store returns an absent report without creating it; an explicit missing or unreadable root is an invocation error. Validate manifest identities and declarations before using them. Conflicting sizes for one hash invalidate that hash's whole estimate. Preserve observed sizes when metadata is invalid, and disclose incomplete coverage. Existing result and manifest formats remain unchanged.

Acceptance covers duplicate hashes, distinct equal-sized payloads, malformed or foreign metadata, missing manifests, unexpected files, all run statuses, permission and disappearance errors, symlinks and Windows reparse points, deterministic output, exit semantics and unchanged filesystem/Git state. Complete inspection exits 0, partial inspection 1, and root or invocation failure 2. Failed review statuses alone do not fail inspection. Existing F6 and F7 supply the measurement and no-mutation requirements; no new failure entry is assigned.

## Follow-up decisions

### Summary view

Planning review `M-026/R-014/R-015`, settled in `M-029`, selected `review storage --summary`. The committed target adoption record reports that individual issues obscured the overview. A synthetic partial/shared formatter report contained 127 issue lines among 165 total lines, separating inspection status from limitations by 160 lines. This does not reproduce the original invocation or reading client. Although 126 missing-artifact records match the count of authorized folder removals, exact per-run correspondence and causes remain unverified.

The summary preserves root, inspection status, run count, logical sizes, recorded statuses, category totals, shared-store descriptor and reference coverage, the unreferenced-object warning, metadata coverage, all four payload estimates and every limitation. It omits only per-run shared-reference rows, largest-run rows and individual issue details, with counts and a route to default output or JSON. Issue counts group classifications by scope and code; unique affected-run counts apply only to run-scoped issues.

Default text remains byte-for-byte compatible for identical reports, schema-2 JSON remains complete, and inspection/status/exit behavior is unchanged. `--summary` and `--json` are mutually exclusive. The feature establishes no faster scan, common cause, permanent removal, cleanup authorization or target configuration change. Validation uses synthetic fixtures; no new target scan is part of this unit.

The cumulative receipt retains the baseline default-output comparison, focused summary and CLI checks, documentation inspection, independent review, frozen check and delivery stages. Read it before repeating a completed stage. The historical inspection receipt above remains separate.

### Broader storage choices

After inspection is delivered, evaluate shared immutable payloads, compatible materialization, concurrent insertion, corruption detection, migration rollback and reference-aware collection. Keep per-run provenance and failed attempts even when payloads are shared. Retention expiry, automatic deletion, real-store migration and changes to another project's collection configuration remain separate decisions. Preserve accepted and unresolved-failure evidence.

Inspection runs on demand. Background tracking, scheduled rechecks and automatic cleanup are not selected. Keep necessary final and unresolved verification evidence under the existing retention policy; a storage report creates no additional record obligation.

The broader [roadmap](../roadmap.md) also retains two-environment continuation and shared-context discovery. Their existence does not expand this implementation unit. Root will consume the implementation receipt and choose subsequent scope without repeating its execution checks.
