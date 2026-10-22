# Failure Catalogue

Agents fail in recognizable situations, in recognizable ways. This catalogue lists those failures. It is a design document: it chooses the kit's situation guards (skills, hooks, `awkit` checks, situation guidance), measures whether they catch anything, and shows what to remove. It is not given to agents. Agents get the baseline workflow and the guards, written as what to do, with a failure as the reason where it helps. See Scope in [development.md](development.md).

Entries observed while developing this repository cite commits on `dev`. Entries carried over from the existing kit were written from earlier sessions whose records were not kept; they are marked "needs evidence" until a real occurrence is recorded. Evidence marked "owner's records" comes from the repository owner's own record of the corrections they made while having agents write documents (project and operations documents, reports for non-developers, UI text and CLI output, resumes and application letters) and while using agents for research, explanations, troubleshooting and purchase decisions. The records stay outside this repository; occurrences are described here without names or dates.

## Rules for entries

An entry needs four things: the situation that triggers it (so the countermeasure can be loaded only then), the failure as it shows in the output, at least one recorded occurrence, and a check that would have caught that occurrence. Prefer checks a machine runs (a test, an `awkit` command, a hook) over instructions; use instructions only where no check is possible, and say so. Remove an entry, and the kit text that serves it, when it has not been seen in real work for a long time.

Record the failure that recurred, not the instruction that corrected it. A correction given for one document (one page, noun endings, no bullets, five revision passes) is that document's requirement and belongs in the project's profile. Before adding an entry, check whether an existing entry already describes the same failure, and add the occurrence there instead.

Mechanism status: `enforced` means a check runs without the agent choosing to; `tool` means `awkit` records or verifies it when the agent uses it; `prose` means only an instruction exists; `planned` names the check to build.

## Entries

### Reporting work as done

#### F1. Done without a check on the delivered version.

The agent reports success, but the checks ran on another state of the files, or did not run. For documents, the text was edited but the rendered output (line breaks, tables, page fit) was never looked at.
- Evidence: owner's records. A documentation site was about to be committed with broken line breaks, which the owner found ("let's undo the commit and fix the line breaks"; "is there anything else to check before committing? I want to stop looking at this"). A table broke after IDs were replaced with long names.
- Countermeasure: check a frozen snapshot and report its run folder; for documents, inspect the rendered output before reporting.
- Check: `awkit check done`, as a Claude Code Stop hook from `awkit kit hooks --claude`: files changed in the session need a passing `review check` of exactly their current state. Status: enforced where the hook is installed, tool otherwise; rendered output is still prose. Test: `tests/test_checks.py` (changed after checking, untracked files, the hook blocking once per turn).

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
- Check: `tests/test_examples.py` runs every command in the example READMEs as written, from an example created inside a repository with history; with the `f475f9e` behavior restored it fails. Status: enforced for the examples.

#### F5. Documents point at things that do not exist.

Install instructions, links or files that were never created.
- Evidence: observed here. The README told users to download the 0.2.0 wheel from Releases; no tag or release had ever existed. The README's development command failed as written because of a relative `PYTHONPATH` (fixed in `6eb632c`).
- Countermeasure: run every documented command; check that referenced releases and files exist.
- Check: relative links and the example READMEs' commands are tested. Status: enforced for links and examples; the install commands in the READMEs are covered by next work 4.

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
- Countermeasure: read the existing history's author and message conventions before the first commit. In this repository the convention is stated in `AGENTS.md`, which coding agents read at the start of a session.
- Check: `awkit check commit` compares the author and trailer keys with the last 50 commits; installed as a `commit-msg` hook by `awkit kit hooks --git`, and run by CI on every pushed commit of this repository. Status: enforced here. Test: `tests/test_checks.py` replays the agent identity with `Co-Authored-By` and `Claude-Session` lines.

#### F10. Irreversible publication prepared before it is justified.

Version bumps, release workflows or uploads set up while the interface is still changing.
- Evidence: observed here. A PyPI release was prepared (`cb24596`) before the kit split and real-use measurement; the owner held it (`5a2ad25`).
- Countermeasure: written release conditions; no tag until they are met.
- Check: prose (release conditions in `docs/development.md`).

### Proposing and inferring

