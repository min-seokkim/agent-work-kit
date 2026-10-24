# Failure Catalogue

Agents fail in recognizable situations, in recognizable ways. This catalogue lists those failures and says what in the kit guards against each: a section of a guide, an `awkit` check or a hook. It is what the kit is for. It is not read every session; read an entry when a guard names it as its reason, and read the catalogue when designing a new guard. `workflow.md` and the situation guides say what to do; this catalogue says why.

Evidence comes in two kinds, never with names, dates, company names or personal context:

- Observed in awkit's development: cited by commit ID in the awkit repository.
- Owner's records: the awkit owner's own record of the corrections they made while having agents write documents (project and operations documents, reports for non-developers, UI text and CLI output, application documents) and while using agents for research, explanations, troubleshooting and purchase decisions. The records are not published; occurrences are described without identifying details.

Entries carried over from the kit's earlier versions were written from sessions whose records were not kept; they are marked "needs evidence" until an occurrence is recorded, and are removed after real-work measurement if none is.

## Rules for entries

An entry needs four things: the situation that triggers it (so the countermeasure can be loaded only then), the failure as it shows in the output, at least one recorded occurrence, and a check that would have caught that occurrence. Prefer checks a machine runs (a test, an `awkit` command, a hook) over instructions; use instructions only where no check is possible, and say so. Remove an entry, and the kit text that serves it, when it has not been seen in real work for a long time.

Record the failure that recurred, not the instruction that corrected it. A correction given for one document (one page, noun endings, no bullets, five revision passes) is that document's requirement and belongs in the project's profile. Before adding an entry, check whether an existing entry already describes the same failure, and add the occurrence there instead.

Mechanism status: `enforced` means a check runs without the agent choosing to; `tool` means `awkit` records or verifies it when the agent uses it; `prose` means only an instruction exists; `planned` names the check to build.

