# One-shot automation example

## Current status

Completed example, delivered in `5b943d0`. Four local mock cases distinguish configuration, an absent trigger, one effect followed by stopping, and a retained failure.

Next action: Reuse the example when needed. Production scheduling, concurrency and cross-run idempotency require separately selected real work.

## Earlier scope and evidence

The following sections retain the original assignments and observations. Their stage-specific status statements are historical; use the current status above when resuming.

Status: delivered in `5b943d0` for roadmap item 7. The local mock example compares a configured trigger and stopping condition with actual execution records. Its four cases distinguish setup, a missing trigger, one local effect followed by stopping, and a failed action with retained evidence.

## Existing behavior and boundary

The [automation guide](../../kit/work-types.md#automation) requires trigger, inputs, allowed actions, stop condition and failure notification, and distinguishes a one-shot task from a recurring schedule. Its F27 occurrence remains a real-use question; a fictional exercise does not supply one.

The [review example](../../examples/review/checks.toml) has explicit setup and check commands. The [data example](../../examples/first-run/data/checks.toml) retains input and output artifacts. The existing review runner invokes those commands when requested and records their results. It does not monitor events or register schedules. Use that machinery for the example and keep scheduler ownership with the user's existing platform. No new scheduler, background listener or provider lifecycle manager is proposed.

## Accepted execution contract

An example-local TOML names one local input signal, its permitted output, a single-attempt stopping condition and a local failure record. Preparation records configuration without claiming an action ran. A missing signal produces no output. A deliberate fixture event invokes the local handler, which retains its one effect and terminal record. Another observation in the same singly owned, sequential job leaves the effect unchanged. A failed action records failure and returns nonzero without claiming the output exists.

Label the executed action as a local mock firing. No OS or provider schedule is registered, and the example does not establish unattended production execution or a global exactly-once guarantee. A separately requested review invocation starts a new example run. Concurrency, crashes, power loss and cross-run idempotency remain outside this example; evidence from the separate collaboration persistence experiment cannot establish them here.

## Fixed acceptance before implementation

Use independent fixture inputs and expected results. Retain the configuration, input identity, configured record, event and effect records, and output where produced through existing review artifacts. The verifier must distinguish setup-only, no-trigger, fired-and-stopped and failed-action cases. Missing required records cannot pass. Keep the failed run when a later correction passes. Existing `review verify` establishes retained bytes, not a real-world trigger or receipt by a recipient.

Choose exact files in a bounded preparation contract. Prefer standard-library code and a repository-only example. Tests should exercise observed effects and stopping, with no new runner schema, hook or dependency. The local record is the mock failure notification; email, external recipients and settings are outside scope. Do not create scheduled tasks or leave running processes.

## Handoff and evaluation

Preparation returned in `R-031`, was accepted in `M-055`, and implementation was assigned in `M-056`. Ownership is eleven files under `examples/one-shot-automation/`, `tests/test_one_shot_automation_example.py` and CHANGELOG. The contract fixes an append effect so duplicate attempts leave detectable extra bytes, refuses existing job roots, and uses a retained regular-file blocker for the intentional write failure. Four existing-schema check configurations keep configured-only, no-trigger, fired and failed evidence separate. The failed action runs as a check, so a subsequent stopped observation and verifier can run while the overall review remains failed. Planning owns scope, records and integrated delivery; the implementation session owns the assigned example and focused checks. No runtime result or production automation is established by this assignment.

One scout located the existing guide, configurations, runner entry points and tests; planning then read the relevant materials. Execution metadata identifies `gpt-6-luna` with low effort for its one assigned turn. Its log reports 46,715 fresh input tokens, 195,456 cached input tokens and 1,329 output tokens, excluding planning. No tests or external actions ran in scouting, and no delegation advantage is measured. Local preparation and metadata are under `.awkit/handoffs/automation-example/`.

## Candidate review

Candidate `1c1c172` returned in `R-033` and was accepted in `M-059`. The frozen focused run `.awkit/reviews/review-tvxfwe20` passed Ruff, sixteen tests with two Windows symlink-privilege skips, writing checks and original-to-frozen comparisons of the three fixed inputs. Eight tests exercise the new example; the remainder cover existing runner, artifact and documentation behavior. No unexpected implementation failure was reported. The initial local unittest process passed despite PowerShell wrapping its stderr as NativeCommandError.

| Case | Run under .awkit/reviews | Action review | Retained verification |
|---|---|---|---|
| Configured | review-hn6dx8eo | Passed; no observation or attempt | Bytes and expected records passed |
| No trigger | review-g6yphoya | Passed; one observation and zero attempts | Bytes and expected records passed |
| Fired | review-wf646fy1 | Passed; one 21-byte append, unchanged by the second observation | Bytes and expected records passed |
| Failed | review-5awdub64 | Intentionally failed; check exits 1, 0, 0 | Bytes and expected failure records passed |

The failed append encountered a retained regular-file blocker and recorded FileNotFoundError on Windows. Its second observation skipped the stopped job without retrying. Passing retained-byte verification and the evidence checker did not change the failed action's result. The fixed inputs preceded execution; expected bytes were not copied from produced output.

Planning read the actor, checker, tests, configurations, focused results and retained effect, failure and observation records against the contract. It inspected the README and CHANGELOG rendered in local Edge at 1200 px without clipping. A BOM in the temporary render-target JSON initially prevented rendering; removing that marker corrected the preview without changing product files. Local review receipts remain under `.awkit/handoffs/automation-example/`. This acceptance covers the thirteen-file candidate, not the other changed planning records or the whole repository. Human acceptance and real F27 occurrence remain unestablished.

## Delivery

The sixteen-file integrated snapshot `0801a91` passed Ruff and 352 tests with seven skips in `.awkit/reviews/review-g71ze8k3`. The whole-tree done check matched, and commit `5b943d0` has that snapshot's tree. All seventeen Windows/Linux jobs passed in [CI run 40061184828](https://github.com/min-seokkim/agent-work-kit/actions/runs/40061184828). The platform installer installed that exact commit; provenance, 26 source files, 29 kit files and sixteen user-skill payloads matched after recorded line-ending normalization. Local receipts are under `.awkit/handoffs/automation-example-delivery/`. Later presentation planning edits are outside this delivered snapshot.
