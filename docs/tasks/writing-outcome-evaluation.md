# Writing outcomes and repeated instructions

Status: the initial retrospective is recorded and correction-carry-forward guidance shipped in `b273d95`. Planning owns this record, evidence interpretation and product decisions. The implementation session owns assigned technical work, checks and delivery. The owner prioritizes better writing and fewer repeated instructions over completion counts. This task follows the [document intent trial](document-intent-trial.md), whose synthetic results do not establish an effect in actual writing.

## Scope and method

The owner authorized reading the selected application session's records and retained drafts to assess awkit. Its writing session retains editorial ownership. Read originals in place; keep private prose and raw conversation out of this repository and collaboration messages. Local metadata identifies the selected log, inspected line ranges, source files and hashes. It does not turn a partial recovered conversation into a full original.

Compare a retained earlier draft with its revision, then trace the reason for the change through visible owner feedback, agent review and tool results. Judge whether the revision preserves the author's question, clarifies the argument, reads naturally and reduces work needed before use. Distinguish added requirements from reminders to meet an existing one. A request for a different corrective action can address the same unresolved problem. Repeated wording alone cannot establish an identical defect or measure the owner's effort.

The inspected sample contains two draft pairs chosen because earlier versions and revision evidence were available. It is not a random sample or a verdict on the whole collection. Planning knows the version order and has read the feedback, so the reading is not blinded. No new independent fact-checking, target-editor inspection or human acceptance is implied.

## Preliminary observations

| Observation | Evidence and judgment | Attribution limit |
|---|---|---|
| An early revision restores a specific personal problem | Reading the retained first and third versions shows a more concrete opening, a clearer central question and a self-counterargument that reconnects the conclusion to the opening. Qualifications remain available. | The visible owner corrections and the writer's technical account identify owner feedback and rereading original material as the triggers. Existing guidance already required preservation. A better revision is not evidence that awkit caused the improvement. |
| Another revision makes a local improvement | A standalone essay retained in the consolidated edition changes two opening paragraphs and a cross-reference. The question becomes more direct; most of the body and its research limits remain unchanged. | This supports a local editorial judgment, not a claim that the entire essay or collection was transformed. An intermediate wording criticized by the AI reviewer was not located as a retained candidate in this comparison. |
| Similar style requirements recur in later work | The owner asks for less generic prose and preservation of voice, later asks for more natural blog writing, and raises the broad style concern again after additional drafting and consolidation. Frozen project instructions already contain a personal-voice requirement. | This demonstrates continued owner intervention at the requirement-class level. It does not show whether each delegated context received the requirement, that every occurrence was the same defect, or that a particular language procedure caused it. |
| Agent editorial review produces specific proposed repairs | The retained review and response identify pacing, missing transitions, changed modality, repeated endings and an artificial conversational turn. The response records targeted integration. | These are agent review records. They are not independent factual verification or proof that the owner accepted the resulting prose. Only the two sampled pairs received the retrospective comparison above. |
| Version and check records make the process inspectable | Preserved drafts, immutable snapshots and retained failed/passing runs let planning distinguish content revision from a mechanical pass and locate earlier requirements. | Inspectability is an observed capability. Saved owner time, lower cost and better final writing attributable to that capability remain unmeasured. |

The inspected requests for an additional opening or ending and a new substantive question add scope. Broader research needs interpretation against the unresolved requirement: a later request to read more platform examples, followed by the writer's acknowledgment that its earlier sample was insufficient, can continue the existing style correction. Preparing publication also changes output requirements. Do not count every platform-format request as forgotten guidance or classify every new action as new scope.

## Later correction application

Passive follow-up found another request to read platform examples and a separate correction about numeric display. The former continues the broad style concern, but does not establish that every intervening draft had the same defect. The numeric request is the first explicit correction of that display issue in the inspected sequence; it is not evidence of forgetting an earlier instruction.

The writer interpreted the numeric correction as readability and unit formatting, then changed its chart formatter. Planning inspected the relevant code and one existing rendered chart in place. The chart uses grouped thousands with its stated unit and a rounding note; the formatter converts the magnitude instead of blindly replacing a decimal point with a comma. This supports application of that correction to the inspected chart. It does not establish consistency across the article, all charts or the publication platform, and no model calculation was independently rerun. Source identities and message references are retained locally without private prose or chart copies.

This is an immediate correction example, not yet evidence of persistence into a later applicable output. The follow-up does not establish that the active writer reread the newly installed guide or that awkit caused the correction. Keep subsequent-output checks and actual owner acceptance separate from this observation.

## Carry corrections forward

Avoiding the need to repeat instructions is an explicit product outcome. A final text can improve while this outcome remains unmet. Evaluate the chain from the first correction, through its interpretation and applicable scope, to the next related draft and any delegated brief. Then inspect the later output. Saving a preference or reporting that a guide was read is insufficient.

