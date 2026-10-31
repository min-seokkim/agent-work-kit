# Development

Start here to resume work on Agent Work Kit. The selected implementations are [channel wait sleep prevention](tasks/channel-keep-awake.md) and the [storage summary view](tasks/review-storage.md#summary-view). Their task records share one cumulative delivery receipt. Root continues product planning while a separate session implements and checks the changes.

[Review preparation failure evidence](tasks/review-preparation-failures.md) was delivered in `9fa9a2a`, including corrected Windows CI assertions and the recovery guide; its record owns the completed checks and exact installation. [Artifact selection preview](tasks/artifact-selection-preview.md) was delivered in `83db970`, with passing Windows/Linux CI, exact installation and authorized read-only use. The owner-approved current-manuscript collection repair was then applied in the target project. [Shared artifact storage](tasks/shared-artifact-storage.md) was delivered in `ac10928`, and the target now uses it for new runs. Initial runs used near-identical content; the [adoption comparison](tasks/shared-artifact-storage.md#adoption-after-technical-delivery) has not measured storage growth and retrieval for the next needed essay continuation. No such task or owning session is selected, and broader evidence and retrieval requirements remain open. Read the relevant task's next action and evidence before repeating a check, push or installation. The [roadmap](roadmap.md) retains broader unfinished outcomes.

## Resume a task

1. Read the current request and [repository rules](../AGENTS.md). Check `git status --short --branch`, the base revision and installation alignment; preserve another session's changes.
2. Open the assigned record in [the task directory](tasks/README.md). Read its current status, next action and resume inputs. Confirm ownership and scope before editing. Historical assignments do not transfer ownership.
3. Follow the named contract or receipt. [Evidence](evidence.md) explains where checks, artifacts and local handoffs live and how to rebuild their task index. A missing local receipt means the evidence is unavailable in this clone.
4. Update the owning task record while working. Check the frozen result and complete the repository's CI and installation requirements before reporting delivery.

## Document ownership

| Question | Owning document |
|---|---|
| What is assigned, what happened and what happens next? | One current record in [tasks](tasks/README.md) |
| Which unfinished outcome could be selected? | [Roadmap](roadmap.md) |
| Which decisions and constraints must the change preserve? | [Design](design.md) and the task's named contract |
| Where is the evidence, and what does it establish? | The task's receipt and [evidence guide](evidence.md) |
| How was an earlier decision or result reached? | [History](history/README.md), opened only as needed |
| How is a checked change or release delivered? | [Release](release.md) and [AGENTS.md](../AGENTS.md) |
| How do users operate the product? | The shipped [kit](../kit/README.md); behavior changes go in [CHANGELOG](../CHANGELOG.md) |

## Current state

Version 0.3.0 remains unreleased. Each task's receipt identifies its published commit, checks, CI and installation rather than treating an older planning baseline as the current product. Shipped behavior is described in the [command reference](../kit/reference.md) and [session guide](../kit/sessions.md). The task directory distinguishes delivered units from unverified broader outcomes.

## Maintaining records

Keep the current conclusion and next action in one task record. Link requirements and evidence rather than copying their narrative. On completion, record the bounded result, the receipt and remaining limits; the next task should not reread a completed execution log. Move superseded narrative into history with its source revision and rebase incoming links. Keep accepted contracts reachable from the current record.

The [evidence guide](evidence.md#retention) defines retention and cleanup. Raw check records retain their paths; failed and incomplete runs remain visible. Historical statuses describe their source revision, and are never a fresh assignment.

## Earlier entry links

<a id="scope"></a><a id="decisions"></a><a id="next-work"></a><a id="independent-session-collaboration-plan"></a><a id="current-local-collaboration-trial"></a><a id="using-awkit-in-the-coordinator-session"></a><a id="measurement-record"></a><a id="release"></a><a id="testing-and-building"></a><a id="verification-record"></a><a id="document-map"></a><a id="rules-for-working-in-this-repository"></a>

[The prior development entry](history/development.md) preserves its capability summary and older navigation. Use the document ownership table above for current work.
