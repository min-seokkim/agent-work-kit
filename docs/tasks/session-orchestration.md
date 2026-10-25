# Create, resume and follow independent sessions

Status: unit 1 implementation and bounded first-use observations are recorded below; technical delivery has its own receipt. Planning owns product scope, research supplies provider evidence and delegated checks, and implementation owns changes, integration and delivery. Planning base: `c3dd1bf`; implementation base: `2906d44`. Native execution, readable-screen inspection, mechanical verification and human acceptance remain separate.

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

## M-151 implementation contract

Base: `2906d44`. Work in the isolated `dev` clone; retain the original checkout and deferred M-141 unchanged. Baseline label `managed-unit-one` was marked before product edits. M-151 owns unit 1; M-154 and M-155 refine later routing and the first screen. Direct feasibility R-006/M-014 is an assessment, not live execution evidence.

### Modules and interface

- `src/awkit/codex_session.py`: owned App Server process, stable stdio JSONL handshake, RPC correlation, streamed events, server requests and bounded cleanup. No experimental queue, WebSocket or dynamic-tool requirement.
- `src/awkit/session_store.py`: managed channel metadata, atomic message/key/attempt transactions, native event and decision projection. Existing `Channel` messages and linked replies remain authoritative task exchanges.
- `src/awkit/sessions.py`: project controller, native thread/session binding, request dispatch after observed idle, normalized lifecycle, scoped approval answers and returned message publication. No semantic task-completion inference.
- `src/awkit/session_http.py` and packaged `src/awkit/session_ui.html`: loopback HTTP owner/control service, token-authenticated agent client and local human screen. Human and agent entries call the same controller. A held SQLite lock prevents a second controller in the same project; stale processes are not killed or taken over.
- `src/awkit/cli.py`: `session --project PATH serve/create/send/status/decide/interrupt`. Serve accepts the provider executable and an optional existing declaration record; other entries use the running owner. Request bodies use structured arguments/files. Human controls choose the scoped project, Codex, name, responsibility and supported permission settings.
- `src/awkit/channel.py`: extract the existing validated insertion into a connection-taking internal helper so message insertion and managed correlation can share a transaction. Preserve all public channel arguments, roles, validation, IDs, schema and exits.
- Tests: focused store/compatibility, stdio lifecycle/correlation and HTTP/CLI/control tests, with a harmless fake provider subprocess. Packaging includes the HTML. Reference points to a new optional `kit/sessions.md`, keeping the existing reference within 9,000 words. CHANGELOG and this record carry behavior and evidence.

### Persistence fixed before code edits

The project-owned `.awkit/sessions/channels/` contains one managed SQLite channel per local session. Its existing `messages` and `cursors` schema and `PRAGMA user_version=1` stay intact. Only explicit managed creation adds the following versioned extension; opening/browsing an ordinary channel never migrates it. Legacy channel readers/writers ignore these additional tables. No existing real channel needs migration for unit 1.

- `awkit_session`: one row, extension schema 1, random local/channel UUID, human name, provider, resolved project, responsibility, native thread ID, controller generation, actual permission/model/client information, last observed state/time/source and error. The UUID is stored inside the database, not derived from its path. Aliases share it; conflicting copied identities are rejected.
- `awkit_posts`: client idempotency key, authoritative message ID, entry source and creation time. The key and message are committed atomically. Repeating a key returns the same message; a different target/body is rejected. A client reports an uncertain transport outcome with its key rather than resending automatically.
- `awkit_delivery`: random attempt ID, unique originating request ID, controller generation, native thread/turn IDs, provider-admission/execution state, linked reply ID, error and timestamps. A unique claim is committed before sending. Stored, accepted, executing and returned remain separate observations. Attempts are never replayed automatically, including after process interruption.
- `awkit_events`: ordered generation-scoped native method/thread/turn/item observations and relevant payload/time. Exclude reasoning and unrelated account/config events. Only this controller's new conversations are observed.
- `awkit_decisions`: generation and native RPC ID, originating thread/turn, method, original parameters, supported choices, state, explicit response and times. Decisions are never granted automatically. Unsupported requests remain visible with unavailable controls; supported answers return through that same live connection.

