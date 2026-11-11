# Roadmap

**Goal: release 0.3.0.** The gate and the feature scope are in [release.md](release.md). Until the tag, the Ready table holds only work toward that gate and CI fixes; any other idea goes to "After 0.3.0".

An agent picks the highest Ready item it can finish, says which in one line, and starts. When an item is finished, delete its row in the same commit as the code and record the behavior change in [CHANGELOG.md](../CHANGELOG.md). When Ready is empty, compare the gate with the current state and add the next unmet condition an agent can work on as a new Ready row, then start it. Stop only when every unmet condition waits for the owner, and say which. Decisions that later work must respect go in [design.md](design.md).

## Ready

| Item | Done when |
|---|---|
| Assess cloud-session channel compatibility ([plan](#cloud-session-channel-plan)) | A live cloud trial and delivery contract determine the supported route and whether implementation needs an incompatible change; keep the existing release gate. |

## Cloud-session channel plan

The owner requested this plan before implementation. Assess compatibility under the existing release gate; do not claim cloud support or change release scope until the runtime trial establishes what works. Local Claude Code works according to the owner and is the regression baseline. The reported failure concerns cloud sessions opening the host channel database; the original error has not been captured.

Expected result: a cloud session exchanges a request and correlated reply with a local awkit participant without sharing a live database file or losing messages after reconnecting. Native messaging remains preferred where supported. SQLite can remain local storage; no measured storage bottleneck justifies replacing it.

| Stage | Work and acceptance evidence |
|---|---|
| 1. Establish runtime capabilities | Start with cloud Cowork and Claude Desktop. Capture the actual failing operation, runtime, allowed connection path and error. Test a minimal local MCP call through Desktop with a cloud-originated request and returned result. Record whether Desktop-originated sessions, permissions and an online PC are required. Treat other cloud runtimes separately; one success proves no other provider's support. If unavailable, record the precise blocker before selecting another transport. |
| 2. Select the interface | Compare native messaging, Desktop-mediated local MCP and authenticated remote MCP/API against the observed runtime. Separate storage, message delivery and starting or waking an agent. Choose adapters by provider and execution environment only where capabilities differ; share message rules, not unsupported operations. Report unsupported capabilities with reasons. Reuse existing session routes when they fit; do not make a fresh session stand in for resuming one. |
| 3. Specify reliable delivery | Define channel identity, participant authorization, message/reply IDs, stable consumer identity, bounded reads and explicit receipt acknowledgement. Persist a caller-supplied idempotency key with each send; retries return the original ID, and conflicting reuse fails. Permit replay until receipt is acknowledged; receipt is distinct from task completion. Keep current local CLI behavior compatible unless a migration is explicitly selected. Never retry a denied operation through another adapter. |
| 4. Implement the smallest proven route | Only after stages 1–3, extend channel operations and add the adapter needed by the first working cloud runtime. Keep DB access on its host. Assess any dependency's license, deployment and maintenance. A hosted relay requires demonstrated need for access without Desktop, plus a deployment and authentication plan; it is not the default. Do not add a scheduler, universal agent server or transcript mirror. |
| 5. Verify and deliver | Test a committed send whose response is lost, duplicate/conflicting retries, lost read results, acknowledgement retry, reconnect/restart, concurrent consumers and cross-channel access denial. Preserve local Claude Code behavior. Obtain an owner-observed cloud request/reply round trip; distinguish polling from unsolicited wake-up. Run the frozen snapshot checks and Windows/Linux CI. Update CHANGELOG and this row with implementation; any incompatible change remains subject to the release gate. |

The implementing agent owns the runtime trial and code; the owner supplies only account-side permissions or acceptance the agent cannot perform. The next action is stage 1. Finish planning now; do not start implementation as part of this documentation task.

Research: [Cowork architecture](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview) and [surface availability](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile) describe Desktop-mediated local access. [SQLite guidance](https://www.sqlite.org/useovernet.html) supports host-local DB access behind an API. [Claude Code channels](https://code.claude.com/docs/en/channels) target running Code sessions; Cowork wake-up support must be demonstrated separately. [A2A](https://a2a-protocol.org/latest/topics/a2a-and-mcp/) still requires app integration and is not selected for this task.

Source-level simulation on `be1303b` reproduced duplicate messages with distinct IDs after repeating a post and an empty second `new` read after discarding its first result; `peek` retained both messages. This establishes delivery work needed before a remote wrapper, not the cause of the reported Cowork error.

## Waiting for the owner

Each row has a default. An agent applies the default when the rest of the gate is met and there is no answer.

| Decision or material | Default |
|---|---|
| Codex sidebar visibility. The owner still cannot see the probe in the exact project; the native listing API returns it. | Restore the Computer Use connection for app-side diagnosis; native pipe lookup still fails after the owner opened the app. |
| Claude's picker excludes SDK sessions by design ([official docs](https://code.claude.com/docs/en/sessions#loop-p-agent-sdk-and-background-sessions)). Exact-ID interactive resume opened the original probe and its saved reply. | The owner retains picker visibility as a release condition and holds the release. Resume when the provider supports listing SDK sessions or the owner changes the condition. |
| The PyPI pending publisher and the `pypi` environment ([release.md](release.md#release)). | None: the upload needs them. |
| The word "release". | None. |

## After 0.3.0

Each waits for what its row names; do not start them before the tag.

| Item | What unblocks it, and who |
|---|---|
| Whether to remove `init --commit`; it stays in 0.3.0. | The owner's decision after the release. |
| Storage growth of shared artifact storage on a real continuation. One copied run is 42.8 MB; the first shared run with one changed file added 284 KB plus a 4.8 KB object. Near-identical repeats prove nothing. | The owner's target project runs a continuation that changes outputs; that session records the increment against a copied counterfactual. |
| Two-environment trial: a file-access-only reviewer on another computer, and recovery of an interrupted request on an execution-capable client. | The owner makes another computer available. |
| Attach to existing IDE sessions; enroll foreign Claude sessions; list live Claude sessions. | A provider endpoint. Codex has none (socket error 10050). The owner says which outcome they want when one appears. |
| Repair the other project's `rules.toml`, which still holds a `MultiplexedPath(...)` value. | Owner authorization; awkit never rewrites a project's rules on its own. |
| The `AWKIT_ENV_PROBE` sentinel probe for Git-Bash commit-path activation. The code fix is delivered in `9093631`; whether the selector activates in a live session is unproven. | The owner opens a fresh Claude session on their Windows machine and gives a new go. |
| The automatic Stop-hook ImportError (`awkit.checks`, `awkit.process`), never reproduced. | The owner captures a failing automatic invocation with its runtime context, if it happens again. |
| Whether writing corrections persist without reminders, and the attribution cost of `writing compare` on a real revision. | The owner selects a real revision. |
| Presentation production with native PowerPoint control; HWP/HWPX validation; the three reported PPTX validator bugs. | A working PowerPoint control connection from the owner, then a selected real task. |
| The winget and Homebrew installer branches have never run. | A clean machine without Git or Python. |

## Decided against

Do not propose these again without a new observed failure: removing the second payload buffer in shared publication (largest observed artifact 11.4 MB, no memory failure); source-snapshot storage cleanup; unifying the two artifact collectors; migrating, expiring or deleting old review runs; a new task store or lookup command; a general updater for connected projects; a scheduler or background listener; a role-management feature; a new document engine or format rule; extending `check done`.