Existing F31 covers correcting the underlying problem; F32 covers other existing occurrences; F33 separates procedure from quality. `M-067` assigns a small revision in the existing writing guide to carry an accepted correction into later related outputs and handoffs. Use existing project requirements or task records when persistence is needed. General lessons belong in kit guidance; a project's voice preference and a one-document instruction keep their scope. No new correction registry, semantic score or automatic approval is assigned.

Acceptance requires an actionable rule that closes this temporal gap, preserves current user precedence and existing review boundaries, and remains within the guide's word limit. Existing focused checks can verify packaging, links and mechanical writing. They cannot establish fewer repeated requests. The next evaluation should inspect a later applicable output without supplying the same correction again, identify any recurrence, and record the owner's actual response when available. Do not ask the owner to repeat a requirement merely to produce an evaluation result.

## Reported recurrence after a handoff

M-023 traced one applicable preservation correction from a retained handoff into another writing project's existing plan and revision records. R-020 reports this explicit sequence: recorded receipt and intended incorporation, later owner intervention about preserving the source questions' connections, then a corrective plan revision. The handoff hash matches the recorded receipt; this identifies the source without independently proving that every worker read or applied it.

The records support a reported recurrence at the requirement-category level after receipt. They do not establish an identical textual defect, successful later prose or persistence without another reminder. The later request also adds material, so it cannot all be counted as repeated correction. The inspected English working plan is supporting context; newer task records, rather than that file or modification times alone, establish the subsequent work sequence.

This observation reads agent-authored records, not the underlying owner messages or manuscript/source pairs. No editorial judgment or new writing instruction was given. The cause remains unresolved: context transfer, application and plan quality cannot be separated from these records. Existing carry-forward guidance remains applicable; no new registry, semantic check or approval gate is selected. Sanitized source identities and scope are retained under `.awkit/handoffs/product-research/executor/correction-carry-forward/`.

## Further visible user inputs

The selected session's later visible inputs include an author-disclosure boundary, a request to restore a passage's intended meaning, another full revision and an explicitly requested independent agent review. The disclosure request refers to an earlier agreement, but a limited search of earlier visible inputs did not locate it. Its prior scope remains unavailable; this is not proof of either a first-time requirement or repeated noncompliance. The bounded observation also does not establish that identifying details were publicly exposed.

These requests establish further owner intervention, without establishing the quality of the resulting revisions or their cause. The later output and delegation evidence were not inspected in this observation. An additional review request does not by itself prove that an earlier required review was omitted. Keep the applicable requirement and actual changed output as the comparison unit instead of counting every request as recurrence.

A later user question asks whether messages from other sessions were read. The writer's answer limits its claim to messages received in that chat and states that linked materials were not all read in full. This supports distinguishing message reading from source inspection; it does not establish that every registered channel was checked or that an obligation was missed. The separate technical feedback channel had no new or unanswered request at this inspection.

Metadata-only evidence is `later-input-observation.json` under the existing local evaluation folder. Private prose and identity details remain in the application session. Future preservation evaluation should include author-approved disclosure scope alongside meaning and style, using existing project requirements. These observations assign no editorial intervention, privacy scanner or new record system.

## Guidance candidate and review

`M-067` returned three-file candidate `a540d42` in `R-037`. Its existing five kit, guard, link, word-limit and skill-payload checks and writing checks passed in `.awkit/reviews/review-l_jh4_6x`. Planning found one overgeneralization: the new rule classified new research or a new question as additional scope. A different requested action can address the same unmet requirement. `M-068` requested that distinction, and `R-038` returned candidate `c0d55c2` with only the two affected guide/catalogue sentences changed. The original candidate and passing mechanical run remain evidence of what those checks missed.

The refined three-file candidate passed the same focused checks in `.awkit/reviews/review-45tr11b6`. It carries correction reasons and scope into later related outputs and delegated briefs, uses existing project records where persistence is needed, and keeps reusable lessons separate from project or document preferences. The guard map was regenerated. No command, hook, registry, test suite or language-method default changed. Planning read the diff, refinement and retained results, inspected the final changed passages rendered in Edge at 1200 px, and accepted the candidate in `M-069`. The delivery below records cumulative repository verification separately from this focused pass.

## Delivery

