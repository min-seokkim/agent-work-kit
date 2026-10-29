# Shared artifact storage

## Current status

Delivered in `ac10928d02a937f6d3fda4c30643059873b6f900`, from source baseline `f167f42`. [CI run 40718629526](https://github.com/min-seokkim/agent-work-kit/actions/runs/40718629526) passed all 21 Windows/Linux jobs, followed by exact-commit installation and source, kit and user-skill alignment. The preceding [storage inspection](review-storage.md) remains a separate delivered unit. Root owns product scope, planning decisions and the planning-review channel. `storage_implementation` owns implementation coordination, technical diagnosis, checks, code-review arrangements and delivery. The unit is high risk because it changes persistent evidence formats and concurrent writes.

The attached Claude Code reviewer (owner-assigned Opus 5.5) covers planning only on `.awkit/review-shared-artifact-storage.sqlite3`. Earlier code observations, the interrupted check and model-verification limits are retained in the delivery receipt; none establishes cumulative code acceptance.

The core, export and inventory portions passed independent cumulative code review and frozen check `767f5a7`: Ruff passed, with 663 of 683 tests passing and 20 skipped. The receipt retains the corrected findings and separate delivery stages. Planning review accepted the outcome in `R-011`; its acceptance is distinct from code judgment.

Next action: present the concrete current-manuscript collection proposal in `.awkit/handoffs/shared-artifact-storage/adoption-preparation.md` for owner approval. [Artifact selection preview](artifact-selection-preview.md) supports that comparison. The proposal preserves existing collection requirements, check commands and copied mode; it does not settle broader task evidence or retrieval needs. Only read-only target observation and local metadata recording are authorized. Follow [Adoption after technical delivery](#adoption-after-technical-delivery) before a storage-format change; existing history is unchanged and real-use reduction remains unverified.

Detailed review and execution evidence is in the local `.awkit/handoffs/shared-artifact-storage/implementation/delivery.json`; the channel is its archive. These ignored files are unavailable in a fresh clone. The published commit and CI above establish the completed feature boundary without requiring those local records.

### Implementation portions and ownership

`M-005` changed the earlier serial sequence: non-overlapping export and inventory work began before corrected-core acceptance to use the available session window. Review order does not imply implementation began after the preceding review. Root selected bounded scopes; `storage_implementation` directs contributors, owns file coordination and integrates the result. Contributors must use the corrected core and do not supply independent judgment on their own changes.

| Portion | Implementation owner and files | Technical boundary |
|---|---|---|
| Publication and core readers | `storage_implementation`: `src/awkit/artifact_store.py`, `src/awkit/review.py`, `tests/test_shared_artifacts.py` | Included in cumulative acceptance `767f5a7` and delivery `ac10928` |
| Portable export | `shared_storage_research`, acting as an implementation contributor: `src/awkit/review_export.py`, export wiring in `src/awkit/cli.py`, `tests/test_review_export.py` | Included in cumulative acceptance `767f5a7` and delivery `ac10928` |
| Inventory | `storage_assessment`, acting as an implementation contributor: `src/awkit/review_storage.py`, `tests/test_review_storage.py` | Included in cumulative acceptance `767f5a7` and delivery `ac10928` |

The primary implementer owns shipped guidance, integration, technical review requests, delivery and the local receipt. At a session cutoff, save a consistent working tree and list reviewed, unreviewed and unfinished portions there. Do not start a Git, CI or installation sequence that cannot finish within the available window.

## Desired result

Repeated checks can reference one stored copy of identical configured artifact content while retaining each run's own source identity, configuration, status, logs and artifact associations. Select shared storage explicitly for new runs. The existing copied mode remains the default, and existing runs remain readable and unchanged. The [inspection record](review-storage.md#evidence-and-selection) owns the real-use measurements and their limits.

The selected backend is a SHA-256 payload store colocated with the chosen review collection, including an explicitly selected external collection. The store owns a versioned descriptor and collection identity. This preserves collection portability without depending on an originating Git database. A Git-backed alternative would require artifact-tree ownership, binary access, reference lifetime and portable object-database handling; no benefit sufficient to require that extra dependency was established by the source assessment.

Payload sharing does not establish source-snapshot retention or full reproducibility. Git snapshot lifetime remains separate work. Existing snapshots cannot substitute for artifacts generated or changed during checks.

## Selected product contract

| Surface | Selected behavior |
|---|---|
| Creation | Set `artifact_storage = "shared"` in the checks TOML to opt into new shared runs; absence or `"copy"` retains copied storage. There is no parallel CLI override in this unit. Reject unsupported values before execution and record the actual mode. Store configured post-check artifact bytes once per content hash; keep run identities, results and logs separate. |
| Format | Preserve legacy schema-1 reads. Shared runs use schema-2 manifests at the existing manifest location and declare their collection identity; the collection descriptor has its own version. Updated readers require the declared manifest and store; unknown, inconsistent or missing storage fails explicitly. |
| Verification and comparison | Use one format-aware artifact reader for verify, accept and comparison, including diff and added-artifact handling. Added artifacts include declared local diagnostics, preserving the existing result meaning. Integrity failures have a distinct failing result and produce no diff from unverified bytes. Preserve the distinction between artifact integrity and the stored check's passed/failed status. |
| Acceptance | Continue producing independent ordinary accepted files. A change to a materialized or accepted file cannot change a stored object or another run's evidence. |
| Export | Add an explicit `review export RUN --output DEST` operation. The destination must not exist. Export an independent bundle of ordinary artifact files, run metadata, configuration, logs and direct run diagnostics; exclude retained worktrees. The export identity rules below define rewritten metadata and preserved originals. A healthy completed export supports legacy schema-1 artifact verification as well as current readers. |
| Direct run output | Keep direct run output as ordinary local evidence. Non-colliding files written under `artifacts/` are declared as local diagnostics in the schema-2 manifest and hash-verified. A managed-namespace or logical artifact-path collision records a completed failed outcome and incomplete artifact publication identifying the colliding paths; preserve the diagnostic bytes. It is not an interrupted or uncertain outcome. Complete exports declare these files in the schema-1 artifact inventory. |
| Portability | Resolve shared payloads using the selected collection and its identity, without guessing absolute source paths or searching repositories. Moving a complete collection preserves artifact verification. Copying a complete collection may retain its collection ID: the ID binds a run to compatible store lineage, not to a globally unique location. Copies may diverge; no discovery or merge is implied. A reference-only run without its collection reports the missing store; export removes that dependency. |
| Inspection | Count shared object bytes once and run-local bytes separately, with referenced logical payload bytes per run. Report object bytes unreferenced by valid readable manifests separately, along with coverage limits when manifests cannot be read or validated. These are not proven reclaimable bytes. Preserve existing field meanings or explicitly version changed structured semantics. Hash estimates remain separate from verified integrity and allocated space. |

Legacy verification can reject a healthy schema-2 manifest while plain old comparison and completion lookup do not establish shared-artifact integrity. The old storage inspector selects only `review-*` folders and omits shared-store bytes. Old binaries cannot be promised to detect every corruption or loss of metadata. Updated readers must recognize incomplete publication and reject it as incomplete evidence. Export compatibility covers complete healthy bundles, not arbitrary damaged copies.

### Export identity and diagnostics

An export retains the original logical run identity, source snapshot, configuration hash, subdirectory and check outcome. Its top-level `result.json` is rewritten to describe the materialized copied representation, and its artifact-publication manifest hash describes the exported schema-1 manifest. It is not a verbatim copy of the shared run result.

Keep the original result and schema-2 manifest byte-for-byte outside `artifacts/`, under export provenance, together with their hashes and an explicit mapping to the rewritten result and manifest. Record export provenance separately from the original check. A reserved provenance-name collision is an explicit export failure; never silently overwrite or relocate existing diagnostic evidence.

The exported schema-1 manifest declares every file under exported `artifacts/`, including non-colliding direct diagnostics. Preserve their original diagnostic versus configured-artifact association in provenance. A failed check can have complete artifact publication and retain that failed outcome in an export. A collision or interrupted/incomplete artifact publication cannot verify or export as a complete bundle; the original diagnostic bytes remain available in the run.

Deleting a shared run does not generally reclaim its object bytes; objects remain until separately authorized collection. State this beside the shared-storage configuration in the command guide. No collector is included here.

## Integrity and ownership requirements

Derive object locations from validated content identifiers under the owned collection. Do not trust arbitrary filesystem paths from manifests, follow linked/reparse descendants outside the selected store, or replace unrelated files. Existing local-state exclusion and explicit output ownership requirements still apply.

Verify an existing object's size and hash before reusing it, and verify bytes when reading them for integrity or materialization. Concurrent writers must not expose partial objects or overwrite a conflicting object. Publish completed evidence only after its required payloads are available. Interrupted attempts remain identifiable; staged files and unreferenced objects do not become accepted evidence merely because they exist.

Ordinary hardlinks are not an immutability mechanism: writing one materialized file must not alter several runs. Missing or corrupt payloads fail visibly. Neither interrupted writes nor corruption may cause automatic deletion, replacement from an unverified source or a successful empty result.

Preserve all existing failure and incomplete-run meanings. Keep required final and unresolved verification evidence under the existing tool retention policy. Inspection, routine conversation and session completion create no new recording obligation.

## Acceptance before delivery

- Two new runs with identical generated bytes retain distinct records and share one stored payload. Changed bytes remain distinct. Measure actual stored logical bytes and metadata overhead on disposable representative fixtures, plus memory and elapsed time with a large artifact; do not infer allocated savings or performance from hash counts.
- Legacy runs still verify, compare and become accepted versions. Shared runs support comparison, diff and added-artifact behavior with the same result meanings. Acceptance and export create independent ordinary files.
- A moved complete collection and a self-contained exported run verify without the original project path. A lone reference-based run, missing object, corrupt object, unsupported format and inconsistent identity fail explicitly. Healthy exports are checked with the preceding reader from `f167f42` as well as the new reader.
- Concurrent processes and injected interruptions preserve completed runs and never publish incomplete evidence as valid. Test shared writers against each other and relevant existing readers or writers. Exercise unsafe paths, symlinks/reparse points and managed-output collisions.
- Direct run diagnostics survive collection and export. A retained worktree is excluded from export. An existing export destination is refused before its contents are changed.
- Storage inspection reports shared bytes and per-run references without double-counting, and retains clear partial-coverage reporting.
- Add the behavior entry to CHANGELOG, document `artifact_storage` and `review export` in `kit/reference.md`, declare the command's applicable `PREVENTS` entries and regenerate the guard map with `python scripts/guard_map.py --write`.
- Ship the writer only with all affected readers, export/materialization and inspection support. Complete a frozen integration check, Windows/Linux CI, exact-commit installation and a disposable use trial. The implementer owns technical verification and names the independent cumulative code reviewer in the receipt. That reviewer must have authored none of the core, export or inventory changes. Root consumes their results and decides subsequent scope.

## Adoption after technical delivery

The next planned outcome is lower growth of new evidence in the observed high-volume project, identified by `inspected_project` in `.awkit/handoffs/scope-input/storage-assessment.json`. Resolve its current canonical path and task owner before preparing a change. Feature delivery, adoption and historical space recovery are separate results. Existing multi-gigabyte history remains unchanged, and no real-project configuration change is assigned within this implementation unit.

Use the implementation acceptance trial as format and measurement evidence; do not repeat it as another adoption gate. Its single 128 MiB sample observed about 1.9 times the main-process peak memory in shared mode. Record the target project's largest required artifact and judge that cost for its environment; the sample is not a general memory or throughput guarantee.

1. Attach the proposed pilot to the project's next needed continuation. Identify the artifact groups required by its acceptance and consumers, including direct filesystem consumers. Compare expected new bytes under current patterns copied, reviewed narrower patterns copied, and current patterns shared. Label estimates and unknown coverage. Narrower collection must preserve the same usable evidence; shared storage must preserve a usable copied or exported path for direct-file consumers. Prefer the least risky option that meets the stated growth goal. Owning a shared-storage feature does not select it for every project.
2. Prepare the named project's exact configuration diff, expected effect and rollback path. Obtain the owner's authorization for that concrete change before enabling it; reuse specific authorization already given for that project rather than asking again. This unit's planning authority does not authorize another project's format change. Apply the selected option only to new pilot runs after its reader/export prerequisites and active ownership are settled.
3. Record the observed storage increment and retrieval outcome in the project's existing task receipt, identifying its configuration, installed revision, workload and limits. Keep the copied baseline as the comparison. Tool delivery alone does not establish reduced growth in real use.
4. A failed adoption returns future runs to copied mode while retaining prior shared evidence. Existing shared runs still need their store and a compatible reader. Export them independently before removing that dependency or downgrading to a reader that cannot handle them. A configuration switch does not convert old runs.

Compare eligible options before approval, including evidence-preserving narrower copied selection estimated with preview. Measure shared growth only during the approved trial, with its rollback and named continuation fixed beforehand. Observe needed runs without rerunning unchanged checks for measurement. Include new objects and collection/run metadata, logs and local diagnostics; record needed exports separately and include them in the observed trial total. Show empty-store initialization and the number of observed runs. Calculate the copied counterfactual from the finalized manifest's configured-artifact logical bytes, adding observed local diagnostics, metadata and logs once. This is a calculated comparison, not an executed copied run's exact format-specific footprint. Neither side measures allocated disk space. Judge the named continuation's storage and retrieval result; one favorable reuse does not establish a general growth reduction.

A successful trial can justify that project's continued selected configuration. Global defaults and historical migration require separate decisions. Existing compatible consumers, evidence completeness and measured new growth take priority over adding more storage commands.

## Subsequent choices

A default-mode change, old-run migration, deletion, expiry, garbage collection, background monitoring and scheduled rechecks are not assigned. Real existing records are not migration fixtures, and another project's collection configuration is unchanged. Any later migration proposal must identify affected paths, demonstrate recovery and explain access changes. Keep two-environment continuation and shared-context discovery in the [roadmap](../roadmap.md); they do not expand this unit.
