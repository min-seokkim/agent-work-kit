# Session controls

Use one project-local controller to create owned Codex or Claude conversations, enroll an explicitly selected supported Codex conversation, exchange work through the human screen or agent CLI, and read explicitly registered channel history. Keep stored messages, provider execution and result handling separate; a returned reply is not evidence that its work was accepted.

## Start the controller

Run in the chosen project:

    awkit session --project . serve

Use --codex PATH to select the installed Codex executable when it is not on PATH. The command prints a private loopback control URL; open that URL in a browser. Keep its capability token local. Control and conversation records live in .awkit/sessions; keep .awkit out of version control through the existing project setup. An unavailable executable disables native creation while existing-history reading remains available. The controller uses documented [Codex App Server](https://learn.chatgpt.com/docs/app-server) stdio and the provider's existing login; it does not configure authentication.

The human screen creates a named session with project, provider, responsibility and requested permissions. The returned native scope is shown separately. Model observation shows the retained creation/initialization response, not per-turn execution; missing enrollment/history coverage stays unknown. Name and responsibility reach the new conversation's startup instructions; normal provider project instructions remain available. Supplied instructions and a displayed role do not establish compliance. This version does not edit the responsibility of a running conversation.

Claude requires the optional claude extra in the controller's Python environment: install agent-work-kit[claude], or inject claude-agent-sdk==0.2.174 into its existing pipx environment. Use serve --claude PATH for an unmodified native executable, or use the SDK's bundled binary. The official persistent ClaudeSDKClient uses the provider's existing login, full native prompt and user/project/local settings. Missing dependencies, missing executables and native authentication failures stay separate. The integration creates no sign-in service or billing fallback. The native UUID requested at creation remains distinct from the identity confirmed by a provider frame; an unconfirmed creation is not silently replaced.

Choose Claude's supported default permission mode or Codex's requested sandbox scope. Switching an unsent creation draft resets incompatible policy choices. Claude's partial native mode observation does not prove complete effective allow/deny rules, Windows sandbox enforcement or equivalent Codex network restrictions. The selected provider and identity stay fixed for an existing conversation.

One controller owns a project at a time. A conflicting owner is refused without taking over its process. Ctrl+C or the explicit stop command closes this controller and its owned provider:

    awkit session --project . stop

Saved identities and channel exchanges remain. Restarting the controller automatically reconnects each saved owned conversation by exact native ID. Closing the browser view only closes the view. Stopping the controller establishes neither task cancellation nor success.

Prevents: F24, F25, F29.

## Enroll a selected Codex conversation

Start the controller first. Choose Use existing Codex conversation in its screen, or supply a name and the exact native thread UUID:

    awkit session --project . enroll Research --thread-id NATIVE-THREAD-UUID

Enrollment sends no assignment. After successful admission, use the ordinary send/status commands below. The name is a local label; enrollment and subsequent recovery submit no role, base instructions or permission overrides. Native context stays in the selected conversation; old transcript text is not copied into the channel.

Enrollment pins Windows x86_64 Codex 0.164.0-alpha.11.1 to executable SHA-256 `4fd2f057bad603bf53dc202457ffd0c3591de62e867a8b01e73816e3fbce5a73`; wrappers, extra launch arguments and other binaries are refused. It requires the same Codex home and local sessions store, exact current project, idle availability, direct-input permission and interpretable native sandbox/approval/reviewer fields. A dedicated private App Server must acquire the native writer lock through exact-ID resume. Close the other owner normally before retrying an ownership refusal. Missing required policy, changed policy/runtime/home, child-input restrictions and admission errors hold work without replacing the conversation. Live IDE attachment remains unavailable.

The controller retains and compares every returned policy field before sending or recovering: sandbox, approval policy/reviewer, runtime workspace roots and active profile. Optional provenance is recorded as supplied; null and key absence remain distinct. An unexposed profile does not invalidate known required scope, and no profile is inferred or configured. Read-only/workspace-write sandbox details must be complete. Inspect a refusal in status; resume retries explicitly after the cause changes. Pending uncertainty is retained without replay.

Prevents: F24, F25, F29.

## Find a conversation by name

Open Use existing Codex conversation to browse indexed conversations in the current project. Choose a row, check the selected identity and local name, then enroll separately. Selection sends nothing and remains fixed across pages, refresh and refused admission. Manual thread ID entry remains available.

    awkit session --project . discover --limit 20

Pass the returned next_cursor as --cursor with the same limit for another page. Omit it to refresh. Limits are 1–50; cursors expire after five minutes or when their connection changes. Concurrent readers keep separate sequences. An unavailable or expired page requires an explicit refresh; no fallback scan occurs. Exit 0 returns a page, 1 reports unavailable discovery, and 2 reports invalid input or a controller error.

Listing requires an already initialized owned Codex connection matching the enrollment runtime, project and home. It never starts or reconnects a server, resumes a conversation or changes permissions. An empty first launch therefore has no list; deliberate creation or enrollment is a separate action.

Only native names, exact thread IDs, project, creation source, labelled creation/update times and registration facts are returned. Unnamed conversations stay unnamed. Updated time is not current activity; creation source is not current ownership. The database-only current-project query can omit stale or missing indexed records. Native previews cross the transport but are discarded before awkit results, events, durable records or diagnostics, including late replies. Other projects, archived threads, child origins, transcript import and live IDE attachment are outside this route.

Prevents: F24, F25, F29.

## Send and read work

Keep the controller started above running. From another terminal, create Research, send an assignment and read its status:

    awkit session --project . create Research --responsibility "Check sources and report findings." --provider codex --sandbox read-only
    awkit session --project . send Research --key request-1 --body "Check the project's source list and report gaps."
    awkit session --project . status

You can also create Research and give its first assignment in the human screen, then use the same running owner from another agent for follow-ups. For Claude creation, use --provider claude --permission-mode default and omit --sandbox.

Use a session name or local ID. Names are unique within this project. Send reads UTF-8 --body-file or stdin when --body is absent. Choose a fresh client key for each new submission. Reusing the key recovers the same stored message; changing its body, kind or recipient is refused. An omitted key is generated and returned. A transport timeout remains uncertain; inspect status with the retained key before repeating an action.

Supported request kinds start a turn after the owner observes the native conversation idle. Existing channel writers can also post requests to that managed channel. --kind notice stores information without invoking the provider. Active work can leave later requests queued. The human view shows complete bodies and reply links, with earlier-message navigation; browsing does not advance an agent's cursor or acknowledge a result.

Pending provider decisions stay with their originating conversation and connection. Only explicitly chosen supported decisions are returned; unsupported requests remain visible. The decide command exposes the same action with a decision ID and an offered choice. Interrupt requests interruption of an observed live turn; its acknowledgement remains distinct from the provider's terminal outcome. Cancel with --request ID prevents an unattempted assignment from dispatching. After an attempt, cancel retains a stop request without erasing delivery uncertainty; it does not send a provider interruption.

Claude tool decisions offer allow-once or deny without applying suggested persistent permission updates. AskUserQuestion accepts answers in the human screen, or decide --answers-file PATH with a JSON object keyed by the original question text. Answers return only to that live callback. Its host route ID is separate from the actual tool-use ID; the SDK does not expose its native control-request ID. Native settings can allow tools without prompting; a callback is not a complete policy audit. No automatic approval is supplied. Application inputs use durable caller UUIDs and matching echoes; human/agent entry is recorded separately from the native human-origin classification. Entry identifies the client path, without authenticating a person. Peer or unknown-origin results never complete the newest application assignment merely by arrival order.

Claude's continuing reader observes public session_state_changed events with the owned-child opt-in CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS=1. A result does not synthesize idle: queued work waits for actual native idle, which can arrive before or after that result. Retain the event's connection, session and position. An initial idle cannot release a later input, and unknown/disconnected activity remains unverified. Idle is a lifecycle observation at that point, not task acceptance or proof that no later background activity can occur.

Status and command results use JSON schema 1. Exit 0 means the command returned its stated result, including stored or stopping; it does not establish task success. Native creation with unknown outcome exits 1 and retains its record. Invalid input, unavailable control or storage errors exit 2. Native state older than one minute is shown as unknown with its last observation and source.

Prevents: F24, F29.

## Read current work

Use ordinary status or the selected conversation's assignment overview. Lead new assignments with the requested output, then add context and limits, so their recorded excerpts identify the work without a generated summary. Read the complete original through its link.

current_work shows outstanding assignments, explicitly pending handling and the latest settled outcome; dispositions retains every request. Local reservation and submission intent are separate from native acknowledgement and a returned reply. Handling stays unrecorded unless an explicit declaration supplies its action and state; an unavailable declaration source stays unavailable. Stored channel requests describe history, not a native queue or current recipient.

Each supported Codex attempt has at most one public_update: its latest retained completed agent-message commentary, with time, request/attempt, turn, native conversation and associated connection generation. Later tools cannot hide it outside the general 30-event window. Final replies, other turns/conversations, unrelated generations and private reasoning never substitute. Claude coverage is unverified. Missing supported commentary is explicit. This text does not establish current activity, correctness or completion; stale native observations remain unknown and failed attempts remain failed.

decision_summary separates responses_needed, submitted_unconfirmed and unavailable. A recorded response awaiting native confirmation is not another response task. Use the existing detailed can_answer controls and offered choices; later work or idle cannot confirm a callback. Reading dispatches nothing, changes no cursor and marks no result handled.

Prevents: F24, F29.

## Update an active turn

Select a Codex conversation's update_target from status, read its original assignment, and supply both that request ID and observed native turn ID:

    awkit session --project . update Worker --request M-001 --expected-turn-id NATIVE-TURN-ID --key correction-1 --body-file correction.txt

The human action appears beside that original active assignment. Its dialog shows conversation, project, assignment and exact observed turn; background refresh does not retarget the open draft. Supply --body, a UTF-8/BOM --body-file or stdin. Updates use the verified runtime identified under enrollment and the existing owned connection. Unsupported providers/runtime or unavailable observations refuse.

The controller durably records a fresh caller key, complete body, source and exact target before native input, then submits required expectedTurnId to turn/steer. A stale/ended turn refuses; nothing moves to another turn or the ordinary queue. Reusing an update key recovers the same local attempt without another provider call; a different body/target or reuse as send/notice is refused. Existing message keys cannot name updates. Response loss stays uncertain through restart without replay. Inspect status before further action.

Updates remain attached to the original assignment; its final reply retains its original relationship and author. Native acknowledgement establishes receipt, not adoption or rollback of earlier work. Read the final output separately. Existing send still queues an assignment for idle; notice still stores information without native input. Update exit0 means acknowledged, exit1 means retained refusal/uncertainty, and exit2 means invalid input or unavailable control.

Prevents: F24, F25, F29.

## Submit a decision file

Use a current offered decision from the selected conversation's status. Keep its complete ID opaque and choose a response under the existing authority. JSON contains exactly decision_id and choice. For an explicitly selected Claude denial, serialize the selected status record without reconstructing its ID:

```powershell
@{decision_id=$awkitDecision.id; choice='deny'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath .awkit/decision.json -Encoding UTF8
awkit session --project . decide Research --input-file .awkit/decision.json
```

Here $awkitDecision is the selected live decision for Research; deny must be offered. Codex uses its own offered values, such as decline. For question answers, choice is the existing object `{"answers":{"Exact question text":"Answer"}}`; every original question still needs its exact text.

Use --input-file - for UTF-8 stdin. Files accept UTF-8 with or without BOM; stdin accepts the same bytes. Do not mix --input-file with --decision, --choice or --answers-file. The existing argument route remains supported. File input cannot change the CLI-selected session. Malformed shapes and duplicate JSON keys are refused before dispatch. The existing handler retains target, connection, generation, offered-choice and once-only checks. A recorded submission remains separate from native resolution; inspect uncertainty before further action.

Prevents: F24, F29.

## Read existing channel history

Choose Open channel history in the screen, or register an existing project channel:

    awkit session --project . register --channel .awkit/channel.sqlite3 --main-name Planning --reviewer-name Implementation --local-role reviewer

Supply names matching the channel's existing role mapping. The view preserves both parties and full reply relationships; it is not a newly managed native conversation. Native send/resume controls remain unavailable. Registration stores path/name references locally, without copying messages, migrating the channel, consuming cursors or accepting a result. Missing or unsupported history stays unavailable rather than being repaired.

An optional serve --record PATH reads the existing schema-1 channel-status declaration record. Declared pending actions show names resolved from registered relationships and compact previews; expand for the complete record and source link. Missing or conflicting identity stays unknown. Ordinary selection opens the recent exchange; Latest returns there after following an earlier reply. Background refresh preserves reading position and expanded declarations. Missing declarations remain unrecorded; a reply does not silently close a declaration. Unread state is not inferred.

Prevents: F24, F29.

## Retain execution evidence

New managed channels keep core channel schema 1 and add extension schema 3 for session/channel UUID, connection generation, submitted context, native identity, message/client-key mapping, durable attempts, native events, cancellation and pending decisions. The owning controller transactionally upgrades extensions 1/2, retaining messages, keys, cursors and provenance. Extension 3 permits an unconfirmed native identity and adds Claude input UUID, echo and result UUID fields; these are not native turn IDs. Older controllers cannot use extension 3. Task text and linked replies remain in the existing channel tables. The database identity is independent of its pathname. Ordinary existing channels are opened read-only without this extension.

Codex recovery preserves the saved effective permission policy and compares the returned sandbox and approval scope before dispatch. A changed scope holds queued work and retains both scopes for inspection. Recovery correlates saved native turn IDs or one matching client-message ID on the exact thread. Returned answers are linked to their original assignment, without regeneration. Missing or ambiguous evidence remains unresolved delivery, separate from queued or cancelled work. After observed idle, a fresh assignment is separate from retrying earlier uncertainty. Completed requests are never dispatched again. Reconnect failure preserves history and its error; resume retries reconnection explicitly without replacing the conversation or bypassing ownership.

Claude resumes only the already confirmed owned ID and project, retaining native context without transcript repasting. It compares the reported default permission mode; complete effective rules remain unverified. A locally recorded correlated result can recover its original linked reply. Public native history omits origin and terminal-result evidence, so missing results remain unresolved; a surviving input or absent history cannot authorize replay. A new request after observed idle remains distinct from that earlier uncertainty. Reconnecting one provider cannot revive another connection's decisions.

Enrolled Codex channels use extension 4 with selected identity, runtime admission and the complete retained native policy. Extensions 1/2/3 keep their existing migration behavior and managed-creation instructions. Older controllers reject extension 4; core channel schema stays 1.

Old disconnected approval callbacks remain unresolved with their request and cannot receive responses. Only a fresh current provider callback establishes a live decision route; saved approvals are never reused. Keep actual inputs, responses, identities, permissions and intervention counts. Offline faults, live-provider recovery, screen inspection and human acceptance establish different scopes. Existing IDE attachment and native peer discovery remain unsupported. No uncertain attempt is replayed automatically.

Prevents: F24, F29.