Ten-file snapshot `96541f3` passed Ruff and 352 tests with seven skips in `.awkit/reviews/review-st2gakg9`. The whole-tree done check matched; commit `b273d95` has the same tree. All seventeen Windows/Linux jobs passed in [CI run 40064211362](https://github.com/min-seokkim/agent-work-kit/actions/runs/40064211362). The exact-commit platform installation matched 26 source files, 29 kit files and sixteen user-skill payloads with recorded line-ending normalization. Receipts are under `.awkit/handoffs/correction-carry-forward-delivery/`. Updating installed files does not establish that an active application session has reread them.

## Remaining evidence

The two comparisons support limited improvements in prose and argument. Direct awkit contribution to those improvements remains uncertain. The repeated broad style corrections show a practical shortfall worth addressing, even though the mechanism is not yet isolated. The current evidence does not justify a new memory service, a universal essay style or a change to the Korean drafting default.

Local metadata belongs under `.awkit/handoffs/writing-outcome-evaluation/`. No manuscript copies are retained there. Further reading should locate whether the applicable correction reached later work and distinguish failed application from unavailable context. Report unresolved access or opaque tool payloads as unknown; do not infer missing instructions from them. Any later causal comparison must disclose differences in sources, model, context and owner involvement.

## Candidates from upstream comparison

R-032 forwards a one-off contribution from the README/comparison session, separate from the registered research executor's assignments. Its note reads [im-not-ai at `b37e0206`](https://github.com/epoko77-ai/im-not-ai/tree/b37e0206d31fffd9149bf57168d4d62eb2086bee) and identifies useful review methods alongside conflicting instructions and unverified effectiveness. Planning read the note, retained at `.awkit/handoffs/im-not-ai-comparison/planning-note.md`; it has not independently repeated the upstream inspection or a live comparison.

Use the following as candidate evaluation cases, not adopted rules or automatic writing gates:

| Candidate | Evidence to inspect in a revision |
|---|---|
| Preserve obligation, possibility, negation and conditions | Compare the original and output directly, including who must or may act and when a claim applies. |
| Preserve phrase boundaries and list relationships | Check whether punctuation or marker changes alter grouping, comparison or an announced list. |
| Remove empty rhetoric without adding a claim | Identify whether a replacement asserts something the source did not support. |
| Preserve passages that already serve the reader | Distinguish a justified local repair from unnecessary changes outside the diagnosed problem. |

Research completed that coverage mapping in R-037. Existing document-intent and scoped-edit evidence partially covers modality, unsupported replacement claims and preservation outside an assigned edit. The inspected fixtures lack a dedicated comparison of phrase grouping or list membership. One invented source with known-good, deliberately defective and unchanged variants could fill that evaluation gap. It would test source-relative judgments, including a no-change decision; a supplied defective variant is not an observed model failure. Mechanical checks cannot make those semantic judgments.

A new example should fill a demonstrated evaluation gap and preserve known-good controls; mechanically countable features do not establish editorial defects. Existing guidance already requires source preservation, scoped corrections and direct comparison with accepted work. No mandatory agent pipeline, style grade, change-rate threshold or change to the English-draft default is selected. Any later trial must name the reader's problem and preservation requirements before revision and separate mechanical checks, direct reading and actual owner acceptance. Private manuscripts remain in their authorized projects.

## Priority after the supplemental writing review

R-036 supplies a supplemental module inventory from the same comparison session, retained at `.awkit/handoffs/im-not-ai-comparison/module-inventory.md`. Its current-source claims refer to the pinned upstream revision above. Historical author-context material and proposed business-document rules remain distinct from shipped functionality. Planning has read the report, without repeating its source inspection or experiments.

The next product question is whether guidance for diagnosing existing prose is being applied too broadly when generating a first draft. The report describes upstream warnings about that transfer; it does not demonstrate the same failure in awkit. A useful change would help an agent choose an appropriate revision while preserving the author's adopted expressions and the document's purpose. More pattern rules or more review stages are not an outcome by themselves.

| Planning priority | Next decision and evidence needed |
|---|---|
| Distinguish drafting from revision | Research maps the current instructions to their intended task and proposes a minimal clarification only where existing protections are insufficient. Implementation answers feasibility questions directly. |
| Preserve author choices within their scope | Reuse current user precedence and project requirements. Establish a missing behavior before proposing additional author-profile storage; the reported retired upstream profile is not an adopted feature. |
| Respect the document's genre | Use the optional Korean commit skill as a reported example of genre-specific design. It does not justify changing this repository's English commit policy or importing proposed business-document rules. |
| Evaluate useful changes and justified no-change decisions | Retain the relationship-preservation case as a bounded evaluation candidate. Judge the requested improvement and source fidelity separately from mechanical pattern counts. |

M-042 assigns the bounded guidance assessment to research. Planning owns the selection and priority of any resulting change; research and implementation exchange technical questions directly. No shipped writing instruction changes in this planning step. Later evaluation must still distinguish improved prose, fewer repeated owner corrections and awkit's contribution to either outcome.

## Selected drafting and revision clarification

R-039 finds a wording tension: Before writing treats existing documents as factual sources without limiting that advice to a new draft, while a later clause protects adopted wording and structure during revision. Existing task scope and user precedence can reconcile the two. This finding supports a local clarification; it does not establish that the paragraph caused earlier failures.

Planning selects replacement of that paragraph, retaining reader-led organization for new drafts and making revision scope explicit. Source meaning and author-approved choices apply to both. A request or applicable requirement can justify an edit without a separately demonstrated defect; the change must not make users defend their preferences. Where no applicable reason calls for revision, unchanged prose is a valid result. Existing text is not automatically accepted text.

Implementation owns the guide change, CHANGELOG, applicable generated guard map and delivery after the current application unit. Research and implementation coordinate a small fictional application exercise directly: new drafting, a satisfactory approved passage and one local actor/condition ambiguity with a relationship-preservation constraint. Fix the inputs and evaluator expectations before outputs; retain corrections and disagreements. Use existing drafting requirements only for affected writing. Direct reading of requested improvement and preservation is separate from packaging checks and rendered inspection.

This unit changes neither the Korean drafting method nor checker behavior and adds no required review stage. The exercise's known purpose and synthetic material limit inference: it cannot prove better real-world prose, fewer reminders or an awkit-caused improvement. The implementation and bounded exercise results are recorded below; technical delivery has its own receipt. The handoff is `.awkit/handoffs/product-research/writing-guidance-implementation.md`.

### Drafting-clarification implementation and delivery

M-143 replaces only the existing source-use paragraph in `kit/writing.md`.
New drafts follow the reader's needs while preserving source meaning, intended
voice and approved choices. Revisions stay within requested scope; unchanged
prose is valid when no request, applicable requirement or reader problem calls
for a change. Explicit requests/preferences need neither defect proof nor renewed
permission. Approval claims remain limited to choices actually approved. Direct
decisions/reasons, source comparison, correction carry-forward, pattern checks,
genre exceptions and the Korean drafting method remain unchanged.

The first fictional application is frozen at
`.awkit/handoffs/writing-guidance-implementation/executor/initial-v1/`. Research
fixed inputs and separate expectations before writing. A retained its facts and
approved voice in two paragraphs; B stayed unchanged with no manufactured English
draft; C changed only one sentence while preserving actors, both-item condition,
permission and administrative endings. Research directly read the actual drafts
against the fixed expectations in direct-channel M-008 and requested no correction.
Its independent identity/body comparisons passed after correcting its BOM reader;
raw files and the initial failed verification remain. Known task purpose,
synthetic material and no human acceptance limit interpretation.

The subsequent request used actual retained C output and ordinary context,
with fresh expectations fixed before writing. The frozen `followup-v1/` changes
only the storage body: retain existing records, record an assigned shelf code in
the exact requested field, or record the specified unassigned value. Earlier
actor, both-item and permission conditions survived. A sentence-local preference
did not spread to the new field label. Research read the actual English draft and
Korean result in direct M-012 and requested no correction. Identity and unchanged
region checks passed. This supports this context-available fictional continuation;
it does not establish cross-session persistence, real author acceptance, saved
reminders or a causal guide benefit. There was no failed prose result to invent.

Implementation inspected the changed paragraph and all four Korean outputs in
new task-owned plain-source HTML views using Edge accessibility text and
screenshots. Paragraphs, source heading order, wrapping and the relevant conditions
were visible at the default desktop viewport. This was not whole-document GitHub
rendering or a narrow-screen check. The owned tab and server were closed; scope
and hashes are in the executor's `rendered-review.json`.

The existing focused packaging/link/word/guard tests (17) and writing checks
passed on snapshot `2fef3fc649444ad271289310ce3e9e2b9e1df27e`, before these final
record additions. The guide has 1,253 words and the generated guard map did not
change. No checker, schema or new test was added. Final cumulative checks,
commit/CI and exact installation identities belong to
`.awkit/handoffs/writing-guidance-implementation/executor/delivery.json`.

Delivery uses an isolated `dev` clone so the original checkout's deferred M-141
work remains intact and excluded. Three initial and four later planning files
were preserved at their transferred hashes before permitted integration edits;
later outcome notes do not claim those edited copies retain the original hashes.
Owner-label and missing-copy preparation mistakes stopped before a check run;
their records remain alongside the successful runs.

## Later passage comparison after owner intervention

Research R-043 compared one later opening and bridge with a retained predecessor
and selected original user messages in place. Both versions preserved part of the
starting question; the later passage made the connections clearer. Some stronger
evaluative wording remains unsupported by the inspected excerpts alone, while
the writer reports additional uninspected material. This is a limited improvement,
not whole-manuscript fidelity or confirmed invention.

Retained owner messages show further intervention before revision, so persistence
without another reminder is not demonstrated. Reported kit use, fuller sources,
fresh writing contexts and owner input changed together. Causal kit contribution
and saved effort remain unknown. Planning read research's report without another
private-manuscript inspection; no private prose was copied here. Research source
identities and limits remain under
`.awkit/handoffs/product-research/executor/later-preservation-output/`.
