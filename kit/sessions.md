# Session controls

Use one project-local controller to create managed Codex conversations, exchange work through the human screen or agent CLI, and read explicitly registered channel history. Keep stored messages, provider execution and result handling separate; a returned reply is not evidence that its work was accepted.

## Start the controller

Run in the chosen project:

    awkit session --project . serve

Use --codex PATH to select the installed Codex executable when it is not on PATH. The command prints a private loopback control URL; open that URL in a browser. Keep its capability token local. Control and conversation records live in .awkit/sessions; keep .awkit out of version control through the existing project setup. An unavailable executable disables native creation while existing-history reading remains available. The controller uses documented [Codex App Server](https://learn.chatgpt.com/docs/app-server) stdio and the provider's existing login; it does not configure authentication.

The human screen creates a named session with project, provider, responsibility and requested permissions. The returned native scope is shown separately. Name and responsibility reach the new conversation's startup instructions; normal provider project instructions remain available. Supplied instructions and a displayed role do not establish compliance. This version does not edit the responsibility of a running conversation.

One controller owns a project at a time. A conflicting owner is refused without taking over its process. Ctrl+C or the explicit stop command closes this controller and its owned provider:

    awkit session --project . stop

Saved identities and channel exchanges remain. Resumption after controller restart is not supported yet.

Prevents: F24, F29.

## Send and read work

Give the first assignment in the human screen, then use the same running owner from another agent:

    awkit session --project . send Research --key request-2 --body "Continue using the facts from the previous request."
    awkit session --project . status

Use a session name or local ID. Names are unique within this project. Send reads UTF-8 --body-file or stdin when --body is absent. Choose a fresh client key for each new submission. Reusing the key recovers the same stored message; changing its body, kind or recipient is refused. An omitted key is generated and returned. A transport timeout remains uncertain; inspect status with the retained key before repeating an action.

Supported request kinds start a turn after the owner observes the native conversation idle. Existing channel writers can also post requests to that managed channel. --kind notice stores information without invoking the provider. Active work can leave later requests queued. The human view shows complete bodies and reply links, with earlier-message navigation; browsing does not advance an agent's cursor or acknowledge a result.

Pending provider decisions stay with their originating conversation and connection. Only explicitly chosen supported decisions are returned; unsupported requests remain visible. The decide command exposes the same action with a decision ID and an offered choice. Interrupt requests cancellation of an observed live turn; the provider outcome is reported separately.

Status and command results use JSON schema 1. Exit 0 means the command returned its stated result, including stored or stopping; it does not establish task success. Native creation with unknown outcome exits 1 and retains its record. Invalid input, unavailable control or storage errors exit 2. Native state older than one minute is shown as unknown with its last observation and source.

Prevents: F24, F29.

## Read existing channel history

Choose Open channel history in the screen, or register an existing project channel:

    awkit session --project . register --channel .awkit/channel.sqlite3 --main-name Planning --reviewer-name Implementation --local-role reviewer

Supply names matching the channel's existing role mapping. The view preserves both parties and full reply relationships; it is not a newly managed native conversation. Native send/resume controls remain unavailable. Registration stores path/name references locally, without copying messages, migrating the channel, consuming cursors or accepting a result. Missing or unsupported history stays unavailable rather than being repaired.

An optional serve --record PATH reads the existing schema-1 channel-status declaration record. Declared pending actions appear beside their related messages and evidence. Missing declarations remain unrecorded; a reply does not silently close a declaration. Unread state is not inferred.

Prevents: F24, F29.

## Retain execution evidence

New managed channels keep core channel schema 1 and add a versioned extension for session/channel UUID, generation, submitted context, native identity, message/client-key mapping, durable attempts, native events and pending decisions. Task text and linked replies remain in the existing channel tables. The database identity is independent of its pathname. Ordinary existing channels are opened read-only without this extension.

Keep actual inputs, responses, native identities, permissions and intervention counts when claiming a working path. Offline fixtures establish error/compatibility behavior; live execution and readable-screen inspection need their own evidence. Approval recovery, controller-restart resume, uncertain-send reconciliation, Claude and existing IDE attachment remain unsupported. No uncertain attempt is replayed automatically.

Prevents: F24, F29.
