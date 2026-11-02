# Evidence

Where check results and task evidence live in a clone of this repository, and how to cite them. The current state of work is in the [roadmap](roadmap.md); decisions are in [design](design.md).

## Where evidence lives

| Store | Contents |
|---|---|
| `.awkit/reviews/review-*/` | Frozen snapshot results, command logs and artifacts from `awkit review check`. Match the snapshot and check scope before citing a pass. A `running` status can be an interrupted record. |
| `.awkit/handoffs/<collection>/` | Task receipts, input versions, fixtures and reviews. A collection can serve several tasks; cite the exact file. |
| `.awkit/workspaces/<name>/.awkit/` | Evidence kept from a task checkout. Check the folder's actual state before cleaning it up. |
| `.awkit/sessions/` and channel databases | Session and collaboration state. Not evidence. |
| Git history | Commits, CI runs and the task records that existed before `2ef5040`. Use `git log -S` to find when a decision or result was recorded. |

All `.awkit/` stores are ignored by Git and exist only in the clone that produced them. A fresh clone has none of them. CI runs on GitHub are the evidence that survives.

Run `python scripts/evidence_catalog.py` to list the local collections with their sizes, the review runs with their recorded status, and which documents reference them. It writes `.awkit/evidence/index.md` and `catalog.json`, both ignored. It reads; it never moves or deletes evidence.

## Citing a result

Name the snapshot or commit, the command, the environment, the result and the run folder. Keep failed and interrupted runs beside the passing one and say why the later run differs. A passing check establishes what it checked, not document quality or saved effort.

## Retention

Keep accepted artifacts, manifests and failures. Do not move review runs into subfolders: completion lookup reads `review-*/result.json` directly. Before deleting a checkout, confirm it is clean and merged and remove its worktree registration. An unreferenced collection is a candidate for review, not permission to delete it.