Each Check field starts with the kind of guard. `block` refuses a tool call before it runs. `verify` runs a check after a tool call, when the agent stops, or in tests and CI, and blocks once with the check's output. `inject` adds one line of guidance when a tool call has the situation's shape, once per session. `guidance` is a guide section the agent applies on its own. The hook rules (`block`, `verify` and `inject` in the agent's session) are the kit's default rules (`rules.toml` and `rules-session.toml`), run by `awkit hook`; each names the entries it guards, and every message it gives cites them.

## Entries

### Reporting work as done

#### F1. Done without a check on the delivered version.

The agent reports success, but the checks ran on another state of the files, or did not run. For documents, the text was edited but the rendered output (line breaks, tables, page fit) was never looked at.
- Evidence: owner's records. A documentation site was about to be committed with broken line breaks, which the owner found ("let's undo the commit and fix the line breaks"; "is there anything else to check before committing? I want to stop looking at this"). A table broke after IDs were replaced with long names.
- Countermeasure: check a frozen snapshot and report its run folder; for documents, inspect the rendered output before reporting.
- Check: Kind: verify. `awkit check done`, run by the `done-check` hook rule when the agent stops (Claude Code or Codex, from `awkit kit hooks`): files changed in the session need a passing `review check` of exactly their current state. Status: enforced where the hooks are installed, tool otherwise; rendered output is still prose. Test: `tests/test_checks.py` (changed after checking, untracked files, the hook blocking once per turn) and `tests/test_hooks.py`.

#### F2. The first failure disappears.

A check fails, a rerun passes, and the report mentions only the pass.
- Evidence: needs evidence.
- Countermeasure: keep every run; explain or list the first failure.
- Check: Kind: guidance. run folders are kept per run. Status: tool, prose for the reporting.

#### F3. Support claimed for environments that were not run.

Tests pass on one platform and the work is reported as working everywhere.
- Evidence: observed in awkit's development. Tests passed on Linux; the first Windows CI run on `dev` failed two tests (path ordering, 8.3 short names), fixed in `a5eec42`.
- Countermeasure: name the environments a claim covers; run all of them before claiming.
- Check: Kind: verify. CI matrix for this repository. Status: enforced here, prose for user projects; planned: profile field for target environments that the done-check reads.

### Describing behavior in documents and commit messages

#### F4. Documents describe behavior the code does not have.

The text states what the change was meant to do; the code does something else, and the test covers only the easy case.
- Evidence: observed in awkit's development. `f475f9e` documented that an example created inside an existing repository is committed there; the code skipped any repository that already had a commit, and the test used a repository without one. The example's first command then failed. Fixed in `b5d78ba`.
- Countermeasure: for each behavior stated in a document, a test that exercises exactly that case.
- Check: Kind: verify. `tests/test_examples.py` runs every command in the example READMEs as written, from an example created inside a repository with history; with the `f475f9e` behavior restored it fails. Status: enforced for the examples.

#### F5. Documents point at things that do not exist.

Install instructions, links or files that were never created.
- Evidence: observed in awkit's development. The README told users to download the 0.2.0 wheel from Releases; no tag or release had ever existed. The README's development command failed as written because of a relative `PYTHONPATH` (fixed in `6eb632c`).
- Countermeasure: run every documented command; check that referenced releases and files exist.
- Check: Kind: verify. relative links and the example READMEs' commands are tested, and CI runs `install.sh` and `install.ps1` from the checkout and then `awkit doctor`. Status: enforced for links, examples and the installers; the winget and Homebrew branches run only where Git or Python is missing, which CI runners never are.

#### F6. Numbers reported beyond what was measured.

A count from part of the data is stated as the whole, or a metric counts things it should not.
- Evidence: observed in awkit's development. The kit's size was given as about 10,800 words from a count that left out `kit/examples/` (about 800 more words). `awkit usage` counted notices and command output as user messages (13 instead of 9 in a real log; fixed in `6eb632c`).
- Countermeasure: state the scope of every number; check a metric against one real record before using it.
- Check: Kind: guidance. prose; for `usage`, a test built from a real log's record kinds.

### Choosing defaults and side effects

#### F7. A convenience changes state nobody asked to change.

A read or check command creates, commits or deletes something, or a setup command changes more of the project's own files than it adds.
- Evidence: observed in awkit's development. `review compare` in a folder without Git created a repository and committed every file, `.env` included (from `f475f9e`, fixed in `b5d78ba`). `kit hooks` rewrote a project's `.claude/settings.json` with two-space indentation and `\u` escapes for non-ASCII text, so every line changed to add one handler; with a commit-msg hook already present it left the identity check out while reporting the hook as kept; with husky it would have written into `.husky/_`, which husky regenerates (found while connecting the kit to existing setups, fixed in `006575b`). `kit init` committed what it wrote, and `kit init --copy` created a repository and set `core.autocrlf` where there was none, though the user had asked only for setup (pointed out by an external review; both now commit only with `--commit`).
- Countermeasure: read commands never write; write commands touch only what was named, add beside what the project has, and record what they add so it can be taken out.
- Check: Kind: verify. tests that read commands leave the folder unchanged, and that `kit init`, `kit skills`, `kit hooks` and `kit remove` change only the places in `WRITES`, leave memory and instruction files untouched and restore the project and home folders (`tests/test_connect.py`, `tests/test_layers.py`). Status: enforced for `awkit`.

#### F8. The user's unrelated work is bundled in.

A commit or snapshot includes changes the user had staged or made elsewhere.
- Evidence: found while fixing F7; not observed in use.
- Countermeasure: commit only named paths; skip when the index has staged changes.
- Check: Kind: verify. enforced in `kit init --commit` and `kit example`; snapshots include only named files.

### Committing and publishing

#### F9. The agent's own identity replaces the repository's convention.

Commits are authored as the agent, or carry trailers the owner did not ask for.
- Evidence: observed in awkit's development. Commits on `dev` were authored as "Claude" with `Co-Authored-By` lines while the owner's commits used their own identity; the history had to be rewritten and force-pushed. Later, a cloud session's harness asked for `Co-Authored-By` and `Claude-Session` lines, the fresh clone had no identity in `.git/config` although `AGENTS.md` said it had, and `awkit doctor` reported the global `Claude <noreply@anthropic.com>` as fine (the doctor check was fixed in `23649e0`).
- Countermeasure: read the existing history's author and message conventions before the first commit. In this repository the convention is stated in `AGENTS.md`, which coding agents read at the start of a session.
- Check: Kind: block. The `commit-identity` hook rule runs `awkit check commit --hook` on every `git commit` command before it runs, comparing the author and trailer keys with the last 50 commits; `awkit kit hooks --git` installs the same check as a `commit-msg` hook, and CI runs it on every pushed commit of this repository. Status: enforced here. Test: `tests/test_checks.py` replays the agent identity with `Co-Authored-By` and `Claude-Session` lines, `tests/test_hooks.py` the same as a Bash command.

#### F10. Irreversible publication prepared before it is justified.

Version bumps, release workflows or uploads set up while the interface is still changing.
- Evidence: observed in awkit's development. A PyPI release was prepared (`cb24596`) before the kit split and real-use measurement; the owner held it (`5a2ad25`).
- Countermeasure: written release conditions; no tag until they are met.
- Check: Kind: guidance. prose (release conditions in awkit's development record).

### Proposing and inferring

#### F11. A guess is presented as a finding.

An inference from file names or conventions is reported as how the project works; a question from the user is recorded as a confirmation.
- Evidence: observed in awkit's development. `kit scan` suggested pytest for any `tests` folder; this repository uses unittest (fixed in `6eb632c`). `kit scan` reported `"present": false` for the kit in this repository, which uses it through skills pointing at `kit/`, because it looked only for a folder named `agent-work-kit` (fixed in `006575b`). `awkit doctor` reported "kit: connected by awkit 0.3.0" in this repository because `.awkit/installed.json` existed, a record the session hook's `kit hooks --git` had written seconds earlier listing only the commit-msg hook; it now reads the `[kit]` table of `checks.toml` and the skills instead (fixed in the three-layer change). Owner's records: a component that was already installed was installed again; files were sorted by their names without opening them; the owner's question whether a tool was allowed was recorded as the owner confirming that it was ("I was asking whether it is okay").
- Countermeasure: mark inferences; run a suggested command once before relying on it; check the current state before installing, sorting or reviewing; treat a question as a question.
- Further evidence: the connection diagnostic trial at `4a7cb6a` reproduced doctor printing ready for empty or invalid check configuration, including after a repeated init that no longer warned about missing commands. Its validation now reuses review's configuration rules without claiming execution.
- Check: Kind: guidance. the connect procedure runs the drafted checks once. Status: prose plus tool.

#### F12. Scope grows before anything is measured.

Features and documents are added because they seem useful, before real use shows a need.
- Evidence: observed in awkit's development. The release runner was widened to every kind of delivery and documentation grew to several thousand words for readers who did not read it (`8cf8e72`, restructured in `8f93b7b`). Owner's records: a server for a temporary project was specified with a graphics card, more memory than the load needed and a layout for a larger organization.
- Countermeasure: a feature needs a failure entry here and a check; measure on real tasks before widening. Size a design to the purpose, duration, load and the person who will run it.
- Check: Kind: guidance. prose; the kit word limit tests bound each file by when it is read.

#### F35. The user's guess becomes the requirement.

The user, new to a field, proposes an approach; the agent builds on it and adjusts the plan to each new idea instead of evaluating it.
- Evidence: owner's records. A server layout kept changing to follow the owner's ideas until the owner said to ignore what they had said and think it through, asked what the standard layout was, and said it was their first time and the agent should bring in industry practice.
- Countermeasure: read each statement from the user as a hypothesis, a constraint or a decision. For a hypothesis, give the standard approach, the strengths and weaknesses, and the alternatives, and say when the conclusion changes and why. Disagreement names the premise or step that is wrong, not the user.
- Check: Kind: guidance. prose.

#### F36. The answer ends at "unknown".

Where the facts do not settle a question, the agent stops at the uncertainty instead of saying what can be compared, which explanation fits best and what would change the judgment.
- Evidence: owner's records. After an explanation of the market range for a role, the owner asked where their own band was. An analysis of someone's behavior concluded that it could not be known, which the owner found useless.
- Countermeasure: separate what is established, the candidate explanations, the assumptions each needs and what is unknown; give a provisional judgment with its assumptions and the observation that would change it; put no numbers or probabilities on it that the material does not support.
- Check: Kind: guidance. prose.

### Writing for people

#### F13. AI writing patterns in English.

Contrasts against claims nobody made, lead-ins, closing lines that repeat the paragraph, slogans, bold labels, dashes, sales words, promotional headlines and repeated labels.
- Evidence: observed in awkit's development. The first rewrite of the README (owner's feedback, corrected in `8f93b7b`). Owner's records: em dashes in English and Korean application text; the largest line on a documentation index page was a slogan ("this is not a brochure"); every list entry carried a tag repeating its title; a README listed what the project does not do; consulting and promotional tone in reports.
- Countermeasure: the pattern list in `writing.md`; awkit's own repository applies it through its `AGENTS.md`.
- Check: Kind: verify. `awkit check writing`: em dashes fail; lead-ins, contrasts, sales words warn. The test suite runs it over this repository's documents. Status: enforced here for errors; the rest of the list is judgment.

#### F14. Korean that reads like a translation, including from an agent that wrote the rules.

Translationese, mixed sentence endings, noun chains; the agent's own Korean guide not applied to its own output.
- Evidence: observed in awkit's development. The Korean README and replies before the owner pointed it out. Owner's records: Korean still unnatural after an English draft and translation; `-세요` turning into `-시오` within one guide, then the same mix left in other documents; words Korean readers do not use in that sense (`정제`, `권위 순서`, `경계`, `흐름`); middle dots joining words; italics in Korean reports. Observed in awkit's development: the planning session for the hook runner had the writing skill and the `AGENTS.md` rule that replies follow the guide, wrote a long Korean instruction for another session in the chat without calling the skill, and fixed it only after the owner pointed it out twice; no tool call was made, so no hook ran (guarded from `5aea860` by `writing-reply`). With awkit installed by pipx, `{kit}` expanded to an 85-character path, and the kit's `korean-writing`, `research` and `delegation` rules passed the 200-character message limit and were dropped as broken (fixed in `5aea860`).
- Countermeasure: `korean-writing.md` with `writing.md`, applied to every Korean text, including the agent's replies.
- Check: Kind: verify, inject. `awkit check writing`: middle dots joining Korean words and `-세요` mixed with `-시오` fail; Korean stock phrases warn. Natural Korean remains a reader's judgment. The `writing-request` rule adds the guide's line on a request for a document, and `writing-reply` blocks once when the final reply is a long Korean document from a session that never read the guide. Test: `tests/test_hook_rules.py`.

#### F15. Writing for the wrong reader.

Long human-oriented documents for a tool whose user is an agent, or agent details in what people read. A document for one reader is made by rewording one written for another.
- Evidence: observed in awkit's development. Five human-oriented documents under `docs/` that neither the owner nor agents needed in that form (restructured in `8f93b7b`). Owner's records: tracking codes (`AB-001`, `S1` to `U8`) throughout documents people read; commit IDs and evidence references in a report for non-developers; the abbreviation ADR in an administrative form; a status report for stakeholders built from developer documents with the wording changed ("LLMs just copy the development documents"); a resume that read like a technical report; one developer's Windows and Edge setup written as everyone's.
- Countermeasure: decide the reader, what they must understand or decide, and the kind of document first; write from that, using other documents only as sources of facts. Keep tracking codes where the agent needs them and out of the text people read.
- Check: Kind: guidance. prose.

#### F30. Facts, attribution or certainty change while writing.

A rewrite drops a number, condition or exception, turns a possibility into a certainty or a permission into an obligation, or claims something was verified when only the wording changed. Shortening removes facts instead of repetition. A plan reads as what happened, or one person's or project's work is credited to another.
- Evidence: owner's records. A purchase plan read as the purchase actually made, and had to be rewritten to say what was planned and what was bought. Asked to write a status document more compactly, the agent cut content; the owner corrected that it should say the same in fewer words, over more than one page if needed. In resumes: results from two projects merged, a problem someone else found written as the owner's discovery, integration work written as ownership of the system, a technology used once listed as a skill.
- Further evidence: a synthetic paired writing trial exposed a shared preservation brief turning withdrawal of a proposal into a new plan; both drafts followed that unsupported premise. Source comparison exposed the error, and bounded revisions removed it.
- Countermeasure: list what must be preserved (facts, numbers, conditions, who did what, plan or done), validate source-derived claims against relevant available originals, and compare the draft with both; shorten by removing repetition and wordy phrasing.
- Check: Kind: guidance. prose.

#### F31. The form of a correction is fixed, not its reason.

After a correction, the agent changes exactly what was named and repeats the underlying problem in another form.
- Evidence: owner's records. Told not to name categories "A and B", the agent renamed them all to four-character names that still did not say what each held. Told that tracking codes were hard to read, it put long names in the ID column, which broke the table.
- Countermeasure: state the reader's problem and the correction's applicable scope; check the edit and next related result against that reason.
- Check: Kind: guidance. prose.

#### F32. One instance is fixed and the same problem stays elsewhere or returns later.

The passage the user pointed at is fixed; the same pattern remains elsewhere or recurs in later related outputs.
- Evidence: owner's records. Mixed polite endings fixed in the document the owner showed and left in others; an "A and B" category name ("infrastructure and purchase documents") left after the first round; tracking codes left after a cleanup; the same "A and B" grouping in CLI status output after it was removed from documents. Later records show renewed requests about the same broad style problem despite available project notes and writing guidance. They do not establish whether guidance was read or whether recording a preference would have prevented recurrence. The particular inspected research additions and substantive question added requirements; a new action can also address an earlier unmet requirement.
- Countermeasure: search existing outputs for the pattern and fix each occurrence, or list those left and why; carry the accepted reason and scope into later related outputs and delegated briefs, using existing requirements or task records when persistence is needed.
- Check: Kind: verify. `awkit check writing` searches folders recursively; repository tests cover its listed mechanical patterns. Comparing a later result with the correction's reason is agent review, not proof of owner acceptance. Status: mechanical patterns enforced here; future application remains guidance and review.

#### F33. Following the writing procedure is reported as quality.

The agent reports that it drafted in English, translated and ran review passes; the text still reads badly.
- Evidence: owner's records. After English drafts, translation and repeated review passes, the owner still found the Korean unnatural ("why does this repository's documentation still read unnaturally") and had to ask whether the agent had read the research a previous agent left.
- Countermeasure: judge the final text by reading it; report what it is, not the steps taken.
- Check: Kind: guidance. prose; `awkit check writing` covers listed patterns only.

#### F34. The user's own words become the document's text.

Conversational phrasing, the user's feelings or the conversation itself appear in a document written for someone else.
- Evidence: owner's records. A note for an administrative discussion repeated the owner's complaint as its argument ("don't be a parrot of what I say"); development documents used "the user" as a subject ("reflecting the mail server restriction the user reported") instead of stating the decision.
- Countermeasure: treat the user's words as material; write what the reader needs to understand or decide, and state decisions and reasons directly.
- Check: Kind: guidance. prose.

### Revising approved work

#### F16. Approved work regresses during a later change.

A revision passes its checks but loses what the user had accepted.
- Evidence: needs evidence (carried over from `work-types.md`). awkit's own loop (accept and compare) guards it, so whether it occurs in real work is a main question of next work 5.
- Countermeasure: keep the accepted version; compare every revision with it.
- Check: Kind: guidance. `awkit review accept` and `compare`. Status: tool.

### Review

#### F17. The reviewed version is not the shipped version.

The author keeps editing during review, or the reviewer has seen the author's reasoning.
- Evidence: needs evidence. Like F16 it is guarded by awkit's own loop and measured in next work 5.
- Countermeasure: review a snapshot ID; use a fresh session that did not see the implementation.
- Check: Kind: guidance. `awkit review snapshot`, `channel --snap`. Status: tool.

#### F18. Review never ends.

Each fix produces new findings and more premium calls.
- Evidence: needs evidence (carried over from `delegation.md`).
- Countermeasure: one premium call by default, a stated reason for a second, a cap of three, then a user decision.
- Check: Kind: guidance. prose; `awkit usage` shows the calls afterwards.

### Delegation

#### F19. Parallel subagents make conflicting decisions.

Interfaces, names or error handling diverge because each subagent decided alone.
- Evidence: needs evidence.
- Countermeasure: settle shared decisions before parallel work and give every handoff the same wording.
- Check: Kind: inject. prose.

#### F20. A subagent's self-report is trusted.

The model, permissions or work claimed by a subagent are not what happened.
- Evidence: needs evidence.
- Countermeasure: read the actual model and permissions from logs.
- Check: Kind: guidance. `awkit usage`. Status: tool for models, prose for permissions.

#### F21. Handoffs carry too much or too little.

The whole conversation or repository is passed, or a decision the subagent needs is missing.
- Evidence: needs evidence (size limits come from 55 handoffs in one project).
- Countermeasure: four-part handoff with size limits; `NEEDS_CONTEXT` status.
- Check: Kind: inject. prose.

### Data and analysis

#### F22. Observations, assumptions and interpretation are mixed.

A computed value depends on an unstated or wrong assumption, or an interpretation is presented as a result.
- Evidence: needs evidence (the analysis example reproduces it).
- Countermeasure: assumptions in a file checked against the data; a report with separate parts; interpretation by a person.
- Check: Kind: guidance. the analysis example's check script shows the pattern. Status: prose plus example.

#### F23. Contradicting sources are averaged.

Research merges disagreeing sources into one claim.
- Evidence: needs evidence.
- Countermeasure: show contradictions and gaps; cite what was read.
- Check: Kind: inject. prose.

#### F37. The sources answer a different question.

The question was about what people experience; the sources collected are official pages and news. One account is reported as the norm.
- Evidence: owner's records. Asked what work at a kind of company is like, the agent collected job postings and news; the owner asked for what current and former employees had written, broadly rather than only complaints, and corrected the industry being searched. Hobby research needed the makers' own accounts, not only ratings.
- Countermeasure: choose the kind of source the question needs: official requirements from official sources, lived experience from first-hand accounts; distinguish the parent company from the local office and the advertised role from the one applied for; say what recurs across accounts and what is a single case.
- Check: Kind: inject. prose.

### Operating environments and applications

#### F24. A tool's success is taken as the result.

A command returned 0, so the message is assumed delivered, the file transferred, the setting applied or the release live.
- Evidence: needs evidence (the release runner was built for the deploy case). A defect of its guard, not an occurrence: the `delivery` rule's line was added when a heredoc that wrote a document mentioning `git push` went to `cat`, because the shell condition read the heredoc body as commands (fixed in `5aea860`).
- Countermeasure: observe the end state where the recipient sees it.
- Check: Kind: inject. `awkit pipeline` verifies the running release. Status: tool for releases, prose otherwise.

#### F25. Instructions for another version are applied.

Setup steps from documentation for a different edition, OS or account type.
- Evidence: observed in awkit's development. Two cloud sessions in a row started on a checkout of `dev` older than a rewrite of its history (the second at `ce591c1`, while `origin/dev` was at `cc71b90`): the checkout had no `AGENTS.md`, `checks.toml` or session hook, so awkit was not installed and the first `awkit doctor` failed with command not found. A `git fetch` showed the forced update; the session reset to `origin/dev` and ran the hook by hand. No check caught it: the guard would have been the session hook, which the old checkout did not have.
- Countermeasure: confirm version, OS and account type before following found instructions.
- Further evidence: the connection diagnostic trial records installed code at `f85a1ec` and checkout code at `4a7cb6a` with the same 0.3.0 version but different file contents. Runtime diagnostics report the loaded code's origin; provenance metadata alone does not prove file integrity or freshness.
- Check: Kind: guidance. prose.

#### F26. Checks interfere through shared resources.

Parallel or repeated checks share a database, port or device and fail or pass for the wrong reason.
- Evidence: needs evidence.
- Countermeasure: allocate resources per run ID; run single-device checks one at a time.
- Check: Kind: guidance. `{run_id}` placeholders. Status: prose plus tool.

#### F27. A one-off request becomes a standing automation.

"Just this once" ends as a registered schedule, or a test run is reported as the real run.
- Evidence: needs evidence.
- Countermeasure: confirm once or recurring; record the first real run and the removal separately.
- Check: Kind: guidance. prose.

### Explaining and troubleshooting

#### F38. Caveats instead of the mechanism.

Asked what a feature does, the agent answers with warnings and a recommendation and never says what changes, why the feature exists or when to use it.
- Evidence: owner's records. Asked about a color-space option, the agent explained that it does not always improve image quality; the owner replied that they wanted to know what changes, why the feature was made and when it is used.
- Countermeasure: answer a "what is this" question with the problem it solves, what changes inside, what the user can observe and when to use it; address a misunderstanding only when the user holds it.
- Check: Kind: guidance. prose.

#### F39. A workaround replaces the restoration the user asked for.

A behavior that worked before a change is to be restored; the agent proposes alternatives that need extra steps each time, repeats proposals that already failed and ignores the change history and per-condition results the user supplied.
- Evidence: owner's records. Remote access that had worked before a system reinstall was to be restored; the agent kept proposing a different procedure although the owner had reported what had and had not changed, the difference between shutdown and sleep, and the result per packet type. The fix was a network profile setting.
- Countermeasure: keep the wanted end state fixed; a solution that needs extra steps is reported as an alternative, not as the fix. Use when it last worked, what changed and the results per condition; update the hypothesis after each failed attempt instead of repeating it.
- Check: Kind: guidance. prose.

### Working with the user over time

#### F28. The wrong level of autonomy.

The agent does the work when the user wanted to learn or decide, or only advises when the user wanted it done.
- Evidence: owner's records, in both directions. Given a setup task, the agent described the steps for the owner to perform until the owner said to do it; asked to confirm a system state the agent could read itself, it asked the owner to check. Conversely, when the owner said they would do the first parts of an assignment themselves, the agent began drafting the answers ("I did not tell you to write the answers"); in another conversation the owner said the agent need not write code because they were doing it elsewhere and only wanted to talk through the task.
- Countermeasure: settle the form of help at the start and record it in the handoff.
- Check: Kind: guidance. prose.

#### F29. Context is lost between sessions.

The user explains the project again, or an interrupted external operation is repeated.
- Evidence: owner's records. Writing rules kept in one agent's memory did not reach another agent working on the same documents; the owner repeated the instructions and asked whether the second agent had read the first one's research. Observed in awkit's development: `kit init` copied the kit and `kit skills` pointed skills at the situation guides, but nothing a session reads at its start pointed at `workflow.md` or the profile, so the baseline reached an agent only where someone had written that into the project's instructions by hand, as this repository's `AGENTS.md` did (`6482bc7`; fixed in `006575b`).
- Countermeasure: standing rules in a repository file every agent reads (`AGENTS.md`); the way of working installed once per computer, as skills in the user folders every session reads; what done means in the project's `checks.toml`; state kept where the project already keeps it; checkpoint with the next action; verify actual state before resuming.
- Check: Kind: guidance. prose plus templates; `kit skills` puts the workflow and guides in the user folders and `kit guide` prints them for agents without skills, `awkit doctor` warns when no skills or no hook reaches sessions, and `kit scan` lists where the project keeps state.

## What guards each entry

Generated from the guards' own declarations: each guide section ends with a "Prevents:" line, each `awkit` command declares its entries in its code, and each rule in `rules.toml` names them in `prevents`. The test suite fails when this table differs from a fresh one; regenerate it with `python scripts/guard_map.py --write` in the awkit repository.

<!-- guard table: generated by scripts/guard_map.py -->
| Entry | Guide sections | Checks and commands | Hook rules |
|---|---|---|---|
| F1 Done without a check on the delivered version | workflow.md Check a frozen version; workflow.md Report; protocol.md A task record; protocol.md States; writing.md Completion check | `awkit check done`, `awkit kit hooks`, `awkit hook`, `awkit ui` | `done-check (verify)` |
| F2 The first failure disappears | workflow.md Check a frozen version; checking.md Interpreting results; review-session.md 3. Work through a unit; review-session.md 4. Review criteria | `awkit review check` | none |
| F3 Support claimed for environments that were not run | workflow.md Check a frozen version; checking.md The checked version | none | none |
| F4 Documents describe behavior the code does not have | none | none | none |
| F5 Documents point at things that do not exist | none | `awkit publish` | none |
| F6 Numbers reported beyond what was measured | workflow.md Report; delegation.md 1. Objective | `awkit usage` | none |
| F7 A convenience changes state nobody asked to change | connect.md; delivery.md Confirm it in its intended context | `awkit kit hooks`, `awkit kit init`, `awkit kit remove` | none |
| F8 The user's unrelated work is bundled in | workflow.md Define the task | `awkit kit init --commit and kit example (commit only what they wrote)` | none |
| F9 The agent's own identity replaces the repository's convention | connect.md | `awkit check commit`, `awkit kit hooks`, `awkit kit init --commit and kit example (commit only what they wrote)`, `awkit doctor`, `awkit hook` | `commit-identity (block)` |
| F10 Irreversible publication prepared before it is justified | none | none | none |
| F11 A guess is presented as a finding | workflow.md Do the work; connect.md; checking.md The checked version; writing.md Before writing | `awkit doctor`, `awkit kit scan`, `awkit hook` | none |
| F12 Scope grows before anything is measured | connect.md | `awkit kit scan`, `awkit kit init`, `awkit kit skills` | none |
| F13 AI writing patterns in English | workflow.md Report; writing.md Write plainly | `awkit check writing`, `awkit check writing-compare`, `awkit hook` | `writing-check (verify)` |
| F14 Korean that reads like a translation, including from an agent that wrote the rules | korean-writing.md Writing process; korean-writing.md Tone and terminology; korean-writing.md Revise sentences | `awkit check writing`, `awkit check writing-compare`, `awkit hook`, `awkit hook reply` | `writing-check (verify)`, `korean-writing (inject)`, `writing-request (inject)`, `writing-reply (verify)` |
| F15 Writing for the wrong reader | writing.md Before writing; writing.md Write plainly | none | none |
| F16 Approved work regresses during a later change | work-types.md Common rules; work-types.md Writing; writing.md Preserve facts and judgments | `awkit review accept`, `awkit review compare` | none |
| F17 The reviewed version is not the shipped version | workflow.md Check a frozen version; checking.md The checked version; review-session.md 1. Purpose and cost; review-session.md 2. Session setup; review-session.md 3. Work through a unit; review-session.md 5. Commands; review-session.md 8. Starting prompts | `awkit review snapshot`, `awkit review check`, `awkit channel` | none |
| F18 Review never ends | protocol.md Reviews and decisions; delegation.md 3. Risk and premium calls; delegation.md 6. Failures and retries; review-session.md 3. Work through a unit; review-session.md 4. Review criteria; review-session.md 6. Waiting; writing.md Rewriting and collaboration | `awkit channel` | none |
| F19 Parallel subagents make conflicting decisions | workflow.md Define the task; protocol.md Roles and file ownership; delegation.md 2. When to delegate; delegation.md 4. Roles and execution paths | none | `delegation (inject)` |
| F20 A subagent's self-report is trusted | delegation.md 4. Roles and execution paths; delegation.md 7. Model tiers; delegation.md 8. Measurement; review-session.md 7. Records and evaluation | `awkit usage` | none |
| F21 Handoffs carry too much or too little | delegation.md 2. When to delegate; delegation.md 5. Handoffs and results; writing.md Rewriting and collaboration | none | `delegation (inject)` |
| F22 Observations, assumptions and interpretation are mixed | work-types.md Common rules; work-types.md Data preparation and analysis | none | none |
| F23 Contradicting sources are averaged | work-types.md Research | none | `research (inject)` |
| F24 A tool's success is taken as the result | workflow.md Check a frozen version; delivery.md Identify what is delivered; delivery.md Confirm it in its intended context; delivery.md Failure and recovery; work-types.md Environment setup; work-types.md Operating an application | `awkit pipeline`, `awkit publish` | `delivery (inject)` |
| F25 Instructions for another version are applied | work-types.md Environment setup | `awkit doctor`, `awkit hook kit-version` | `kit-version (inject)` |
| F26 Checks interfere through shared resources | checking.md Shared resources and processes | none | none |
| F27 A one-off request becomes a standing automation | work-types.md Automation | none | none |
| F28 The wrong level of autonomy | workflow.md Define the task; work-types.md Learning | none | none |
| F29 Context is lost between sessions | workflow.md Continue across sessions; connect.md; protocol.md A task record; protocol.md Resume after interruption; writing.md Before writing | `awkit doctor`, `awkit kit scan`, `awkit kit init`, `awkit kit skills`, `awkit kit guide`, `awkit channel status`, `awkit hook` | none |
| F30 Facts, attribution or certainty change while writing | work-types.md Writing; writing.md Before writing; writing.md Write plainly; writing.md Preserve facts and judgments | none | none |
| F31 The form of a correction is fixed, not its reason | writing.md Corrections; writing.md Rewriting and collaboration; korean-writing.md Revise sentences | none | none |
| F32 One instance is fixed and the same problem stays elsewhere or returns later | writing.md Corrections; writing.md Rewriting and collaboration | `awkit check writing` | `writing-check (verify)` |
| F33 Following the writing procedure is reported as quality | writing.md Completion check; korean-writing.md Writing process | none | none |
| F34 The user's own words become the document's text | writing.md Before writing | none | none |
| F35 The user's guess becomes the requirement | workflow.md Define the task | none | none |
| F36 The answer ends at "unknown" | workflow.md Report | none | none |
| F37 The sources answer a different question | work-types.md Research | none | `research (inject)` |
| F38 Caveats instead of the mechanism | work-types.md Learning | none | none |
| F39 A workaround replaces the restoration the user asked for | work-types.md Environment setup | none | none |

Entries with no guard yet: F4, F10.
<!-- end of guard table -->
