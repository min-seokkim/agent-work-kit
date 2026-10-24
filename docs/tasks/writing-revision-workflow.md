# Reviewing and revising existing writing

Status: product plan with units 1 and 2 exercised under M-143/M-145. The guide clarification and its technical delivery are recorded in the [outcome evaluation](writing-outcome-evaluation.md#drafting-clarification-implementation-and-delivery). This plan defines the broader behavior those exercises inform. It does not report a shipped skill, command or quality improvement. Planning owns product choices; research supplies evidence and implementation owns changes, checks and delivery.

## Outcome

A user can ask for an assessment, a local edit or another revision of an existing document without explaining applicable requirements again or recovering passages the agent unnecessarily changed. The result must solve the requested reader problem, retain the author's intended claims and choices, and remain usable in the requested format.

This extends the [common document workflow](../document-workflow-plan.md). It does not replace unfinished presentation production, native editing or human-acceptance work. The [outcome evaluation](writing-outcome-evaluation.md) owns real-use observations and the distinction between improved writing and awkit's contribution.

## Evidence and existing coverage

The owner reports repeated style corrections and author intent weakened during editing. Retained research identifies a later improvement after further owner intervention; it does not demonstrate persistence without reminders or a missing storage capability. Existing guidance already covers source comparison, accepted wording, scoped revisions and carrying correction reasons forward.

The [reported im-not-ai inventory](https://github.com/epoko77-ai/im-not-ai/tree/b37e0206d31fffd9149bf57168d4d62eb2086bee) suggests useful methods: sample assessment, scoped redo, final source comparison, genre-specific handling and short rule views generated from shared material. The local investigation is retained in `.awkit/handoffs/im-not-ai-comparison/module-inventory.md`. Planning read that report rather than independently repeating its upstream inspection. Historical author profiles and proposed extensions are not treated as current integrations; runtime effectiveness was not tested by the inventory.

Use the existing writing guides, project requirements, task records, snapshots and comparison tools first. The missing product evidence is whether agents apply them coherently through successive requests. A new command, profile store or required agent pipeline is not selected.

## User requests and expected behavior

| Request | Agent behavior | Result the user receives |
|---|---|---|
| Assess an existing draft | Recover its reader and purpose from available context. Inspect the requested scope, identify concrete problems and distinguish them from preferences. A sample assessment states its coverage. | A concise assessment with locations, reader impact and proposed repairs. An acceptable passage may need no change. Review alone does not authorize an unsolicited rewrite. |
| Make a local correction | Apply the requested change and inspect affected meaning and layout. Preserve adopted wording and structure outside scope. Explicit preferences are sufficient reasons to edit. | The revised document and a short account of the meaningful change and remaining limits. No additional approval step is introduced for an already authorized edit. |
| Rework for a different reader or purpose | Identify which content, structure and conventions must change, while retaining source meaning and protected author choices. | A document organized for the new use, with source limits intact. A request for new structure is not permission to invent a new author position. |
| Revise again after feedback | Carry the earlier correction's reason and scope into the new request. Use the retained current version and existing records. Current explicit instructions supersede earlier choices. | A new revision that solves the new request without silently undoing still-applicable work. |

Diagnosis and revision are functions in this flow, not mandatory separate agents or user approval stages. A direct edit request does not require a preliminary assessment report. Use the existing affected-passage drafting procedure; an unchanged passage needs no manufactured draft.

## Requirements that survive a revision

Recover the applicable requirements before editing: reader and purpose, source claims and their uncertainty, adopted expressions and structure, requested format, and earlier corrections with their scope. Keep original material distinct from excerpts, summaries and reconstruction. Unknown source coverage remains unknown. Consult project plans before claiming that an idea is absent from the whole project.

Do not treat every existing sentence as accepted. Preserve deliberately adopted choices within their actual scope, and distinguish them from provisional wording. A preference for one sentence does not automatically apply to the entire project. A later explicit change can supersede an earlier choice without being classified as a preservation failure.

Compare the candidate with both its source and the preceding version. Mechanical comparison locates changes; reading determines whether a changed condition, relationship or author judgment is justified. Use the project's existing requirements and task record for continuity. Do not create another mandatory preference ledger or ask the user to restate information already available there.

## Implementation sequence

| Unit | Concrete output | Acceptance and decision boundary |
|---|---|---|
| 1. Clarify the entry behavior | The assigned replacement paragraph in `kit/writing.md`, with its existing packaging and delivery. | New drafting and revision are distinguishable without weakening source preservation, explicit preferences or genre conventions. This is M-143, not an additional assignment. |
| 2. Exercise a subsequent request | Reuse one actual output from the first fictional exercise. Fix a new request and evaluator expectations before producing the next revision. | The new request requires a real edit; prior applicable requirements are not repeated in it. Ordinary retained context remains available. Reading identifies regression, unnecessary edits and inappropriate spread of a local preference. Research and implementation coordinate directly under M-045/M-145. |
| 3. Package a usable review-and-revision route | A worked scenario in the existing document-intent example, with fictional sources, successive requests, actual before/after outputs and evidence limits. Link it from the existing writing reference without adding a command. | Include the corrections the exercise actually needed. Another agent can follow the route from its ordinary entry point without the planner explaining missing steps. Do not claim less user effort from a packaging check. |
| 4. Test genre adaptation | One fixed fictional source used for a standalone explanation and a short administrative entry, with separate reader requirements. | Necessary facts and uncertainty survive; sentence endings, detail and structure fit each use. Reuse the current administrative case where possible. Select a format supplement only if the common guide is insufficient. |
| 5. Improve rule maintenance when needed | A documented candidate rule with its condition, reason, counterexample and observed side effects, using the existing failure/evidence records. | Promote only a supported general lesson. Generate shorter views from a common source if duplicated guidance actually causes maintenance drift; do not build that machinery merely because upstream has it. |

Units 1 and 2 produced retained fictional outputs; research requested no correction in direct M-008/M-012. The successive request used ordinary retained context and preserved the earlier applicable conditions without spreading a local preference. This is bounded semantic evidence, separate from mechanical checks, scoped rendering and real author acceptance. Technical delivery has its own receipt. Units 3 through 5 are planning candidates, not concurrent work. The owner selected [session creation and communication](session-orchestration.md) as the next feature after the assigned writing work; unit 3 requires a later selection. Later writing units depend on a concrete unmet need. Preserve the current Korean drafting method while assessing these behaviors. This plan does not select a language-method winner, pattern score, edit-percentage target or fixed number of reviewers.

## Worked-example package contract

Unit 3 should make the completed method usable without the private collaboration channels or this planning session. Extend `examples/document-intent/` with a distinct revision scenario and preserve its existing coverage task, flawed weather-station brief and method-comparison instructions. Update the example's introduction to distinguish the scenario families. Do not overwrite an earlier observed failure with a corrected input.

The new entry point offers review-only and revision-follow-up tasks. A review request returns an assessment; an authorized revision request proceeds to editing. The instructions name the actual participant materials, ordinary current guides and where to retain outputs. They must not imply that an example folder restricts file access or that the existing `awkit kit example` command installs this repository example.

| Artifact | Required content and use |
|---|---|
| Participant source and first request | Independently invented material, reader and task scope, source conditions and the actual approved-choice premises used in the completed exercise. No private source adaptation or planner-channel dependency. |
| Subsequent request | A genuine new change, released after the first result is retained. The request does not restate the earlier applicable correction, but ordinary project context remains available. A sentence-local preference must remain local. |
| Evaluator material | Meaning, scope and preservation criteria fixed before the corresponding output. Keep it outside the participant's initial reading scope. Accept several valid wordings and a justified no-change decision; do not prescribe a canonical sentence. |
| Retained execution | Actual first and subsequent outputs, corrections and the guide/input identities used. Clearly distinguish scenario approval from real human acceptance and agent judgments from mechanical results. |
| Reproduction instructions | How to start each task, retain its result and perform direct comparison using existing records and commands. Provide complete file inputs where a command requires them; no hidden preparation by the planner. |

The package must allow a reader to determine what changed, which prior requirements still applied and what was actually checked. If the first execution failed, keep the failure and correction visible. If no failure occurred, do not introduce one and describe it as observed. Optional deliberately defective controls must be separately labeled.

Implementation owns integrity/packaging checks and rendering of the final documents. Direct reading supplies the semantic result. A separate use from the documented entry point can establish that the route is usable without manual relay; merely adding files and passing tests cannot. A successful repeat does not establish long-term memory, real-author preference retention, reduced cost or superiority over upstream.

Keep the worked scenario optional. Add one discoverable reference to it rather than loading all inputs, outputs and evaluation rules into every writing session. The existing generated skills remain the entry to current writing guidance. A separate review/redo skill is a later packaging decision only if the current entry point proves insufficient.

## Observation and stopping criteria

For each exercised request, retain the source and preceding version, applicable requirements, actual candidate, corrections and the method used to judge it. Reuse existing evidence rather than introducing a second record format. Separate mechanical checks, source/meaning review, rendered inspection and real user acceptance.

Record whether the requested improvement occurred, whether unaffected adopted content changed, whether a prior applicable correction recurred, and whether resolving it required another owner intervention. Do not count a new requirement as a repeated reminder. Time, usage, edit burden and causal kit benefit remain unknown unless supported by observations.

A synthetic success supports the tested behavior only. If existing procedures suffice, retain and package them where useful; do not invent a missing feature. If a case fails, research identifies the missing information or decision and works directly with implementation on technical questions. Planning selects the product change. Stop expanding a case when the evidence settles that decision.
