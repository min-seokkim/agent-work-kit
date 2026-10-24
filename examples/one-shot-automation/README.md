# One-shot local automation

This optional repository example records a configured task, an absent trigger, one local mock effect and stopping, or a failed attempt. Each review invocation creates a separate job in a disposable worktree. The scripts run only when explicitly invoked; they register no schedule or listener.

The fixed [task](task.toml), [signal](input/signal.json) and [expectations](expected.json) precede execution. The task permits one append of `mock effect DEMO-ONE` followed by a newline to its local delivery/effect.txt. failure.json is its local failure notification. No external recipient is involved.

## Run the four cases

From the repository root, create a snapshot of this example, its test file and CHANGELOG, or use their full checked commit ID. Replace SNAP below with that ID. Keep generated jobs inside review worktrees; the scripts refuse preparation over an existing job root and provide no reset command.

```sh
awkit review check SNAP --config examples/one-shot-automation/checks/configured.toml
awkit review check SNAP --config examples/one-shot-automation/checks/no-trigger.toml
awkit review check SNAP --config examples/one-shot-automation/checks/fired.toml
awkit review check SNAP --config examples/one-shot-automation/checks/failed.toml
```

| Case | Observed state | Review result |
|---|---|---|
| configured | Configuration retained; no trigger observation or attempt | Pass |
| no-trigger | One observation finds no signal; zero attempts | Pass, without an action-completion claim |
| fired | Signal deliberately staged; one effect; second observation skips the stopped job | Pass |
| failed | A retained file blocks the effect's parent directory; one failed append; second observation skips | Fail intentionally; later evidence checker passes |

The failed action is a check step so later checks still run. It returns 1, writes failure.json and leaves the overall review failed. A setup error, timeout, missing record or unexpected mismatch is a separate defect. Preserve that run when correcting anything later.

## Inspect retained evidence

The run folder retains configuration, logs, state, observations, fixed inputs, produced effect or failure, and an artifact manifest. Output files exist under its artifacts subtree after worktree cleanup. Replace RUN with the reported run directory:

```sh
awkit review verify RUN
python examples/one-shot-automation/check_output.py failed --root RUN/artifacts/examples/one-shot-automation
```

The first command checks retained bytes; the second compares the failed case's evidence with its fixed expectations. Both may pass while the action's review remains failed. The checker rejects missing records, changed effect bytes and contradictory stopping evidence.

Read the [automation guide](../../kit/work-types.md#automation) and [task record](../../docs/tasks/one-shot-automation-example.md) for scope. This sequential mock demonstrates no unattended execution, concurrency or crash/power-loss safety, cross-run idempotency, production receipt or real F27 occurrence. Mechanical checks and agent reading do not establish a person's acceptance.
