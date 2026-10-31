# Channel wait sleep prevention

## Current status

The coordinator selected an opt-in, best-effort `awkit channel wait --keep-awake` behavior under the owner's delegated scope. Planning review `M-021/R-010` replaced the proposal's power-error exits with warnings so an unsupported platform or a power-only failure does not interrupt channel work. Root owns scope and planning; the implementation session owns code, checks and delivery.

Implementation and 45 focused channel tests pass on the Windows development host, including simulated unsupported-platform and API-failure paths. A five-second native probe confirmed this thread's request and restoration through actual API return values. Another holder kept aggregate system state active throughout; that aggregate observation does not isolate this request. Read `.awkit/handoffs/channel-keep-awake/implementation.json` for the cumulative frozen check, independent review, publication, CI and exact-installation stages before repeating work. The [storage summary view](review-storage.md#summary-view) shares that delivery cycle.

## Selected behavior

On Windows, the flag requests `ES_CONTINUOUS | ES_SYSTEM_REQUIRED` on the wait's thread and restores that thread's previous state in `finally`. Messages, timeout, closure, exceptions and interrupts end the scope. `--max 0` remains one immediate channel read. The default wait never requests a power-state change.

Unsupported platforms and acquisition or release failures warn on stderr that the system may sleep. Normal messages, JSON, cursor behavior, exit codes and exceptions remain. A warning is not evidence that the request succeeded. The option changes no display, away-mode or power-plan setting, and starts no helper process.

The request covers only an active command. Gaps between waits and ended turns remain unprotected; it cannot prevent explicit or forced sleep or reactivate a finished agent turn. Waiting and starting-prompt guidance retain the client's existing duration and recovery rules.

## Evidence and limits

- Proposal: `.awkit/handoffs/planning-continuation/channel-keep-awake-proposal.md`; the accepted `R-010` warning behavior supersedes its exit-2 proposal.
- Retained sleep observation: `.awkit/handoffs/sleep-prevention/observation.json`. It records the reviewer's local event/power-setting queries and temporary helper. The meaning of event reason code 7 is unverified; the helper's aggregate request observation was not proven exclusive to that helper.
- Native API contract: [Microsoft SetThreadExecutionState](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate). Its success return is the previous thread state; zero means failure. The request does not prevent user-initiated sleep.
- Implementation and delivery receipt: `.awkit/handoffs/channel-keep-awake/implementation.json`. Local receipts are unavailable in a fresh clone; published commit and CI identifiers will identify the delivered boundary.

This operational option adds no failure-catalogue entry or guard mapping. Existing channel guards retain their meanings. The native probe must use an owned disposable channel after the reviewer pauses its temporary helper; it must not consume a real channel cursor or change power settings.

## Next action

Read the cumulative receipt and finish only its pending review or delivery stages. The accepted scope includes both additive features, the F16 evidence update and the transferred planning observations. The held task index and shared-storage record remain outside this unit's edit scope.
