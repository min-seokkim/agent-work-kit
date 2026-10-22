# Failure Catalogue

Agents fail in recognizable situations, in recognizable ways. This catalogue lists those failures. It is a design document: it chooses the kit's situation guards (skills, hooks, `awkit` checks, situation guidance), measures whether they catch anything, and shows what to remove. It is not given to agents. Agents get the baseline workflow and the guards, written as what to do, with a failure as the reason where it helps. See Scope in [development.md](development.md).

Entries observed while developing this repository cite commits on `dev`. Entries carried over from the existing kit were written from earlier sessions whose records were not kept; they are marked "needs evidence" until a real occurrence is recorded. The repository owner is collecting the patterns they actually corrected when having AI write documents; those will be merged here.

## Rules for entries

An entry needs four things: the situation that triggers it (so the countermeasure can be loaded only then), the failure as it shows in the output, at least one recorded occurrence, and a check that would have caught that occurrence. Prefer checks a machine runs (a test, an `awkit` command, a hook) over instructions; use instructions only where no check is possible, and say so. Remove an entry, and the kit text that serves it, when it has not been seen in real work for a long time.

Mechanism status: `enforced` means a check runs without the agent choosing to; `tool` means `awkit` records or verifies it when the agent uses it; `prose` means only an instruction exists; `planned` names the check to build.

## Entries

### Reporting work as done

#### F1. Done without a check on the delivered version.