#### F11. A guess is presented as a finding.

An inference from file names or conventions is reported as how the project works; a question from the user is recorded as a confirmation.
- Evidence: observed here. `kit scan` suggested pytest for any `tests` folder; this repository uses unittest (fixed in `6eb632c`). Owner's records: a component that was already installed was installed again; files were sorted by their names without opening them; the owner's question whether a tool was allowed was recorded as the owner confirming that it was ("I was asking whether it is okay").
- Countermeasure: mark inferences; run a suggested command once before relying on it; check the current state before installing, sorting or reviewing; treat a question as a question.
- Check: the connect procedure runs the drafted checks once. Status: prose plus tool.

#### F12. Scope grows before anything is measured.

Features and documents are added because they seem useful, before real use shows a need.
- Evidence: observed here. The release runner was widened to every kind of delivery and documentation grew to several thousand words for readers who did not read it (`8cf8e72`, restructured in `8f93b7b`). Owner's records: a server for a temporary project was specified with a graphics card, more memory than the load needed and a layout for a larger organization.
- Countermeasure: a feature needs a failure entry here and a check; measure on real tasks before widening. Size a design to the purpose, duration, load and the person who will run it.
- Check: prose; the kit word limit tests bound each file by when it is read.

#### F35. The user's guess becomes the requirement.

The user, new to a field, proposes an approach; the agent builds on it and adjusts the plan to each new idea instead of evaluating it.
- Evidence: owner's records. A server layout kept changing to follow the owner's ideas until the owner said to ignore what they had said and think it through, asked what the standard layout was, and said it was their first time and the agent should bring in industry practice.
- Countermeasure: read each statement from the user as a hypothesis, a constraint or a decision. For a hypothesis, give the standard approach, the strengths and weaknesses, and the alternatives, and say when the conclusion changes and why. Disagreement names the premise or step that is wrong, not the user.
- Check: prose.

#### F36. The answer ends at "unknown".

Where the facts do not settle a question, the agent stops at the uncertainty instead of saying what can be compared, which explanation fits best and what would change the judgment.
- Evidence: owner's records. After an explanation of the market range for a role, the owner asked where their own band was. An analysis of someone's behavior concluded that it could not be known, which the owner found useless.
- Countermeasure: separate what is established, the candidate explanations, the assumptions each needs and what is unknown; give a provisional judgment with its assumptions and the observation that would change it; put no numbers or probabilities on it that the material does not support.
- Check: prose.

### Writing for people

#### F13. AI writing patterns in English.

