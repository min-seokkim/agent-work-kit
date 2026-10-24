# One-shot automation example

Status: planning for roadmap item 7. No implementation is assigned. Produce a local mock example whose configured trigger and stopping condition can be compared with its actual execution record. Completion requires distinguishing setup, a missing trigger, one local effect followed by stopping, and a failed action with retained evidence.

## Existing behavior and boundary

The [automation guide](../../kit/work-types.md#automation) requires trigger, inputs, allowed actions, stop condition and failure notification, and distinguishes a one-shot task from a recurring schedule. Its F27 occurrence remains a real-use question; a fictional exercise does not supply one.

The [review example](../../examples/review/checks.toml) has explicit setup and check commands. The [data example](../../examples/first-run/data/checks.toml) retains input and output artifacts. The existing review runner invokes those commands when requested and records their results. It does not monitor events or register schedules. Use that machinery for the example and keep scheduler ownership with the user's existing platform. No new scheduler, background listener or provider lifecycle manager is proposed.

## Proposed execution

An example-local TOML names one local input signal, its permitted output, a single-attempt stopping condition and a local failure record. Preparation records configuration without claiming an action ran. A missing signal produces no output. A deliberate fixture event invokes the local handler, which retains its one effect and terminal record. Another observation in the same singly owned, sequential job leaves the effect unchanged. A failed action records failure and returns nonzero without claiming the output exists.

Label the executed action as a local mock firing. No OS or provider schedule is registered, and the example does not establish unattended production execution or a global exactly-once guarantee. A separately requested review invocation starts a new example run. Concurrency, crashes, power loss and cross-run idempotency remain outside this example; evidence from the separate collaboration persistence experiment cannot establish them here.

## Fixed acceptance before implementation

Use independent fixture inputs and expected results. Retain the configuration, input identity, configured record, event and effect records, and output where produced through existing review artifacts. The verifier must distinguish setup-only, no-trigger, fired-and-stopped and failed-action cases. Missing required records cannot pass. Keep the failed run when a later correction passes. Existing `review verify` establishes retained bytes, not a real-world trigger or receipt by a recipient.

Choose exact files in a bounded preparation contract. Prefer standard-library code and a repository-only example. Tests should exercise observed effects and stopping, with no new runner schema, hook or dependency. The local record is the mock failure notification; email, external recipients and settings are outside scope. Do not create scheduled tasks or leave running processes.

## Next handoff and evaluation

Prepare the implementation contract after the current document-intent package returns. Planning owns scope and acceptance, the implementation session owns the assigned example and focused checks, and planning integrates and delivers it. The contract must explain how existing runner steps retain evidence without confusing their success with a real automation deployment. No source files or executable behavior change with this plan.

One scout located the existing guide, configurations, runner entry points and tests; planning then read the relevant materials. Execution metadata identifies `gpt-6-luna` with low effort for its one assigned turn. Its log reports 46,715 fresh input tokens, 195,456 cached input tokens and 1,329 output tokens, excluding planning. No tests or external actions ran in scouting, and no delegation advantage is measured. Local preparation and metadata are under `.awkit/handoffs/automation-example/`.
