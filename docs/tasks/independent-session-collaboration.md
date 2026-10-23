# Independent-session collaboration

Status: planned. The owner requested the outcome; implementation choices remain open. The coordinating session maintains this plan. See [roadmap item 11](../roadmap.md#next-work), the [design decision](../design.md#decisions) and the [local trial](local-collaboration.md).

## Independent-session collaboration plan

Independent-session coordination is a requested outcome, with the design still open. Roles depend on the work: examples include coordination, planning, research, implementation, testing, review and writing. Allow project-defined roles. Keep session identity separate from role and task: one session may hold several compatible roles, and several sessions may divide tasks within one role. An independent review still requires a separate session. Assign responsibilities, expected outputs, dependencies and file ownership per task, allowing parallel work on separate files and handoffs between roles.

Evaluate creating, attaching to and resuming independent sessions through the capabilities each chosen runtime exposes; subagents alone do not meet this request. Where automatic creation is unavailable, the user opens a session and gives it an initial connection instruction. Subsequent assignments and reports should travel through awkit, including between local and cloud environments once two actual environments are selected. Keep requests, receipt and completion states, checked revisions and results across interruptions. Completion requires a real task involving at least three distinct roles to pass through assignment, execution, verification and any correction without manual message relay after setup, with unresolved decisions returned to the user. The current local two-role channel implements only part of this scope; no session launcher or remote transport is implemented.

The owner reports that the current workflow works well. Preserve that working path. The broader scope above is a direction, not a requirement to implement every missing capability now. Sessions make judgments; awkit records requests, reviewed revisions, checks and outcomes. Collaboration across providers is an explicit requirement: the owner values their complementary behavior. Keep each session's context independent and exchange the task material needed; routine sharing of full transcripts would weaken independent review. The recorded local trial used two Codex workers, so it does not establish Claude/Codex interoperability.

Next validation work, before expanding the protocol:

1. Clarify existing command semantics: `post` confirms storage; `wait` returns matching messages; a reply records the sender's reported result. None alone proves successful task completion. Snapshot references remain optional and format-checked by the channel; review procedures supply stronger requirements.
2. Exercise interruption and replay: stop after reading but before replying, resume and find unanswered requests, then repeat a request after its result exists. Use request IDs to detect prior work. Check that cursor movement is not mistaken for processing and that retained results can prevent duplicate actions. These are planned checks, not new recovery guarantees.
3. Run a real task with independent Claude and Codex sessions using the current channel and snapshot workflow. Record the exact clients, versions, models and environments, manual relays or wakes, and interruption outcomes. Establish CLI, IDE and desktop behavior separately; record untested combinations as unverified.

## Lessons from the proposal trial

The [trial recorded with `89549b7`](workflow-review.md) completed assignment, frozen review, correction, checks and final receipt using the existing channel without either session editing the other's product files. The main and reviewer used Codex IDE and Desktop clients and were exposed to the implementation discussion. This supports the local two-role workflow; cross-provider operation, automatic wake-up, recovery after interruption and blinded review remain unverified. The reviewer's later account judged the channel sufficient for this task and reported procedure overhead for small edits.

Preserve this working path before expanding the protocol. Verify session identity from the active runtime when a handoff names an older session. Request judgments against snapshots; retain failed runs as well as corrected runs, classify environment failures separately from candidate defects, and reuse accepted evidence for unchanged content. In this trial, final review found a guide word-limit violation while a separate run failed because Ruff was absent from PATH. They require different corrections.

At closure, confirm the delivered tree equals the checked tree and obtain the recipient's acknowledgement before sending `close`, which prevents further posts. Check for unanswered requests and disclose remaining processes and work. For shared external actions, designate one executor and wait for all affected sessions to finish; task completion never supplies fresh authorization. A deadline for starting closure should leave time for checks and receipts rather than force an abrupt stop. Test interruption immediately before the final receipt and before close without repeating external actions.

Measure active work and waiting separately, using the [usage compatibility plan](usage-log-compatibility.md) where counts are uncertain. Compare the burden of a scoped correction and a larger task before adding acknowledgements, services or routine full reviews. These observations justify validation scenarios, not a larger channel schema.

The [planning and implementation trial](planning-implementation.md) exposed a separate usage issue: polling only `request` recovered unfinished assignments but omitted `notice` messages by design. The implementer repeated an installation comparison before reading a notice containing reusable evidence. Both roles should inspect `new` between work portions for notices and replies, and use `request` to recover unanswered work. Advancing a read position still does not establish handling or completion. This observed duplicate work supports a guidance correction, without changing channel storage or adding an acknowledgement protocol.

## Conditional extensions

External designs are references for specific problems, not adoption candidates under this decision. The research inspected public documentation and selected source/CI files; no external tool was installed or tested here. Recheck upstream behavior before using a design.

| Lesson and source | Application and trigger |
|---|---|
| Separate storage, receipt and completion: [Hardline inbox signals](https://github.com/sushiHex/hardline-mcp/blob/main/docs/inbox-signals.md) | Clarify meanings now. Add explicit receipt state under [roadmap item 9](../roadmap.md#next-work) only when real work needs to distinguish reading from handling. Keep completion tied to result evidence. |
| Retain messages until processing is acknowledged: [agent-peers-mcp](https://github.com/Co-Messi/agent-peers-mcp) | Preserve unanswered-request lookup. If acknowledgements are added, test interruption before acknowledgement and repeated delivery without repeated actions. |
| Address sessions separately from roles: [Hardline messaging](https://github.com/sushiHex/hardline-mcp/blob/main/docs/messaging.md) | When several sessions share a role, give requests a specific recipient and define ownership across reconnects. Do not treat a provider name as one session. |
| Define restart ownership: [Telepathy](https://github.com/Winterrks/telepathy#good-to-know) | Distinguish resuming a conversation from starting a new one in the same folder. Specify who may recover pending requests; do not copy another project's expiry period without a local need. |
| Declare file ownership: [MCP Agent Mail](https://github.com/Dicklesworthstone/mcp_agent_mail_rust) | Use task handoffs first. Consider file reservations only after repeated concurrent-edit conflicts. |
| Verify each receiving environment: [Hardline's Codex evidence](https://github.com/sushiHex/hardline-mcp/blob/main/docs/codex-queue-wake.md) | Record end-to-end receipt and response in the actual client; configuration, a successful send or a CI matrix alone does not establish live delivery. |

Session registration, explicit acknowledgements and file reservations remain conditional extensions. Evaluate automatic wake-up after repeated manual intervention, and remote transport after selecting two real environments that need it. Prefer the existing commands and storage; account for installation, background processes and provider-version maintenance before expanding them. This planning update authorizes no implementation or external dependency installation.
