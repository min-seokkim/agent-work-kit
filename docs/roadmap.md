# Roadmap

Remaining work and its completion criteria. Item numbers retain the earlier development record's references; they do not authorize implementation or set a new priority. The owner chooses the next task. Candidate checks and conditional extensions keep their stated prerequisites. Completed items are in the [evidence record](evidence.md#completed-work).

[Development](development.md) summarizes what exists. Task documents hold detailed plans, ownership and progress.

## Next work

| Item | Work | State, prerequisites and completion criteria |
|---|---|---|
| 1 | Complete the failure catalogue | Done for the owner's records: their writing corrections (F1, F13 to F15, F29 to F34) and their corrections from research, explanation, troubleshooting and purchase conversations (F11, F12, F28, F35 to F39) are merged. The twelve entries still marked "needs evidence" (F2, F16 to F24, F26, F27; F25 got an occurrence from a stale cloud checkout) concern review sessions, delegation, data work and operations, which those records do not cover; they get occurrences from the real tasks in 5 or are removed then. |
| 2a | Candidate checks from the guides | Not built. From a review of each guide section for what could be checked: a hook asking for a state check before install commands (F11); a SessionStart hook printing the latest checkpoint (F29); a hook refusing edits outside the files a task names (F19); call counts from `awkit usage` against the premium-call cap (F18); handoff sizes measured against the limits (F21). Usage-based enforcement also depends on item 6 establishing what counts as a call. Each is built only when item 5 shows its failure occurring, as a rule in `rules.toml` where its situation shows in a tool call. |
| 5 | Measure real work, starting with this repository | Started: this repository is developed with its own kit from `6482bc7` (cloud session hook, `checks.toml`, skills, Stop hook). Per task, record three values in the [measurement record](evidence.md#measurement-record) (`awkit hook report` adds how often each rule fired and blocked): messages in which the user repeated an instruction already given, tokens (`awkit usage`), and catalogue entries that occurred or that a guard caught. No run of the same task without the kit: done twice by the same person, the second run starts from knowing the answer, so the two cannot be compared. F16 (accepted work regressing) and F17 (a reviewed version that is not the shipped one) are the entries awkit's own loop guards, so the main question is whether they occur in this repository. Then one document task and one data task in other projects, and one existing project connected with `kit scan`, recording how many drafted commands were right. |
| 6 | Check usage against current logs | Claude queued-message coverage was corrected in `536c0ea`. Format 3 in `7977b35` makes modern human observations visible, separates interaction coverage and keeps ambiguous exact counts unknown; local checks pass, delivery is pending. The [compatibility record](tasks/usage-log-compatibility.md) retains the mixed-stream, identity and client limits. Fresh client samples, unique-turn/API-call meaning and bounded task usage remain open; token arithmetic was preserved, not newly validated against client totals. |
| 7 | One-shot automation example | A mock example whose trigger and stop condition live in a config file, recording setup and the actual firing separately, using the existing check runner and artifacts. |
| 8 | Task start lookup | After 5 settles the record format: extend `kit scan` to read runs, accepted versions and checkpoints and summarize state and the next action. |
| 9 | Channel receipts | Only if 5 shows several sessions reading as one role, or a need to separate "read" from "handled": per-consumer positions and explicit acknowledgement. |
| 10 | Hand-off to another environment | Export and import of request ID, base revision, retained artifacts and replies, with repeated-input and version-mismatch checks. Remote transport after two real environments are chosen. |
| 11 | Coordinate independent work sessions | Extend the existing channel after the current installation, snapshot and hook defects are fixed, preserving its small dependency and setup burden. Start with the [validation priorities](tasks/independent-session-collaboration.md). A coordinating session assigns work across independent sessions with roles chosen for the task, receives results, checks evidence and sends follow-up requests without the user relaying each prompt and report. Items 9 and 10 remain conditional on demonstrated need. |

## Task plans

- [Planning and implementation trial](tasks/planning-implementation.md): bounded assignments from existing plans, product acceptance and feedback from using awkit during implementation.
- [Usage log compatibility](tasks/usage-log-compatibility.md): reproduced modern-message gap, uncertain turn counts and acceptance criteria for reliable measurement.
- [Document workflow trial](tasks/workflow-review.md): live proposal-writing evidence, check-scope explanations and collaboration with an existing user session.
- [Connection diagnostics](tasks/connection-diagnostics.md): reproduced configuration and runtime-origin gaps, implemented diagnostics, and unresolved writing-scope and sandbox-path questions.
- [Document workflow](document-workflow-plan.md): the separately maintained plan for document creation, with presentations as its first application.
- [Independent-session collaboration](tasks/independent-session-collaboration.md): requested outcome, validation order and conditional protocol extensions for item 11.
- [Local collaboration trial](tasks/local-collaboration.md): installation results, hook findings and the assigned Python 3.14 support work.
- [Documentation restructuring](tasks/documentation-restructure.md): document ownership and observation of awkit during this task.

Whether the skills-only bundle helps without executable checks remains part of item 5; its packaging is already recorded as completed item 6a.

## Follow-up from the document trial

The [trial](tasks/workflow-review.md) supplies one real document case for item 5. `89549b7` clarifies check/report scope; it does not enforce reading quality or classify existing findings. The reviewer reported useful snapshot-based review and handoff, alongside heavy procedure for short changes. Treat that account as experience to investigate, not measured productivity.

| Work | Next bounded result | Completion boundary |
|---|---|---|
| Scale document work to the change | Exercise the [scoped document trial](document-workflow-plan.md#scale-the-work-to-the-change) on a local correction and a substantive revision. | Preserve required evidence while recording preparation, review, execution, waiting and missed defects separately; passing commands must not hide omitted reviews. Presentation phases remain open. |
| Separate old and introduced writing findings | Define baseline ownership and ambiguous correspondence using the [diagnostic cases](tasks/connection-diagnostics.md#writing-scope-and-path-limits). | Keep full-file findings visible and test contextual changes; display and exit-code policy require an explicit decision. |
| Diagnose the automatic Stop-hook import failure | Capture the [failing automatic invocation](tasks/connection-diagnostics.md#automatic-hook-import-investigation) and compare the direct shell under identified permissions. | A direct import or matching installation cannot establish restored automatic execution. |
| Preserve the working collaboration path | Exercise [receipt and closure recovery](tasks/independent-session-collaboration.md#lessons-from-the-proposal-trial) using existing commands. | Delivered and checked versions match, requests are answered, and retries do not repeat external actions. Extra channel infrastructure remains conditional. |

Usage compatibility in item 6 is a prerequisite for quantitative cost or call-limit claims. Hook reproduction can proceed separately. These are planning dependencies; the owner still chooses implementation order. The design decision against expanding `check done` remains in force.