The controller keeps a local endpoint/capability file and lifetime lock beside these channels. Neither is a new task registry. Existing task-record declarations are optional read-only evidence; absent declarations are unrecorded. Browsing never advances channel cursors or acknowledges/accepts a result. Unanswered requests and actual pending provider decisions are derived from their records; declared pending handling is shown beside returned replies without rewriting it.

For a live session, supported unanswered request kinds trigger a uniquely claimed turn after observed idle; notices remain stored without invoking the provider. This also permits existing channel writers to post to a managed channel. A final native message becomes a linked channel reply atomically with the attempt result. Provider turn completion alone does not establish task success or result integration.

### Runtime and acceptance boundaries

Use the current generated default schemas in the executor's `schema/`; the executable matches retained SHA-256 `f5521b058ca08e249afd3b25b4681e81100181d92e73aa6b94bb8e75c2aa487b`. Its reused version is Codex 0.162.0-alpha.17.2. Current schema uses `read-only`/`workspace-write` sandbox inputs; some official examples use different spellings. Preserve the actual returned policy, reviewer and sandbox, not a requested label. Thread-local choices do not edit provider configuration or credentials.

The first screen follows M-155: session list beside complete conversation, compact pending strip, visible project/recipient, optional technical details, actual permissions and reasons for unavailable actions. Narrow navigation opens the full conversation with a return control. Escape content and authenticate mutations; neither raw event text nor an untrusted page can choose a provider method.

Acceptance uses a disposable project and invented text: create/name from the human interface, first assignment and actual reply, observed idle, then an agent CLI follow-up using a harmless fact from the first turn in the same native conversation. Retain full exchanges, IDs/events, permissions, binary/version, interventions and normal/narrow rendered inspection. Offline tests and Windows/Linux CI cover the wrapper only; actual provider/platform coverage is reported separately. No human usability acceptance is implied.

Restart/same-ID resume and uncertain-send/approval recovery remain unit 2. Old generations are unavailable/unknown with their last observations; no silent replacement, automatic replay or takeover. Claude/cross-provider and selected IDE attachment remain later units. For later Claude routing, prefer native peer discovery/delivery only when the participating sender actually exposes and resolves it; this is not generic external RPC. Keep managed SDK/CLI same-ID recovery distinct, as M-154 requires. No live Claude call is part of unit 1.

### M-158 existing-history integration

Include explicit read-only registration in unit 1, as the original human-view requirement calls for. Add `src/awkit/session_history.py` for project-scoped channel path/name registration and read-only projections, plus `session register` and its human control. A schema-1 `.awkit/sessions/views.json` contains registration UUID, resolved channel path, human names for both existing roles, selected local role and optional task label. It holds references only, not copied messages or task state. Atomic file replacement is serialized by the existing controller lock. Aliases reuse a compatible registration; conflicting party/role labels are rejected. Missing/invalid channels remain visibly unavailable; they are never created or repaired by viewing.

Extend the existing private `channel_status._read_channel` with optional full-body selection for this explicitly requested view. Its default projection, validation and public status output remain unchanged. Validation and full-body selection use the same read-only transaction. Existing-history views preserve both named parties and reply links, never claim a managed native identity, and disable send/resume with the reason. They neither write/migrate the channel nor advance cursors. Test byte/cursor preservation separately from managed-provider execution.

The managed extension's session metadata is one versioned JSON object in `awkit_session.data` with its stable UUID also constrained in a separate column; the described fields retain their meanings. Delivery outcome is recorded separately from admission/execution state. This physical representation changes no existing channel table or schema version.

A delivery also stores its client RPC ID before writing to the provider, so the durable request/attempt/turn binding retains ambiguous admission evidence. This is part of the new managed extension; no real managed records have been created or migrated yet.

The controller also exposes an explicit stop action for graceful owned-process cleanup; it preserves native identities and uncertainty, and does not implement unit-2 resumption.

The real-use [planning-role recurrence](planning-role-drift.md) is retained separately. Its bounded diagnosis is complete; procedural correction remains unverified. Startup responsibility is supplied through the provider-native thread instructions and retained with its admission source; a displayed role or an accepted creation request does not establish role compliance. This unit adds no role enforcement or mandatory acknowledgment turn.

## Unit 1 execution and verification