Contrasts against claims nobody made, lead-ins, closing lines that repeat the paragraph, slogans, bold labels, dashes, sales words, promotional headlines and repeated labels.
- Evidence: observed here. The first rewrite of the README (owner's feedback, corrected in `8f93b7b`). Owner's records: em dashes in English and Korean application text; the largest line on a documentation index page was a slogan ("this is not a brochure"); every list entry carried a tag repeating its title; a README listed what the project does not do; consulting and promotional tone in reports.
- Countermeasure: the pattern list in `kit/writing.md`, which `AGENTS.md` applies to this repository.
- Check: `awkit check writing`: em dashes fail; lead-ins, contrasts, sales words warn. The test suite runs it over this repository's documents. Status: enforced here for errors; the rest of the list is judgment.

#### F14. Korean that reads like a translation, including from an agent that wrote the rules.

Translationese, mixed sentence endings, noun chains; the agent's own Korean guide not applied to its own output.
- Evidence: observed here. The Korean README and replies before the owner pointed it out. Owner's records: Korean still unnatural after an English draft and translation; `-세요` turning into `-시오` within one guide, then the same mix left in other documents; words Korean readers do not use in that sense (`정제`, `권위 순서`, `경계`, `흐름`); middle dots joining words; italics in Korean reports.
- Countermeasure: `kit/korean-writing.md` with `kit/writing.md`, applied to every Korean text, including the agent's replies.
- Check: `awkit check writing`: middle dots joining Korean words and `-세요` mixed with `-시오` fail; Korean stock phrases warn. Natural Korean remains a reader's judgment.

#### F15. Writing for the wrong reader.

Long human-oriented documents for a tool whose user is an agent, or agent details in what people read. A document for one reader is made by rewording one written for another.
- Evidence: observed here. Five human-oriented documents under `docs/` that neither the owner nor agents needed in that form (restructured in `8f93b7b`). Owner's records: tracking codes (`AB-001`, `S1` to `U8`) throughout documents people read; commit IDs and evidence references in a report for non-developers; the abbreviation ADR in an administrative form; a status report for stakeholders built from developer documents with the wording changed ("LLMs just copy the development documents"); a resume that read like a technical report; one developer's Windows and Edge setup written as everyone's.
- Countermeasure: decide the reader, what they must understand or decide, and the kind of document first; write from that, using other documents only as sources of facts. Keep tracking codes where the agent needs them and out of the text people read.
- Check: prose.

#### F30. Facts, attribution or certainty change while writing.

A rewrite drops a number, condition or exception, turns a possibility into a certainty or a permission into an obligation, or claims something was verified when only the wording changed. Shortening removes facts instead of repetition. A plan reads as what happened, or one person's or project's work is credited to another.
- Evidence: owner's records. A purchase plan read as the purchase actually made, and had to be rewritten to say what was planned and what was bought. Asked to write a status document more compactly, the agent cut content; the owner corrected that it should say the same in fewer words, over more than one page if needed. In resumes: results from two projects merged, a problem someone else found written as the owner's discovery, integration work written as ownership of the system, a technology used once listed as a skill.
- Countermeasure: list what must be preserved (facts, numbers, conditions, who did what, plan or done) before writing and check the text against the list; shorten by removing repetition and wordy phrasing.
- Check: prose.

#### F31. The form of a correction is fixed, not its reason.

After a correction, the agent changes exactly what was named and repeats the underlying problem in another form.
- Evidence: owner's records. Told not to name categories "A and B", the agent renamed them all to four-character names that still did not say what each held. Told that tracking codes were hard to read, it put long names in the ID column, which broke the table.
- Countermeasure: state the reader's problem behind the correction and check the edit against that problem.
- Check: prose.

#### F32. One instance is fixed and the same problem stays elsewhere.

The passage the user pointed at is fixed; the same pattern remains in other passages, documents or outputs.
- Evidence: owner's records. Mixed polite endings fixed in the document the owner showed and left in others; an "A and B" category name ("infrastructure and purchase documents") left after the first round; tracking codes left after a cleanup; the same "A and B" grouping in CLI status output after it was removed from documents.
- Countermeasure: after a correction, search every text people read (documents, UI text, CLI output) for the same pattern and fix each occurrence, or list those left and why.
- Check: `awkit check writing` takes folders and searches them recursively, and the test suite runs it over every document in this repository. Status: enforced here for the mechanical patterns.

#### F33. Following the writing procedure is reported as quality.

The agent reports that it drafted in English, translated and ran review passes; the text still reads badly.
- Evidence: owner's records. After English drafts, translation and repeated review passes, the owner still found the Korean unnatural ("why does this repository's documentation still read unnaturally") and had to ask whether the agent had read the research a previous agent left.
- Countermeasure: judge the final text by reading it; report what it is, not the steps taken.
- Check: prose; `awkit check writing` covers listed patterns only.

#### F34. The user's own words become the document's text.

Conversational phrasing, the user's feelings or the conversation itself appear in a document written for someone else.
- Evidence: owner's records. A note for an administrative discussion repeated the owner's complaint as its argument ("don't be a parrot of what I say"); development documents used "the user" as a subject ("reflecting the mail server restriction the user reported") instead of stating the decision.
- Countermeasure: treat the user's words as material; write what the reader needs to understand or decide, and state decisions and reasons directly.
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

#### F37. The sources answer a different question.

The question was about what people experience; the sources collected are official pages and news. One account is reported as the norm.
- Evidence: owner's records. Asked what work at a kind of company is like, the agent collected job postings and news; the owner asked for what current and former employees had written, broadly rather than only complaints, and corrected the industry being searched. Hobby research needed the makers' own accounts, not only ratings.
- Countermeasure: choose the kind of source the question needs: official requirements from official sources, lived experience from first-hand accounts; distinguish the parent company from the local office and the advertised role from the one applied for; say what recurs across accounts and what is a single case.
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

### Explaining and troubleshooting

#### F38. Caveats instead of the mechanism.

Asked what a feature does, the agent answers with warnings and a recommendation and never says what changes, why the feature exists or when to use it.
- Evidence: owner's records. Asked about a color-space option, the agent explained that it does not always improve image quality; the owner replied that they wanted to know what changes, why the feature was made and when it is used.
- Countermeasure: answer a "what is this" question with the problem it solves, what changes inside, what the user can observe and when to use it; address a misunderstanding only when the user holds it.
- Check: prose.

#### F39. A workaround replaces the restoration the user asked for.

A behavior that worked before a change is to be restored; the agent proposes alternatives that need extra steps each time, repeats proposals that already failed and ignores the change history and per-condition results the user supplied.
- Evidence: owner's records. Remote access that had worked before a system reinstall was to be restored; the agent kept proposing a different procedure although the owner had reported what had and had not changed, the difference between shutdown and sleep, and the result per packet type. The fix was a network profile setting.
- Countermeasure: keep the wanted end state fixed; a solution that needs extra steps is reported as an alternative, not as the fix. Use when it last worked, what changed and the results per condition; update the hypothesis after each failed attempt instead of repeating it.
- Check: prose.

### Working with the user over time

#### F28. The wrong level of autonomy.

The agent does the work when the user wanted to learn or decide, or only advises when the user wanted it done.
- Evidence: owner's records, in both directions. Given a setup task, the agent described the steps for the owner to perform until the owner said to do it; asked to confirm a system state the agent could read itself, it asked the owner to check. Conversely, when the owner said they would do the first parts of an assignment themselves, the agent began drafting the answers ("I did not tell you to write the answers"); in another conversation the owner said the agent need not write code because they were doing it elsewhere and only wanted to talk through the task.
- Countermeasure: settle the form of help at the start and record it in the handoff.
- Check: prose.

#### F29. Context is lost between sessions.

The user explains the project again, or an interrupted external operation is repeated.
- Evidence: owner's records. Writing rules kept in one agent's memory did not reach another agent working on the same documents; the owner repeated the instructions and asked whether the second agent had read the first one's research.
- Countermeasure: standing rules in a repository file every agent reads (`AGENTS.md`); project profile; checkpoint with the next action; verify actual state before resuming.
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
| | Publish documents and AI summaries | 166 | F7, F14; the AI summary rules serve no entry yet |
| | Continue across sessions | 41 | F29 |
| protocol.md | A task record, States | 239 | F1 (session end is not done); the state table itself: none |
| | Roles and file ownership | 72 | F19 |
| | Check evidence | 96 | F1, F3 |
| | Reviews and decisions | 73 | F18 |
| | Resume after interruption | 65 | F29 |
| | Connect optional tools | 95 | none (tool semantics; belongs in the reference) |
| work-types.md | Common rules | 530 | F16, F22, F24, F28, F35, F36 |
| | Research | 182 | F23, F37 |
| | Writing | 167 | F16, F30 |
| | Data preparation and analysis | 225 | F22 |
| | Environment setup | 292 | F24, F25, F39 |
| | Operating an application | 114 | F24 |
| | Learning | 166 | F28, F38 |
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
| writing.md | Before writing | 159 | F15, F30, F34 |
| | Write plainly | 222 | F13, F15, F30 |
| | Preserve facts and judgments | 133 | F16, F30 |
| | Corrections | 67 | F31, F32 |
| | Rewriting and collaboration | 134 | F18, F21 |
| | Completion check | 83 | F1, F33 |
| korean-writing.md | all sections | 565 | F14, F31 |
| templates/project.md | Start here | 59 | F11, F29 |
| | Deliverables and completion | 195 | F3, F24 |
| | Delegation and models | 109 | F18, F19, F20 |
| | Other sections | 439 | none directly (fields); review which fields any entry needs |
| templates/task.md, review.md, decision.md, checkpoint.md | | 811 | F1, F17, F12, F29 |
| templates/roles/README.md | | 316 | F20 |

Sections marked "none" total roughly 1,700 words and are reviewed against the baseline workflow. Entries F4, F5 and F9 have no kit text at all, and F13, F14 and F30 to F34 have only kit text; they are the first candidates for checks (planned items above).
