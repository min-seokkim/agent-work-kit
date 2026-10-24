# Create, resume and follow independent sessions

Status: selected for development after the active writing-guidance unit and its assigned application exercise. Planning owns the product contract; research owns provider capability evidence; implementation owns adapters, interface, verification and delivery. Planning base: `c3dd1bf`. The [collaboration record](independent-session-collaboration.md) retains existing channel behavior, native-provider research and executed worker probes. No production session launcher is delivered by this plan.

## User outcome

From one local interface, a person or authorized coordinating agent can create an independent session, give it work, read the exchange, and resume that same session with another assignment. The person can see who owes a response without opening a database or asking the planner to reconstruct several channels. Codex and Claude sessions can collaborate while retaining their own context and provider tools.

The owner selected four capabilities together: independent-session creation, waking or resuming sessions, integration with first-party capabilities, and readable communication history. Existing request recovery and assignment-boundary procedures remain useful, but do not fulfill these capabilities. A functioning first increment is a delivery boundary, not a reduction of the full outcome.

## Product contract

| Action | Result the user can observe |
|---|---|
| Create a session | Choose project, provider, name and responsibility. A real independent provider conversation is created with a stable identity and its actual execution permissions. |
| Give it work | Select the recipient by name, send an assignment and see whether it is queued, accepted by the provider, running or awaiting intervention. |
| Continue a session | Send another assignment after idle, or resume its persisted identity after the controller restarts. Display a recovery failure without silently creating a replacement conversation. |
| Connect an existing session | Explicitly select a known conversation. Show whether the provider supports observation, sending or resumption for that surface; unsupported attachment remains an unfinished capability. |
| Follow collaboration | Read messages, replies, task changes and pending actions in a local timeline, with sender, recipient and related assignment visible. |
| Resolve an intervention | Identify the session and request needing a decision. Route supported approval responses to the originating provider; otherwise show the exact native action needed. |

Creating a managed session and attaching an existing IDE conversation are separate operations. Managed creation can ship while existing-session attachment is unresolved. Creating a fresh session, forking history or reading an old log must never be labeled as resuming the selected conversation.

For a managed idle session, sending an authorized assignment should start its next turn through the provider automatically. The person must not need to press a separate wake control for every message. For a busy session, use the provider's supported queue or steering behavior and show which occurred. A notice need not trigger a model turn; distinguish information from assigned work using the explicit request type and current task context.

Prefer native session discovery, messaging and lifecycle events where the selected provider exposes them. awkit supplies the common project/session view, cross-provider routing and retained task relationships. Keep native tools and approval behavior accessible; avoid recreating the provider's conversation engine merely to normalize its interface.

## First implementation unit

