# Channel wait sleep prevention

## Current status

The opt-in, best-effort `awkit channel wait --keep-awake` behavior was delivered in `38512d8`, after accepted independent review, a passing frozen check, Windows/Linux CI and exact installation with source, kit and user-skill alignment. The coordinator selected the scope under the owner's delegation. Planning review `M-021/R-010` replaced the proposal's power-error exits with warnings so an unsupported platform or a power-only failure does not interrupt channel work.

The implementation passed 45 focused channel tests on the Windows development host, including simulated unsupported-platform and API-failure paths. A five-second native probe confirmed this thread's request and restoration through actual API return values. Another holder kept aggregate system state active throughout; that aggregate observation does not isolate this request. The completed cumulative receipt `.awkit/handoffs/channel-keep-awake/implementation.json` retains the frozen check, independent review, publication, CI and exact-installation evidence. No real idle timeout or explicit sleep was tested. The [storage summary view](review-storage.md#summary-view) shares that delivery cycle.

## Selected behavior

On Windows, the flag requests `ES_CONTINUOUS | ES_SYSTEM_REQUIRED` on the wait's thread and restores that thread's previous state in `finally`. Messages, timeout, closure, exceptions and interrupts end the scope. `--max 0` remains one immediate channel read. The default wait never requests a power-state change.

Unsupported platforms and acquisition or release failures warn on stderr that the system may sleep. Normal messages, JSON, cursor behavior, exit codes and exceptions remain. A warning is not evidence that the request succeeded. The option changes no display, away-mode or power-plan setting, and starts no helper process.

The request covers only an active command. Gaps between waits and ended turns remain unprotected; it cannot prevent explicit or forced sleep or reactivate a finished agent turn. Waiting and starting-prompt guidance retain the client's existing duration and recovery rules.

## Evidence and limits

- Proposal: `.awkit/handoffs/planning-continuation/channel-keep-awake-proposal.md`; the accepted `R-010` warning behavior supersedes its exit-2 proposal.
- Retained sleep observation: `.awkit/handoffs/sleep-prevention/observation.json`. It records the reviewer's local event/power-setting queries and temporary helper. The meaning of event reason code 7 is unverified; the helper's aggregate request observation was not proven exclusive to that helper.
- Native API contract: [Microsoft SetThreadExecutionState](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate). Its success return is the previous thread state; zero means failure. The request does not prevent user-initiated sleep.
- Implementation and delivery receipt: `.awkit/handoffs/channel-keep-awake/implementation.json`. Local receipts are unavailable in a fresh clone; published commit `38512d820ac75e861b93cfa5209e252784f18e3b` and [CI run 41189114063](https://github.com/min-seokkim/agent-work-kit/actions/runs/41189114063) identify the delivered boundary.

This operational option adds no failure-catalogue entry or guard mapping. Existing channel guards retain their meanings. Any later native probe must use an owned disposable channel after the reviewer pauses its temporary helper; it must not consume a real channel cursor or change power settings.

## Next action

Reuse the delivered option and storage summary view. No review or delivery stage remains for this cumulative unit; read the completed receipt before repeating checks or installation. The delivered scope includes both additive features, the F16 evidence update and the transferred planning observations. A further native trial is not assigned. The held task index and shared-storage record remain outside this records follow-up's edit scope.