The implementation supplies the shared loopback controller and human/agent controls,
with explicit existing-channel registration. Core channel schema and default status
output remain compatible. The new managed extension stores identity, immutable
submitted startup context and correlated runtime observations beside the existing
task exchanges. The optional [session reference](../../kit/sessions.md) describes
commands, permissions, errors and unsupported recovery.

The Windows first-use execution used Codex 0.162.0-alpha.17.2 from the executable
matching retained SHA-256 `f5521b058ca08e249afd3b25b4681e81100181d92e73aa6b94bb8e75c2aa487b`.
The human screen created a named research conversation in a disposable Git project
and sent its first invented-fact assignment. After an observed completed/idle
turn, the agent CLI sent a contextual arithmetic follow-up without repasting the
facts. Both actual replies appeared in the same human conversation view.
Native identity `01a16e86-d6b9-7c43-951f-030cc5d41c04` retained two distinct turns,
`01a16e88-6437-71b1-9ab9-34113292ded4` and
`01a16e89-2d9b-74b3-a468-d176df59116f`, linked to the two channel requests/replies.
The second answer retained the earlier name and calculated the expected remainder.
The first answer identified the supplied responsibility; future adherence remains
unverified. The provider returned read-only permissions, network access false,
on-request approval and user review. No tool items or approval requests were
observed. There were no extra runtime interventions, owner relays, turn retries or
manual approval grants; the expected human create/first-send and agent follow-up
are counted separately. This is two live turns, not a measured productivity gain.

Implementation inspected actual full messages, reply links, recipient/project,
permission source, stale-state provenance and unavailable recovery controls in
Edge. The default desktop view and a 390 by 844 viewport were inspected; document
width remained 390 pixels. Narrow list/back/conversation navigation and view
reload preserved access to both exchanges. Temporary viewport settings were reset.
Two current channels, Planning/Implementation and Research/Implementation, were
opened separately as named read-only history. Their full bodies and reply links
were readable; a reply navigated to its original request. Native controls stayed
unavailable. Two bounded quiet status reads left both original database hashes
unchanged; other sessions' independent writing remains outside that interval.

Research executed the frozen offline package at
`bdf0d2331df53d53992539bbdc68abbe7accdd63`, tree
`e43e954bc251cc80ef2f1d4034f92d4f6df56b01`, under direct R-007/M-020. Ruff, all 23
session tests and 35 existing-channel compatibility tests passed without warnings
in its retained run `review-c9_8b386`. Implementation did not duplicate that
delegated snapshot run. These tests use offline provider processes and ephemeral
ports; they do not establish Linux live-provider behavior or actual approval
recovery. The cumulative final delivery checks belong to the delivery receipt.

Earlier working checks and failures remain: two initial Windows fixture cleanup
errors from unclosed test connections were corrected; an HTTPError cleanup warning
led to closing the product client's error response, followed by a clean HTTP
slice. CLI/preflight helper assertions and path errors stopped before their
claimed mutation or provider launch. The failed first disposable setup is retained
with zero provider/model starts. No failure was relabeled as a successful live run.

The product's stop control closed both feature-owned controllers and its owned
native process; explicit process and endpoint observation confirmed cleanup. The
two browser tabs were closed. Existing planner/researcher/IDE owners were neither
attached nor interrupted. Full restart/resume and uncertain-send/approval recovery
remain M-166/unit 2; Claude, selected existing attachment and real collaboration
remain later units. Human usability acceptance and causal benefit are unverified.

Evidence is retained under
`.awkit/handoffs/managed-session-implementation/executor/`: `live-v2/` fixes inputs,
actual exchanges/events, client/model/permission provenance, intervention counts
and screenshots; `history-live/reading.json` records passive history scope;
`cleanup.json` records owned-process observations. Research owns its check run and
diagnosis under `.awkit/handoffs/product-research/executor/managed-session-verification/`.
Final tree, cumulative checks, commit, CI and exact installed contents are recorded
in the executor's `delivery.json`. The original checkout's pending copies and
deferred M-141 remain separately preserved and unmatched.


The final declaration-view exercise reused the four actual saved messages after
closing their provider. A new controller read the old generation as unavailable,
without native resume or another model turn. An explicitly synthetic pending
declaration remained visible beside its actual returned reply and linked to the
source request. Both declaration and channel hashes stayed unchanged during
reading. The first fixture used the wrong ownership-field name; the UI showed
declarations unavailable, and the corrected fixture used the existing
`responsible_session` field. This was a fixture correction, not a schema migration.
The invalid input and observation remain in `declaration-view/`; its controller
was stopped separately. Full native restart recovery remains outside unit 1.