Deliver a complete local path for one managed Codex session through an awkit-owned App Server process using documented stdio JSON-RPC. Research M-049 supports this selected path from current official documentation, local executable/help inspection and retained owned-worker runs. The [Codex App Server documentation](https://learn.chatgpt.com/docs/app-server) describes conversation creation/resumption, starting or steering turns, and streamed events. The previous live runs used a different transport; the shipped stdio path still requires live verification. These methods alone do not establish attachment to an existing IDE session.

Use one project-scoped controller for the human controls and agent entry point. Reuse native identity, response correlation, event observation and owned-process cleanup responsibilities from the retained probes. Their top-level scripts, global request state and scratch-specific approval rejection are not the product implementation. Research's capability matrix and evidence limits are retained under `.awkit/handoffs/product-research/executor/independent-session-readiness/`.

The first interface includes creation, assignment, a readable reply and observed session state. After the first turn finishes, a second assignment reaches the same conversation without user relay. Preserve enough identity and event evidence to distinguish this from two independent one-shot commands. Keep the provider adapter usable by the coordinating agent as well as the human interface, so the planner does not become a manual dispatcher.

Implementation chooses the smallest supported process-ownership and persistence arrangement after the bounded capability report. A viewer of existing messages alone does not meet this unit. A reusable runtime wrapper without the human path also does not meet it. Reuse existing channel records where they provide the required correlation; identify any necessary schema migration before changing persisted data.

## Human interface

Provide a session list and a conversation view. The list shows name, provider, project, responsibility, current assignment and observed execution state. The conversation view shows complete message bodies, reply relationships, related outputs and pending decisions. Make unread material, unanswered requests and returned results awaiting integration distinguishable. Informational notices do not automatically create reply duties.

Show create, send and resume controls where supported. Explain unavailable actions beside the selected session. Keep database paths, transport role labels and internal message IDs in optional details; people should identify the parties and next action without decoding them. Retain timestamps and the source of runtime observations so an old status does not appear current.

The first view is project-scoped and local. Register participating sessions and channels explicitly. Existing channel history can be opened read-only without importing unrelated private transcripts. The interface displays task-related exchanges and provider events needed to operate the session; it does not need private reasoning traces.

## First-use acceptance walkthrough

Use a disposable project with invented inputs and existing authorized provider access. Create a named research session from the local interface and give it a small bounded assignment. The selected project, provider, actual permission mode and new native conversation identity must be retained. The interface should show the submitted assignment immediately, then the provider's execution and actual response without a manual channel export.

After the turn becomes idle, use the agent entry point to request a specific follow-up in that same session. Preserve the first conversation identity and correlate both replies with their requests. The follow-up can refer to the earlier supplied material; do not repaste a complete conversation to make an independent replacement appear continuous. Open the local interface again and read both exchanges there.

Inspect the interface at a normal desktop width and a narrow window. A reader must be able to identify the session, the recipient of each message, the latest reply and any remaining action without raw database access or unexplained identifiers. Check full message readability and state updates, not merely the existence of buttons. An automated browser walkthrough can establish that the controls operate; it is not human acceptance of their usability.

Retain the actual input/output, native identities, observed state transitions, controller version and intervention count. A failed provider launch or an unavailable approval route remains a visible incomplete attempt. Keep failure evidence alongside any successful rerun. This bounded exercise establishes the first live path; the later real collaboration unit measures its usefulness.

## Lifecycle and recovery

Keep three kinds of evidence separate: a message stored locally, provider acceptance/execution, and a reported or verified task result. A completed provider turn is not proof that the assigned work succeeded. A disconnected controller is not proof that a session is idle or finished.

Persist provider conversation identity, the originating assignment and native turn/message correlation before relying on restart recovery. Reconcile an uncertain send against available provider evidence before retrying; unresolved delivery must remain visible rather than triggering duplicate work. Scope process ownership explicitly so resumption does not take over another active client or bypass a provider lock.

Preserve permission requests and their originating session. Approval to run an agent is not approval for every external action it proposes. Use the provider's existing execution and approval mechanisms, and preserve a pending decision across controller interruption where supported. Define explicit stop behavior so stopping a controller or turn does not falsely mark its assignment complete.

## Sequence and acceptance

| Unit | Completion evidence |
|---|---|
| 1. Managed Codex session with local controls | Actual creation, first assignment/reply, idle observation and second assignment in the same conversation through the human and agent entry points. Record client/version, permissions, native identity and manual interventions. |
| 2. Restart and uncertain delivery | Restart the owned controller, resume the persisted conversation and recover pending work. Exercise interrupted delivery and approval handling without duplicate execution or false completion. |
| 3. Claude and cross-provider work | Use supported Claude capabilities. Exchange an assignment and correlated reply between independently contextualized Codex and Claude sessions, visible in the same interface. |
| 4. Selected existing sessions | Demonstrate supported attachment and continuation for each claimed IDE or desktop surface. Record precise provider limitations for unsupported surfaces; managed-session success does not complete this unit. |
| 5. Real collaboration | Planning, research and implementation use the feature for a bounded real task through assignment, correction and result integration, without manual message relay or repeated wake requests after setup. |

Research investigates the existing-session path alongside the first unit. Do not repeat an unchanged failed attachment probe. A provider boundary should identify the next supported observation or missing upstream capability, while useful managed-session development continues.

Implementation supplies focused lifecycle/compatibility tests, a frozen full check, live provider evidence, readable-interface inspection, Windows/Linux delivery and installation alignment for the scope claimed. Simulated adapter tests establish error handling, not actual provider operation. A live round trip establishes that path, not unattended reliability across all clients. Measure wrong recipients, missed replies, duplicate execution and manual interventions in the real task before claiming reduced user effort.

## Coordination

Research assignment M-049 completed the capability matrix and reusable implementation recommendation in R-049. Planning selected the managed stdio path; technical feasibility and exact modules/schema are coordinated directly with implementation. M-149 sets this feature after the current M-143 writing unit and its assigned exercise. Public writing-example packaging remains a candidate for later selection. Deferred hook work remains separately preserved.

Planning owns this document and the linked collaboration-plan updates. Implementation currently owns the roadmap integration files from the preceding handoff; request its priority/link update instead of editing those files concurrently. Transfer the new plan explicitly before delivery. No runtime behavior or completed verification is claimed by these planning edits.