The agent reports success, but the checks ran on another state of the files, or did not run.
- Evidence: needs evidence (the project's premise; recorded occurrences wanted).
- Countermeasure: check a frozen snapshot and report its run folder.
- Check: `awkit review check` result for the reported revision. Status: tool; planned: a Stop hook that refuses a "done" report without a passing run for the current snapshot.

#### F2. The first failure disappears.

A check fails, a rerun passes, and the report mentions only the pass.
- Evidence: needs evidence.
- Countermeasure: keep every run; explain or list the first failure.
- Check: run folders are kept per run. Status: tool, prose for the reporting.

#### F3. Support claimed for environments that were not run.

Tests pass on one platform and the work is reported as working everywhere.
- Evidence: observed here. Tests passed on Linux; the first Windows CI run on `dev` failed two tests (path ordering, 8.3 short names), fixed in `a5eec42`.
- Countermeasure: name the environments a claim covers; run all of them before claiming.
- Check: CI matrix for this repository. Status: enforced here, prose for user projects; planned: profile field for target environments that the done-check reads.

### Describing behavior in documents and commit messages

#### F4. Documents describe behavior the code does not have.

The text states what the change was meant to do; the code does something else, and the test covers only the easy case.
- Evidence: observed here. `f475f9e` documented that an example created inside an existing repository is committed there; the code skipped any repository that already had a commit, and the test used a repository without one. The example's first command then failed. Fixed in `b5d78ba`.
- Countermeasure: for each behavior stated in a document, a test that exercises exactly that case.
- Check: planned: run the commands in example READMEs in CI as written.

#### F5. Documents point at things that do not exist.

Install instructions, links or files that were never created.
- Evidence: observed here. The README told users to download the 0.2.0 wheel from Releases; no tag or release had ever existed. The README's development command failed as written because of a relative `PYTHONPATH` (fixed in `6eb632c`).
- Countermeasure: run every documented command; check that referenced releases and files exist.
- Check: relative links are tested. Status: partial; planned: documented commands run in CI.

#### F6. Numbers reported beyond what was measured.

A count from part of the data is stated as the whole, or a metric counts things it should not.
- Evidence: observed here. The kit's size was given as about 10,800 words from a count that left out `kit/examples/` (about 800 more words). `awkit usage` counted notices and command output as user messages (13 instead of 9 in a real log; fixed in `6eb632c`).
- Countermeasure: state the scope of every number; check a metric against one real record before using it.
- Check: prose; for `usage`, a test built from a real log's record kinds.

### Choosing defaults and side effects

#### F7. A convenience changes state nobody asked to change.

A read or check command creates, commits or deletes something.
- Evidence: observed here. `review compare` in a folder without Git created a repository and committed every file, `.env` included (from `f475f9e`, fixed in `b5d78ba`).
- Countermeasure: read commands never write; write commands touch only what was named.
- Check: tests that read commands leave the folder unchanged. Status: enforced for `awkit`.

#### F8. The user's unrelated work is bundled in.

A commit or snapshot includes changes the user had staged or made elsewhere.
- Evidence: found while fixing F7; not observed in use.
- Countermeasure: commit only named paths; skip when the index has staged changes.
- Check: enforced in `kit init` and `kit example`; snapshots include only named files.

### Committing and publishing

#### F9. The agent's own identity replaces the repository's convention.

Commits are authored as the agent, or carry trailers the owner did not ask for.
- Evidence: observed here. Commits on `dev` were authored as "Claude" with `Co-Authored-By` lines while the owner's commits used their own identity; the history had to be rewritten and force-pushed.
- Countermeasure: read the existing history's author and message conventions before the first commit.
- Check: planned: a pre-commit hook comparing author and trailers with the repository's recent commits.

#### F10. Irreversible publication prepared before it is justified.

Version bumps, release workflows or uploads set up while the interface is still changing.
- Evidence: observed here. A PyPI release was prepared (`cb24596`) before the kit split and real-use measurement; the owner held it (`5a2ad25`).
- Countermeasure: written release conditions; no tag until they are met.
- Check: prose (release conditions in `docs/development.md`).

### Proposing and inferring

#### F11. A guess is presented as a finding.

An inference from file names or conventions is reported as how the project works.
- Evidence: observed here. `kit scan` suggested pytest for any `tests` folder; this repository uses unittest (fixed in `6eb632c`).
- Countermeasure: mark inferences; run a suggested command once before relying on it.
- Check: the connect procedure runs the drafted checks once. Status: prose plus tool.

#### F12. Scope grows before anything is measured.

Features and documents are added because they seem useful, before real use shows a need.
- Evidence: observed here. The release runner was widened to every kind of delivery and documentation grew to several thousand words for readers who did not read it (`8cf8e72`, restructured in `8f93b7b`).
- Countermeasure: a feature needs a failure entry here and a check; measure on real tasks before widening.
- Check: prose; the kit word limit test bounds documentation.

### Writing for people

#### F13. AI writing patterns in English.

Contrasts against claims nobody made, lead-ins, closing lines that repeat the paragraph, slogans, bold labels, dashes, sales words.
- Evidence: observed here. The first rewrite of the README (owner's feedback, corrected in `8f93b7b`).
- Countermeasure: the pattern list in `docs/development.md`; the owner's collected patterns when merged.
- Check: planned: a writing check that flags the listed patterns.

#### F14. Korean that reads like a translation, including from an agent that wrote the rules.

Translationese, mixed sentence endings, noun chains; the agent's own Korean guide not applied to its own output.
- Evidence: observed here. The Korean README and replies before the owner pointed it out.
- Countermeasure: `kit/korean-writing.md` applied to every Korean text, including the agent's replies.
- Check: planned: Korean patterns in the same writing check.

#### F15. Writing for the wrong reader.

Long human-oriented documents for a tool whose user is an agent, or agent details in what people read.
- Evidence: observed here. Five human-oriented documents under `docs/` that neither the owner nor agents needed in that form (restructured in `8f93b7b`).
- Countermeasure: decide the reader of each document first; people get the README only.
- Check: prose.

#### F30. Facts or certainty change during rewriting.

A rewrite for style drops a number, condition or exception, turns a possibility into a certainty or a permission into an obligation, or claims something was verified when only the wording changed.
- Evidence: needs evidence (carried over from `kit/korean-writing.md`).
- Countermeasure: list what must be preserved before rewriting and check the text against the list.
- Check: prose.

### Revising approved work

#### F16. Approved work regresses during a later change.

A revision passes its checks but loses what the user had accepted.
- Evidence: needs evidence (carried over from `kit/work-types.md`).
- Countermeasure: keep the accepted version; compare every revision with it.
- Check: `awkit review accept` and `compare`. Status: tool.

### Review

#### F17. The reviewed version is not the shipped version.

The author keeps editing during review, or the reviewer has seen the author's reasoning.
- Evidence: needs evidence.
- Countermeasure: review a snapshot ID; use a fresh session that did not see the implementation.
- Check: `awkit review snapshot`, `channel --snap`. Status: tool.

#### F18. Review never ends.

Each fix produces new findings and more premium calls.
- Evidence: needs evidence (carried over from `kit/delegation.md`).
- Countermeasure: one premium call by default, a stated reason for a second, a cap of three, then a user decision.
- Check: prose; `awkit usage` shows the calls afterwards.

### Delegation

#### F19. Parallel subagents make conflicting decisions.

Interfaces, names or error handling diverge because each subagent decided alone.
- Evidence: needs evidence.
- Countermeasure: settle shared decisions before parallel work and give every handoff the same wording.
- Check: prose.

#### F20. A subagent's self-report is trusted.

The model, permissions or work claimed by a subagent are not what happened.
- Evidence: needs evidence.
- Countermeasure: read the actual model and permissions from logs.
- Check: `awkit usage`. Status: tool for models, prose for permissions.

#### F21. Handoffs carry too much or too little.

The whole conversation or repository is passed, or a decision the subagent needs is missing.
- Evidence: needs evidence (size limits come from 55 handoffs in one project).
- Countermeasure: four-part handoff with size limits; `NEEDS_CONTEXT` status.
- Check: prose.

### Data and analysis

#### F22. Observations, assumptions and interpretation are mixed.

A computed value depends on an unstated or wrong assumption, or an interpretation is presented as a result.
- Evidence: needs evidence (the analysis example reproduces it).
- Countermeasure: assumptions in a file checked against the data; a report with separate parts; interpretation by a person.
- Check: the analysis example's check script shows the pattern. Status: prose plus example.

#### F23. Contradicting sources are averaged.

Research merges disagreeing sources into one claim.
- Evidence: needs evidence.
- Countermeasure: show contradictions and gaps; cite what was read.
- Check: prose.

### Operating environments and applications

#### F24. A tool's success is taken as the result.

A command returned 0, so the message is assumed delivered, the file transferred, the setting applied or the release live.
- Evidence: needs evidence (the release runner was built for the deploy case).
- Countermeasure: observe the end state where the recipient sees it.
- Check: `awkit pipeline` verifies the running release. Status: tool for releases, prose otherwise.

#### F25. Instructions for another version are applied.

Setup steps from documentation for a different edition, OS or account type.
- Evidence: needs evidence.
- Countermeasure: confirm version, OS and account type before following found instructions.
- Check: prose.

#### F26. Checks interfere through shared resources.

Parallel or repeated checks share a database, port or device and fail or pass for the wrong reason.
- Evidence: needs evidence.
- Countermeasure: allocate resources per run ID; run single-device checks one at a time.
- Check: `{run_id}` placeholders. Status: prose plus tool.

#### F27. A one-off request becomes a standing automation.

"Just this once" ends as a registered schedule, or a test run is reported as the real run.
- Evidence: needs evidence.
- Countermeasure: confirm once or recurring; record the first real run and the removal separately.
- Check: prose.

### Working with the user over time

#### F28. The wrong level of autonomy.

The agent does the work when the user wanted to learn or decide, or only advises when the user wanted it done.
- Evidence: needs evidence.
- Countermeasure: settle the form of help at the start and record it in the handoff.
- Check: prose.

#### F29. Context is lost between sessions.

The user explains the project again, or an interrupted external operation is repeated.
- Evidence: needs evidence (the README lists it as a common case).
- Countermeasure: project profile; checkpoint with the next action; verify actual state before resuming.
- Check: prose plus templates.

## Current kit mapped to entries

Each section of the kit and the entries it serves. Sections marked "none" serve no entry; for each, decide whether the baseline workflow needs it, and otherwise move it to `kit/reference.md` or remove it.

| File | Section | Words | Entries |
|---|---|---|---|
| templates/agent-instructions.md | Connect the kit to a project | 291 | F11, F12, F29 |
| | Start work | 41 | F8, F19 |
| | Implement and verify | 71 | F1 |
| | Report and resume | 52 | F14, F29 |
| workflow.md | Define the task | 128 | F12, F18 |
| | Delegate work | 84 | F19, F21 |
| | Review independently | 280 | F17, F26 |
| | Interpret check results | 76 | F2, F3 |
| | Deliver results | 165 | F24 |
| | Publish documents and AI summaries | 181 | F7, F14; the AI summary rules serve no entry yet |
| | Continue across sessions | 41 | F29 |
| protocol.md | A task record, States | 239 | F1 (session end is not done); the state table itself: none |
| | Roles and file ownership | 72 | F19 |
| | Check evidence | 96 | F1, F3 |
| | Reviews and decisions | 73 | F18 |
| | Resume after interruption | 65 | F29 |
| | Connect optional tools | 95 | none (tool semantics; belongs in the reference) |
| work-types.md | Common rules | 384 | F16, F22, F24, F28 |
| | Research | 123 | F23 |
| | Writing | 177 | F13, F14, F16 |
| | Data preparation and analysis | 225 | F22 |
| | Environment setup | 224 | F24, F25 |
| | Operating an application | 114 | F24 |
| | Learning | 121 | F28 |
| | Automation | 77 | F27 |
| delegation.md | 1 Objective | 85 | none (policy) |
| | 2 When to delegate | 164 | F19, F21 |
| | 3 Risk and premium calls | 241 | F18 |
| | 4 Roles and execution paths | 376 | F19, F20; the path table: none |
| | 5 Handoffs and results | 262 | F21 |
| | 6 Failures and retries | 123 | F18 |
| | 7 Model tiers | 151 | F20 |
| | 8 Measurement | 208 | none (evaluation method; belongs with real-use measurement) |
| review-session.md | 1 Purpose and cost, 2 Session setup | 208 | F17 |
| | 3 Work through a unit, 4 Review criteria | 406 | F2, F17, F18 |
| | 5 Commands, 6 Waiting | 346 | none (tool usage; belongs in the reference) |
| | 7 Records and evaluation, 8 Starting prompts | 177 | F20; the prompts: none |
| korean-writing.md | all sections | 1,297 | F14, F30 |
| templates/project.md | Start here | 59 | F11, F29 |
| | Deliverables and completion | 195 | F3, F24 |
| | Delegation and models | 109 | F18, F19, F20 |
| | Other sections | 439 | none directly (fields); review which fields any entry needs |
| templates/task.md, review.md, decision.md, checkpoint.md | | 811 | F1, F17, F12, F29 |
| templates/roles/README.md | | 316 | F20 |

Sections marked "none" total roughly 1,700 words and are reviewed against the baseline workflow. Entries F4, F5, F9 and F13 have no kit text at all, and F30 is served only through the Korean guide; they are the first candidates for checks (planned items above).
