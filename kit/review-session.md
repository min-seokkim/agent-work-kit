# Review Session Collaboration

Use this workflow when a main implementation session and an independent review session share a unit of work. Within either session, follow the [delegation guide](delegation.md) for subagents and model selection. This workflow uses `awkit channel` and `awkit review`. If using the same procedure without these commands, define another way to freeze the reviewed revision.

## 1. Purpose and cost

An independent review session is intended to find defects and conflicts earlier than a single-session workflow. It also consumes more time and credits. The user chooses whether to attach one for each unit. Once attached, evaluate it by how early it finds defects rather than by cost (section 7). The main agent may ask whether to attach a review session when starting a `high`-risk unit.

## 2. Session setup

The user opens both sessions. Prefer a different provider for the reviewer; with the same provider, open a fresh session on a judge-tier model. Do not continue or fork the main conversation. A reviewer exposed to the implementation's reasoning is not independent.

| Role | Responsibility | Exclusions |
|---|---|---|
| Main (`main`) | Task decomposition, implementation, policy judgments, integrating recommendations, reproduction tests, authoritative documents, session records and requested commits | Reassigning the review session's judgments or checks to a subagent |
| Reviewer (`reviewer`) | Requested judgments, isolated checks, locating evidence and drafting assigned files | Unrequested file edits, commits, checkout, branch changes, stash or changes to the real index |
| User | `decision-needed` items and conflicts remaining after rebuttals | |

The review session may delegate mechanical exploration and test execution to efficient- or standard-tier subagents while performing judgments itself.

## 3. Work through a unit

1. **Start.** The main session selects a fresh channel file and announces the unit. The reviewer waits for requests.
2. **Incremental review.** After each risky portion, the main session creates a snapshot with `awkit review snapshot` and requests `review` against its ID. The reviewer judges only that snapshot. Later edits belong to a later request; changes made to address recommendations are new changes too. Meanwhile, the main session implements the next non-overlapping portion.
3. **Assignments.** The main session may assign a full test run with `test` or a document draft for named files with `draft`. It leaves those files untouched until the response arrives.
4. **Responses.** The main session accepts findings with `re` or rebuts them with evidence using `rebut`. Each side may rebut the same issue once. Remaining disagreement becomes `decision-needed` for the user.
5. **Final review.** At the end of the unit, the main session requests `final` against a snapshot of the cumulative changes. The reviewer runs `awkit review check` in a fresh worktree before judging it. Further judgment requests follow the second-premium-call conditions and cap in section 3 of the [delegation guide](delegation.md). Reuse results when the already verified snapshot covers the new request.
6. **Close.** Apply the final result, then send `close`. Transfer decisions and verification results into the session record. Retain the channel file as an archive rather than the authoritative evidence document.

The main session closes Minor findings and small issues by checking the diff; they do not trigger another review request. If the reviewer discovers a High risk while handling another request, report it with `notice`. Otherwise, stay within the requested work.

## 4. Review criteria

Separate the response into verdict, findings, execution results and unverified scope. Each finding includes severity (High, Major, Minor), file and line, failure scenario and corrective direction. State both what to add and what to remove. Execution results identify the snapshot, commands, pass and failure counts, and cause classification for each failure. Avoid reassurance without evidence.

Two cases have additional requirements:

- **Concurrency and locking.** A new or changed lock requires a real-database test with two concurrent executions before the work is considered complete. Test both the changed operations against each other and against existing operations that lock the same rows. Without these tests, list the concurrency risk under unverified scope.
- **A failure observed once.** Keep it unresolved until its cause is explained, even if a rerun passes. Use a fresh worktree so first-run failures are not overlooked.

## 5. Commands

Keep the channel file outside Git tracking and use the same path in both sessions.

```powershell
$db = '.awkit/review-<unit>.sqlite3'
$snap = awkit review snapshot apps/events/operations.py tests/test_roles.py
awkit channel --db $db post main reviewer review --snap $snap --body-file request.md
```

| Kind | Sender | Meaning |
|---|---|---|
| `review`, `final`, `test` | Main | Judgment or checks against the specified snapshot |
| `scout`, `draft`, `question` | Main | Locate evidence, draft assigned files, or judge design within approved policy |
| `re` | Either | Respond or accept; the recipient does not reply again |
| `rebut` | Either | Rebut; the other side must respond |
| `notice` | Either | Inform without requiring a reply |
| `close` | Main | End the unit and stop the reviewer's wait |

When user judgment is needed, reply to the original request with `re` and start the body with `decision-needed:`. Exclude credentials, actual personal data, private source material and variable values from error traces. See the repository's CLI documentation for command details.

## 6. Waiting

`awkit channel wait <role> <mode> --max <seconds>` prints the awaited messages and exits with `0`. It exits with `1` on timeout and `3` when the reviewer receives `close`.

- **Claude Code.** A completed background command delivers its output to the session so work can continue. Run `wait reviewer request --max 7200` for the reviewer and `wait main new --max 7200` for the main session in the background. Restart the wait after handling messages. The turn may end while waiting.
- **Codex.** In the session workflow described here, keep the turn open until the unit finishes because an ended turn cannot be awakened externally. Between portions, the main session checks `wait main new --max 0`. Only when blocked does it repeat `wait main reply <ID> --max 600`. The reviewer repeats `wait reviewer request --max 600` until exit code `3`. Each wait cycle requires a model invocation, so avoid short polling intervals.

Do not end the unit with open requests or an unapplied final result. Waiting for user judgment on a `decision-needed` item is the exception.

## 7. Records and evaluation

The main session records the following, marking unavailable values as `unverified`:

- Actual models used by both sessions and their subagents, verified from logs rather than self-reports.
- For each High or Major finding, who found it (main, review session or the main session's verifier) and when (incremental review, tests, final review or after acceptance).
- Request counts by kind and whether the main session also ran its own verifier.

## 8. Starting prompts

Paste the appropriate prompt into each session and replace `<unit>`.

Main session:

```text
Implement <unit> as the main session. Read agent-work-kit/review-session.md and follow the main role. A review session is monitoring the channel.
Use .awkit/review-<unit>.sqlite3 as the channel file. After each risky portion, create a snapshot with awkit review snapshot and request review.
At the end, request final, apply its results and send close. Do not commit.
```

Review session:

```text
Act as the independent review session for <unit>. Read agent-work-kit/review-session.md and follow the reviewer role.
Use .awkit/review-<unit>.sqlite3 as the channel file. Receive and handle requests with awkit channel wait reviewer request; stop when close arrives.
```
