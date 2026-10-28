# Shared artifact storage

Use this reference when repeated checks retain large identical artifacts or when moving review evidence. Start with `awkit review storage` to inspect existing logical sizes. Storage selection changes future checks; it does not reduce existing copied history.

## Select storage for new runs

Set `artifact_storage = "shared"` at the top level of the check configuration. Omit the key or use `"copy"` for ordinary per-run copies. Unsupported values fail before execution. There is no separate command-line storage override.

Shared runs keep configured payloads under the collection's `.awkit-artifacts/objects/`, addressed by SHA-256. Identical bytes share one object within that collection; each run retains its own result, configuration, logs and artifact declarations. The store descriptor records its format and collection identity. Copy mode and existing schema-1 runs remain readable.

Before opting a project in, check tools that directly open configured payloads under `run/artifacts/`. Those consumers need ordinary copied or exported files; updating awkit's readers does not change an external tool's file access.

Shared artifact paths must be portable between Windows and Linux. Traversal, reserved Windows names such as `aux.log`, ambiguous separators and colliding case aliases fail collection. Check naming before opting in; copied mode retains its legacy path behavior.

The schema-2 manifest at `artifacts/manifest.json` records configured object references and direct artifact diagnostics. The result records the selected mode and publication state. Payloads are published before the manifest, and completed publication is recorded last. Missing, corrupt, inconsistent or incomplete shared evidence fails verification or materialization. A failed check can still have complete, verifiable artifacts: integrity does not establish that the check passed.

Payload validation currently reads whole files into memory. Shared publication can hold the input and its verification copy at once; choose artifact sizes that fit the check host's available memory.

Prevents: F2, F16, F17.

## Direct output and materialization

Checks may write ordinary diagnostics under `AWKIT_RUN_DIR`. Non-colliding files under `artifacts/` are declared and hash-verified as local diagnostics; they are not silently turned into configured artifacts. Added-artifact comparison lists these declared paths without reading added payloads. Other direct diagnostics remain ordinary run files.

A path that collides with the managed manifest or a configured artifact records a failed run and incomplete publication, identifies the colliding paths and preserves the direct bytes. Resolve the check's output naming before running again. Interrupted collection retains incomplete evidence and does not repair or replace existing objects.

`review verify` verifies shared payloads and declared local diagnostics. `review compare --run RUN --diff` reads validated payload bytes; a broken reference reports `integrity-error` and produces no diff from unverified bytes. `review accept` produces independent ordinary configured artifacts. Editing an accepted file cannot alter a stored object or another run.

For either storage mode, generated files absent from the working tree show `missing` with a note; compare with `--run` to read retained outputs. Hash equality establishes unchanged bytes, not correctness. `--include-added` requires `--run` and adds an `added_artifacts` inventory with source and scope. It excludes unrecorded paths, reads no added content and adds no diffs. Invalid or unavailable inventory exits 2. Additions leave `unchanged` and exits 0/1 determined by accepted files; omitting the flag retains default output.

Prevents: F7, F16.

## Export

Run `awkit review export RUN --output DEST` with a destination that does not exist. The bundle contains ordinary artifact files, configuration, logs and direct run diagnostics. It excludes the retained worktree. Export verifies the bytes it materializes, refuses existing destinations and reserved provenance-path collisions, and preserves its source.

The exported schema-1 manifest declares all exported artifact files, including local diagnostics. Rewritten `result.json` describes this copied representation and retains the original logical run ID, snapshot, configuration hash, subdirectory and check outcome. `.awkit-export/` preserves the original result and manifest byte-for-byte and records their association with the rewritten metadata. Provenance distinguishes configured artifacts from local diagnostics.

A completed copied run with no artifact patterns can be exported with its configuration and logs. When that run originally had no manifest, provenance records the absence explicitly; the export's empty schema-1 manifest describes the new bundle.

Use a completed export for independent storage or a reader downgrade. Healthy exports support schema-1 artifact verification with older awkit readers. Compatibility does not mean an old reader detects every damaged or interrupted bundle. Current readers validate export provenance; an interrupted export is incomplete and must not be reported as a completed copy.

Prevents: F7, F16, F17.

## Move and inspect a collection

Move the collection with its `.awkit-artifacts/` directory to preserve shared verification without the original project path. Copying a complete collection may retain its identity; the identity represents compatible store lineage, not a unique physical location. Copies may diverge independently. A lone reference-based run cannot reconstruct its missing store by searching other paths.

`review storage` reports run-local bytes, shared object bytes counted once, per-run referenced logical bytes and total observed collection bytes. Staging and unreferenced object bytes are separate. Invalid or unreadable manifests limit reference coverage, so unreferenced does not establish reclaimable space. These are live logical sizes, not allocated disk use or measured savings.

Deleting a run does not generally reclaim its shared objects. Switching future runs back to `"copy"` leaves prior shared runs dependent on a compatible reader and store; export those runs independently before removing that dependency. This unit performs no migration or collection. Source Git snapshot lifetime also remains separate from retained artifact integrity.

Prevents: F6, F7, F16.
