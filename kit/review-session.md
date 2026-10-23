# Review Session Collaboration

Use this workflow when a main implementation session and an independent review session share a unit of work. Within either session, follow the [delegation guide](delegation.md) for subagents and model selection. This workflow uses `awkit channel` and `awkit review`. If using the same procedure without these commands, define another way to freeze the reviewed revision.

## 1. Purpose and cost

An independent review session is intended to find defects and conflicts earlier than a single-session workflow. It also consumes more time and credits. The user chooses whether to attach one for each unit. Once attached, evaluate it by how early it finds defects rather than by cost (section 7). The main agent may ask whether to attach a review session when starting a `high`-risk unit.

Prevents: F17.

## 2. Session setup

The user opens both sessions. Prefer a different provider for the reviewer; with the same provider, open a fresh session on a judge-tier model. Do not continue or fork the main conversation. A reviewer exposed to the implementation's reasoning is not independent.

| Role | Responsibility | Exclusions |
|---|---|---|
| Main (`main`) | Task decomposition, implementation, policy judgments, integrating recommendations, reproduction tests, authoritative documents, session records and requested commits | Reassigning the review session's judgments or checks to a subagent |
| Reviewer (`reviewer`) | Requested judgments, isolated checks, locating evidence and drafting assigned files | Unrequested file edits, commits, checkout, branch changes, stash or changes to the real index |
| User | `decision-needed` items and conflicts remaining after rebuttals | |

The review session may delegate mechanical exploration and test execution to efficient- or standard-tier subagents while performing judgments itself.

Prevents: F17.

## 3. Work through a unit

1. **Start.** The main session selects a fresh channel file and announces the unit. The reviewer waits for requests.
2. **Incremental review.** After each risky portion, the main session creates a snapshot with `awkit review snapshot` and requests `review` against its ID. The reviewer judges only that snapshot. Later edits belong to a later request; changes made to address recommendations are new changes too. Meanwhile, the main session implements the next non-overlapping portion.
3. **Assignments.** The main session may assign a full test run with `test` or a document draft for named files with `draft`. It leaves those files untouched until the response arrives.
4. **Responses.** The main session accepts findings with `re` or rebuts them with evidence using `rebut`. Each side may rebut the same issue once. Remaining disagreement becomes `decision-needed` for the user.
5. **Final review.** At the end of the unit, the main session requests `final` against a snapshot of the cumulative changes. The reviewer runs `awkit review check` in a fresh worktree before judging it. Further judgment requests follow the second-premium-call conditions and cap in section 3 of the [delegation guide](delegation.md). Reuse results when the already verified snapshot covers the new request.
6. **Close.** Apply the final result, then send `close`. Transfer decisions and verification results into the session record. Retain the channel file as an archive rather than the authoritative evidence document.

The main session closes Minor findings and small issues by checking the diff; they do not trigger another review request. If the reviewer discovers a High risk while handling another request, report it with `notice`. Otherwise, stay within the requested work.

Prevents: F2, F17, F18.

## 4. Review criteria

Separate the response into verdict, findings, execution results and unverified scope. Each finding includes severity (High, Major, Minor), file and line, failure scenario and corrective direction. State both what to add and what to remove. Execution results identify the snapshot, commands, pass and failure counts, and cause classification for each failure. Avoid reassurance without evidence.

Locks and failures seen once follow [Checking](checking.md): a concurrent test against a real database, and a fresh worktree for the rerun.

Prevents: F2, F18.

## 5. Commands

Keep the channel file outside Git tracking and use the same path in both sessions.

```powershell
$db = '.awkit/review-<unit>.sqlite3'
$snap = awkit review snapshot apps/events/operations.py tests/test_roles.py
awkit channel --db $db post main reviewer review --snap $snap --body-file request.md
```

The main session sends requests (`review`, `final`, `test`, `scout`, `draft`, `question`) and `close`; either side answers with `re` (no further reply) or `rebut` (the other side must answer), or informs with `notice`. Use one channel file per review; the channel knows only the roles `main` and `reviewer`. When user judgment is needed, reply to the original request with `re` and start the body with `decision-needed:`. Exclude credentials, actual personal data, private source material and variable values from error traces. See the [command reference](reference.md) for command details.

Prevents: F17.

## 6. Waiting

`awkit channel wait <role> <mode> --max <seconds>` exits 0 with matching messages, 1 on timeout, or 3 when the reviewer receives `close`. Keep each wait within the user's and client's limit; 60 seconds is an example bound, not permission to exceed a smaller limit. A timeout is not cancellation. Exit 2 reports a usage/storage error; investigate it before waiting again.

On startup or resume, inspect `channel export` for requests, prior results and closure before repeating work. Read `wait <role> new --max 0`, then recover unanswered requests with `wait <role> request --max 0`. Use IDs to distinguish unfinished work from an already returned result. The shared `new` position records reading; it does not establish handling or completion, and cannot hide an unanswered request from `request` mode. Use `reply <ID>` or export to recover an earlier result.

Both roles inspect `new` between work portions, including notices and replies. Before waiting, check for unanswered requests. When idle or blocked, wait in `new` mode with the allowed bound, then check `request --max 0` and handle the corresponding IDs. Request-only waits omit notices; a receipt notice does not answer a request.

- **Claude Code.** Where the client delivers completed background-command output to the session, run a bounded `new` wait in the background and restart it after handling messages. The turn may end only with that delivery capability established in the actual client; storing a channel message does not establish it.
- **Codex.** Keep the turn open while waiting: an ended turn cannot be awakened by a stored message. Repeat bounded `new` waits, inspect notices and recover requests after each return. Each cycle requires a model invocation, so avoid short polling intervals and keep the user informed.

Exit 3 means the reviewer stops waiting on that closed channel. Do not end a unit with open requests or an unapplied final result, except for a pending user `decision-needed` item. If the client forces the turn to end, retain a checkpoint with pending IDs and report that resuming needs an active session.

Prevents: F18.

## 7. Records and evaluation

The main session records the following, marking unavailable values as `unverified`:

- Actual models used by both sessions and their subagents, verified from logs rather than self-reports.
- For each High or Major finding, who found it (main, review session or the main session's verifier) and when (incremental review, tests, final review or after acceptance).
- Request counts by kind and whether the main session also ran its own verifier.

Prevents: F20.

## 8. Starting prompts

These prompts assign independent review. Replace `<unit>` before use. For another explicitly authorized pairing, state the actual responsibilities and treat `main`/`reviewer` as transport addresses; an address does not establish independent review.

Main session:

```text
Implement <unit> as the main session. Read agent-work-kit/review-session.md and follow the main role. A review session is monitoring the channel.
Use .awkit/review-<unit>.sqlite3 as the channel file. After each risky portion, create a snapshot with awkit review snapshot and request review.
On startup/resume, inspect history, new messages and unanswered requests. Between work portions inspect new notices; use bounded new-mode waits when blocked, recovering requests by ID.
At the end, request final, apply its results and send close. Do not commit.
```

Review session:

```text
Act as the independent review session for <unit>. Read agent-work-kit/review-session.md and follow the reviewer role.
Use .awkit/review-<unit>.sqlite3 as the channel file. Inspect history on startup/resume and recover unanswered requests in request mode. Read new messages between portions and use bounded new-mode waits while idle, then recover requests by ID. Handle notices as well as assignments; stop when close returns exit 3. Keep the Codex turn open while waiting.
```

Prevents: F17.