The guard generator's explicit source lists register the new session guide and
command module before regenerating their existing F24/F29 mappings. The first
generation omitted those unregistered declarations and a final-preparation
allowlist assertion stopped before creating a snapshot/check. This integration
changes no role-incident rule, hook or failure entry.

## Unit 2 recovery and current-work reading

M-166 assigns exact-conversation recovery after delivered unit 1; M-175 adds two bounded reading improvements at the next unfrozen integration. Implementation works from 70aec98 in the isolated dev clone. M-176 queues owned Claude integration after these outcomes, without changing existing-owner or IDE-attachment limits. The retained execution package is .awkit/handoffs/managed-session-recovery/executor/; its delivery receipt owns the final frozen checks, CI, installation and remaining repository mismatch.

The owning controller explicitly upgrades managed extension 1 to 2, preserving core schema 1, messages, client keys, cursors and original connection generations. It adds client correlation, interruption intent and cancellation disposition. Ordinary channel registration stays read-only. Restart automatically resumes the exact owned native ID with its project and startup responsibility, reconciles known turns or one exact client-message match, and publishes an existing answer against its original assignment. Unmatched admission remains unresolved; a separately keyed new assignment after observed idle is distinct from replay. Pre-dispatch cancellation prevents launch; a later stop request retains delivery uncertainty. Acknowledged interruption, controller stop and provider terminal outcome stay separate.

Decision controls retain original request and callback identity. Disconnected routes remain unavailable; neither old RPC IDs nor recorded choices grant a new callback. Current server callbacks alone establish live response routes. Replacing a dead owned provider changes the connection generation, including within the same HTTP controller. Reconnection passes the saved effective permission policy and compares the returned sandbox/approval scope before queued dispatch; a difference holds work and retains both scopes. Final preservation reading exposed the earlier hardcoded policy and missing comparison, so the earlier frozen run remains retained and a superseding snapshot checks this correction. Owner conflicts and unsupported recovery preserve history and the actual error; no replacement thread or lock bypass is used.

The actual Windows case reuses unit 1's Harbor project and native ID 01a16e86-d6b9-7c43-951f-030cc5d41c04. After restart, a human follow-up correctly retained Silver Wren and computed eight cubes without a transcript repaste. A separate task was visible after closing its view and stopping its controller; native persisted history subsequently reported interrupted with no reply, and it was not replayed. A deliberately dropped local turn/start response left another attempt unbound. After that real turn completed, a cold restart matched its persisted userMessage.clientId, recovered one reply against M-005, and retained five total attempts. The final agent CLI follow-up M-006 returned Silver Wren and four cubes in the same conversation. Six actual attempts include the two earlier unit-1 turns, one interrupted task and five linked replies overall; no extra regenerated task, automatic grant or owner relay was observed. This bounded observation does not establish exactly-once execution.

Offline provider tests cover lost response/recording, duplicate correlation keys, old decision routes, unsent cancellation, several unfinished requests, delayed interruption outcome, callback ID reuse and owner conflict. The focused 35-test run passed. Earlier retained failures were a legacy expectation that restart was unsupported, premature send availability during reconciliation, and unclosed test-only SQLite connections; the latter two were corrected before the clean runs. Real pending-approval process recovery was not exercised. The inspected protocol provides no general old-callback rebind API; such a route remains unavailable unless a current native request establishes it. Linux live-provider behavior, unrelated IDE ownership and real user acceptance remain unverified.

Current-work declarations resolve names only through actual registered relationship mappings, retain unknown identities, show compact previews and expand to complete records/evidence. In authorized actual Planning/Implementation history, the recovery action identified Implementation and linked to M-166. Ordinary selection opened the latest exchange, a delivery reply linked back to its original request, and Latest returned to recent work. Background refresh retained the earlier reading anchor and expanded declaration. A scheduled latest-scroll race found during inspection was corrected so an explicit reply/action target takes priority. Desktop and narrow observations, source/position receipts and screenshots remain in the execution package. Reading changes no cursor, receipt, task state or native ownership; the planner's corrected stale declaration remains a source-record correction.
