# Evidence

Find evidence through the [owning task](tasks/README.md). Its current record names the conclusion, relevant historical section and local collections; the exact receipt identifies the checked revision and what passed. The [historical evidence record](history/evidence.md) preserves earlier measurements and their limits.

## Local catalogue

Run `python scripts/evidence_catalog.py` from the repository root. It writes `.awkit/evidence/index.md` for reading and `.awkit/evidence/catalog.json` for lookup. Both are local, ignored outputs. Regenerate after adding evidence or changing references; each output records the checkout revision and document hashes it read.

The catalogue groups collections and standalone evidence files by references in current and historical development documents. It lists shared collections, collections without a document reference, missing locations and inspection errors. References establish a relationship, not ownership or acceptance. The tool reads review `result.json` status fields but does not rerun checks or infer whether a process is alive. It never follows directory links, copies source material or modifies evidence.

| Store | Contents and interpretation |
|---|---|
| `.awkit/reviews/review-*/` | Frozen snapshot results, command logs and artifacts. Match the snapshot and check scope before citing a pass. `running` can be an interrupted historical record. |
| `.awkit/handoffs/<collection>/` | Task receipts, input versions, fixtures, reviews and rendered previews. Some collections serve several tasks; cite the exact file and version. |
| `.awkit/workspaces/<name>/.awkit/` | Evidence retained from a task checkout. Some outer folders contain only evidence; others are working repositories. Check actual state before cleanup. |
| `.awkit/sessions/` and channel databases | Operational session and collaboration state. They stay in their current locations and outside the catalogue's content scan. |
| `docs/history/` | Versioned explanations, decisions, measurements and evidence references. These are historical records, not raw run artifacts. |

## Recording a result

Record the source revision or snapshot, command and environment, result, evidence location and remaining limits in the task's receipt. Separate implementation, local checks, rendered inspection, CI, installation and human acceptance. Link one receipt from the task instead of copying every run into a central narrative. Keep retry attempts with the final result and explain why the new run differs.

For real-use measurements, preserve task boundaries, counting units and unknown values. The [earlier measurement table](history/evidence.md#measurement-record) defines the observations already collected; its figures remain historical. A hook firing or a passing test alone does not establish prevented failures or saved user effort.

## Retention

Preserve accepted artifacts, their manifests, source identities, failures and incomplete attempts. Keep baseline and candidate fixtures distinct even when files are identical. Do not move review runs into task subfolders: completion lookup reads direct `review-*/result.json` paths, and receipts can contain absolute locations.

Before deleting a checkout, verify that it is clean and merged, retain its evidence, and remove its worktree registration safely. Dirty or unclassified workspaces stay untouched. Regenerable caches and inactive preview profiles can be removed after checking their use. An unreferenced collection is a review candidate, not permission to delete it.

The local cleanup receipt `.awkit/handoffs/documentation-restructure/local-cleanup.json` records the earlier deletion and preservation checks. This restructuring retains the raw stores in place; it changes how agents locate and interpret them.

## Earlier sections

<a id="documentation-restructuring"></a><a id="profile-and-role-examples"></a><a id="completed-work"></a><a id="measurement-record"></a><a id="verification-record"></a><a id="managed-session-first-use-path"></a><a id="managed-conversation-recovery"></a><a id="optional-persistent-claude-observations"></a><a id="earlier-development-overview"></a>

[Earlier milestones, measurements and verification](history/evidence.md) retain every prior section and qualification from `90e2557`.
