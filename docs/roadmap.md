# Roadmap

Remaining work and its completion criteria. Item numbers retain the earlier development record's references; they do not authorize implementation or set a new priority. The owner chooses the next task. Candidate checks and conditional extensions keep their stated prerequisites. Completed items are in the [evidence record](evidence.md#completed-work).

[Development](development.md) summarizes what exists. Task documents hold detailed plans, ownership and progress.

## Next work

| Item | Work | State, prerequisites and completion criteria |
|---|---|---|
| 1 | Complete the failure catalogue | Done for the owner's records: their writing corrections (F1, F13 to F15, F29 to F34) and their corrections from research, explanation, troubleshooting and purchase conversations (F11, F12, F28, F35 to F39) are merged. The twelve entries still marked "needs evidence" (F2, F16 to F24, F26, F27; F25 got an occurrence from a stale cloud checkout) concern review sessions, delegation, data work and operations, which those records do not cover; they get occurrences from the real tasks in 5 or are removed then. |
| 2a | Candidate checks from the guides | Not built. From a review of each guide section for what could be checked: a hook asking for a state check before install commands (F11); a SessionStart hook printing the latest checkpoint (F29); a hook refusing edits outside the files a task names (F19); call counts from `awkit usage` against the premium-call cap (F18); handoff sizes measured against the limits (F21). Each is built only when item 5 shows its failure occurring, as a rule in `rules.toml` where its situation shows in a tool call. |
| 5 | Measure real work, starting with this repository | Started: this repository is developed with its own kit from `6482bc7` (cloud session hook, `checks.toml`, skills, Stop hook). Per task, record three values in the [measurement record](evidence.md#measurement-record) (`awkit hook report` adds how often each rule fired and blocked): messages in which the user repeated an instruction already given, tokens (`awkit usage`), and catalogue entries that occurred or that a guard caught. No run of the same task without the kit: done twice by the same person, the second run starts from knowing the answer, so the two cannot be compared. F16 (accepted work regressing) and F17 (a reviewed version that is not the shipped one) are the entries awkit's own loop guards, so the main question is whether they occur in this repository. Then one document task and one data task in other projects, and one existing project connected with `kit scan`, recording how many drafted commands were right. |
| 6 | Check usage against current logs | Partly done: a message typed while a turn runs is recorded only as a queued-command attachment and was not counted; `536c0ea` counts it (this session: 51 messages before, 56 after). Still to compare: format 2 tokens with what Claude Code and Codex show, and how Codex records a message sent during a turn. |
| 7 | One-shot automation example | A mock example whose trigger and stop condition live in a config file, recording setup and the actual firing separately, using the existing check runner and artifacts. |
| 8 | Task start lookup | After 5 settles the record format: extend `kit scan` to read runs, accepted versions and checkpoints and summarize state and the next action. |
| 9 | Channel receipts | Only if 5 shows several sessions reading as one role, or a need to separate "read" from "handled": per-consumer positions and explicit acknowledgement. |
| 10 | Hand-off to another environment | Export and import of request ID, base revision, retained artifacts and replies, with repeated-input and version-mismatch checks. Remote transport after two real environments are chosen. |
| 11 | Coordinate independent work sessions | Extend the existing channel after the current installation, snapshot and hook defects are fixed, preserving its small dependency and setup burden. Start with the [validation priorities](tasks/independent-session-collaboration.md). A coordinating session assigns work across independent sessions with roles chosen for the task, receives results, checks evidence and sends follow-up requests without the user relaying each prompt and report. Items 9 and 10 remain conditional on demonstrated need. |

## Task plans

- [Connection diagnostics](tasks/connection-diagnostics.md): reproduced configuration and runtime-origin gaps, implemented diagnostics, and unresolved writing-scope and sandbox-path questions.
- [Document workflow](document-workflow-plan.md): the separately maintained plan for document creation, with presentations as its first application.
- [Independent-session collaboration](tasks/independent-session-collaboration.md): requested outcome, validation order and conditional protocol extensions for item 11.
- [Local collaboration trial](tasks/local-collaboration.md): installation results, hook findings and the assigned Python 3.14 support work.
- [Documentation restructuring](tasks/documentation-restructure.md): document ownership and observation of awkit during this task.

Whether the skills-only bundle helps without executable checks remains part of item 5; its packaging is already recorded as completed item 6a.
