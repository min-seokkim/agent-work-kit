# Document workflow implementation plan

Status: bounded document trials and evidence examples have shipped, and one corrected representative presentation page was accepted as probe evidence. The immediate priority is [actual writing outcomes and fewer repeated instructions](tasks/writing-outcome-evaluation.md). The owner has chosen a unified document workflow, with presentation materials as its initial planned application. Broader implementation scope, tool adoption and scheduling remain to be decided through the trials below. This document records future work separately from [development.md](development.md), the entry point for the repository's current state, roadmap, task records and verification evidence.

## Outcome and scope

Help an agent turn source material into a document that serves its reader, remains accurate through revision, works in the required format, and reaches the recipient with evidence of what was checked. Reduce the owner's repeated explanations, recovery of accepted work and manual correction after delivery.

Presentations are documents within this workflow. Their quality depends on material selection, argument, evidence, explanation order, visual expression and actual use. Design and PPTX integrity are parts of that outcome. Use the common principles for reports, proposals, explanatory documents, personal writing and correspondence, choosing methods and evidence for each reader and purpose.

The user should be able to request a finished document without assembling writing, design, conversion and checking skills themselves. The agent carries the audience, purpose, source facts and preservation conditions through the entire task. Use applicable writing methods, task records and review commands to connect the stages; evaluate a method's suitability before making it a requirement. Authoring applications and renderers remain replaceable tools supplied by the environment.

For a local edit, run the affected stages and check its consequences. For review-only work, inspect the existing document against its purpose. Reuse known requirements instead of asking the owner to complete a new questionnaire. Save inspectable sections or representative pages during long work and report what is available, what is being checked and what remains unresolved.

The [review and revision plan](tasks/writing-revision-workflow.md) develops this behavior across successive requests: assess an existing draft, make a scoped edit, preserve adopted choices and carry applicable feedback into a later revision. Its assigned exercises use existing records and comparison tools; additional packaging and genre-specific guidance remain candidates. This work does not complete the presentation and native-editing phases below.

The [design decision](design.md#principles-methods-and-verification) separates common principles, selectable methods and verification conditions. The [method-selection review](tasks/writing-revision-workflow.md#method-selection-review) therefore examines excessive obligations as well as missing guidance. Source expression and the progression of thought can be protected material when they serve the commissioned work. A concise handoff can point to complete required sources; its size does not determine source coverage. Corrections should improve the actual artifact, with persistence scaled to demonstrated continuity needs.

## Basis and evidence limits

The input is the owner's local external-session proposal, titled in translation *awkit document work module proposal*, SHA-256 `25284ea10111700a9f56007cc31ffc6738f24f429137408b99780935ef5b3a66`. This plan incorporates the owner's subsequent decisions about a common document workflow, broader design research and further development of their own methods. The inspected repository base is `f85a1ec`; existing concurrent edits are outside this plan's change scope.

The proposal reports comparisons of conversations, work logs and final artifacts. During planning, the local production procedure, design reference records and selected revision logs were also read. The complete historical conversations and final artifacts were not independently rechecked. Treat reported source-code paths as findings to reproduce, and agent statements of improvement as claims to assess against the artifact and the owner's acceptance.

Preserve evidence distinctions in future research:

- User instructions establish requirements and recorded acceptance; they do not establish that an agent executed every step.
- Work logs establish what an agent recorded. Final files establish their contents and appearance. Neither alone establishes the entire revision history or authorship.
- The owner's confirmation of their contribution takes precedence over inferences from a shared author list. Metadata alone does not establish personal authorship; inherited templates and collaborators' material remain distinct.
- Source inspection establishes a code path; an execution establishes behavior only in the tested environment.
- Missing conversations and unavailable prior versions remain evidence gaps. Do not infer deletion or reconstruct undocumented disputes from a final file.

Keep private originals, source paths, conversation identifiers, work conditions and personal interpretations in their existing private locations. This public-facing repository plan contains generalized lessons and public references. Build public fixtures independently with fictional content; redaction alone does not make a private artifact suitable for distribution. Check reuse rights for reference images, fonts and code before packaging them.

The [expanded essay retrospective](tasks/writing-outcome-evaluation.md#expanded-essay-project-retrospective) adds observations of purpose drift, specific improvements and limits of review records. It supports checking whether the actual output still serves its reader after transformation. It does not establish that essay techniques improve every document genre; the [revision plan](tasks/writing-revision-workflow.md#purpose-and-transfer-between-genres) keeps general principles, conditional methods and unsafe extrapolations distinct.

### Findings from the proposal trial

The [live proposal trial](tasks/workflow-review.md), recorded with `89549b7`, exercised source checking, Korean revision, HTML previews and cross-session review. It supplies evidence for this common workflow without completing the presentation phases below. The installed kit remained at `0f41f0b`; the candidate's passing checks do not establish its behavior in automatic hooks.

The reviewer subsequently reported that snapshots and the channel helped connect claims to evidence, while drafting, reading passes, rendering and frozen checks felt heavy for short edits. The reported five hook firings cover the whole conversation; one occurred during the collaboration. These are firings, not all hook invocations or completed review steps. Neither this account nor the observed corrections measures a productivity gain.

| Finding | Consequence for the next trial | Acceptance evidence |
|---|---|---|
| Mechanical checks passed while preservation and reading evidence were missing. Those duties already existed. | Trace each applicable duty to its actual output or an explicit gap in the existing task record. Diagnose whether it was unavailable, misunderstood or omitted before adding guidance. | Deliberately omit one required review while commands pass; the completion report still names the gap and its consequence. Unsupported check marks do not count as evidence. |
| A report called newly added information a restoration from the original. | Compare the preserved original and candidate before describing what a revision recovered. | A fictional case distinguishes retained facts, additions from new sources and actual restoration; the review narrative matches the diff. |
| An exact hour was supported by an official attachment rather than the cited schedule page. One web tool could not retrieve another valid source. | Attach precise claims to the source passage that supports them; distinguish retrieval failure from missing support. | Keep the relevant excerpt and source identity; qualify an unresolved claim without treating a tool error as proof it is false. |
| Mobile rendering exposed a broken word and crowded footer despite passing pattern checks. | Inspect the affected layout after text edits, including narrow screens when they are a delivery target. | Retain the input identity, viewport and before/after images showing the correction; screenshots alone do not establish that someone read them. |
| Old findings blocked a clean local addition; task checks and whole-repository state had different scopes. | Use the [writing-scope investigation](tasks/connection-diagnostics.md#writing-scope-and-path-limits); state both scopes in delivery evidence. | Old findings remain visible, new and context-dependent failures are exercised, and task success is never described as full-file or repository-wide verification. |

### Scale the work to the change

Start by exercising the existing partial-edit rule: draft and review the changed passage and affected content. The reported burden does not establish that the guides require rewriting or rereading everything after every small edit. The following trial scopes identify work to reuse; they do not waive current mandatory checks or introduce fixed word-count thresholds.

| Change | Work to perform | Evidence that can be reused |
|---|---|---|
| Local wording correction with unchanged facts and structure | Inspect the diff and nearby meaning; apply the required drafting/prose review to that passage; inspect affected rendering and run applicable checks. | Existing audience, preservation conditions and source review when their inputs and claims are unchanged. |
| New fact, number, condition or source | Verify the exact claim and its dependencies, revise the affected argument and review the resulting layout. | Unaffected source checks and sections, with the retained version identified. |
| Reorganization, format conversion or shared style/resource change | Review explanation order, protected content and all output affected by the dependency. | Only evidence whose inputs and coverage remain valid; a local edit label does not establish local impact. |

Use existing records to collect preparation time, active drafting/review time, automated execution time, channel waiting, corrections and defects found after delivery. Keep fixed-deadline waiting separate from necessary work. Compare distinct tasks with similar constraints and state their differences; repeating the same solved task is not a controlled baseline. Missing measurements stay unverified, including [usage counts affected by current logs](tasks/usage-log-compatibility.md). Simplify a step only when its useful evidence can be preserved and the trial records both missed defects and unnecessary work. A reduction in steps alone is not success.

The [scoped document trial](tasks/scoped-document-trial.md#accepted-results) applied this procedure to two fictional documents. Source hashes supported reuse after unrelated edits, while reading caught repetition and an omitted role and rendering exposed broken word wrapping. Its explicit incomplete checkpoint separated command success from missing visual review. These results support the existing procedure without establishing a productivity gain, automatic review enforcement or intended-reader acceptance.

## Common workflow

| Stage | Agent action | Evidence or working output |
|---|---|---|
| Define the task | Establish the reader, use situation, intended understanding or decision, scope, destination application and required editability. | A short brief in the existing task record, including what must survive revision. |
| Select material | Return from indexes to primary sources for important claims. Choose material by relevance, evidence of action and overlap with other sections. | Claims linked to sources; inclusions, omissions and uncertain facts that affect the document. |
| Build the explanation | Decide the order of ideas, section roles, comparisons and dependencies. Assign words and visuals distinct jobs. | An outline or storyboard that explains why each section belongs. |
| Explore expression | Resolve important uncertainty with relevant examples and a representative page using real content. | Selected visual principles, rejected alternatives and a prototype in the required format. |
| Produce and revise | Write and implement the document, preserving accepted features and limiting changes to the task. | An editable candidate and visible intermediate results. |
| Review in use | Check purpose, content, design, requested edits and actual output on the same version. Recheck the reader's task after substantial compression, merging or adaptation. | Findings tied to actual passages and reader impact, with evidence of correction; written destinations for moved requirements and explicit remaining work. |
| Deliver and retain | Deliver the checked artifact under existing authorization rules and retain the accepted result and its evidence. | Identified final files, acceptance status, limitations and a usable next action. |

Keep the outline and review reasoning in working records. They are not a repeated set of boxes, internal identifiers or a checklist to print in the final document. Draft from the reader's needs instead of retaining the source document's structure or turning research questions into the final headings.

### Content and explanation

Connect claims with what supports them. Separate personal work from team outcomes, plans from implementation, and observation from assumptions and interpretation. Preserve conditions, negations, exceptions, units, responsibility and confidence when compressing text. Remove repetition and unnecessary introductions before removing information. Page limits come from the task; a dense argument may need more space.

Use the following patterns when their situation calls for them:

| Situation | Information to connect |
|---|---|
| Technical results | Measurement conditions, result, interpretation, remaining defects and the next development decision. An improvement does not imply the entire problem is solved. |
| Explaining an unfamiliar system | A familiar concept, one concrete example, the actual structure and what the reader can do with it. Reuse the example across text and figures. |
| Requesting a decision | The obstacle, constraints, alternatives, costs, uncertainty and the decision or response needed. Include timing and downstream dependencies when relevant. |
| Retrospective or final report | Reasons for choices, implementation, observed use, limitations and specific changes for the next attempt. Link detailed implementation material where it has a separate role. |
| Portfolio or capability evidence | Relevant choices and actions supported by artifacts. Let photos establish what they can; retain explanations of reasoning that pictures cannot establish. |
| Correspondence | What this recipient needs to know and answer now. Preserve obligations and avoid inventing offers, commitments or urgency while polishing. |
| Combining several sources | Resolve differences in audience, assumptions, status and conclusions before harmonizing style. Surface unresolved contradictions. |

Use the [Korean writing guide](../kit/korean-writing.md) with the existing writing process. Determine terminology, endings, explanation depth, forms, table structure and output requirements for each document. An administrative attachment and an explanatory report can require different endings. Keep familiar job and system names where appropriate and explain unfamiliar abbreviations. Check row heights, line breaks and pagination after wording changes. Personal punctuation preferences and one institution's form are not universal Korean rules.

### Presentation materials

Distinguish a spoken presentation, a deck read alone and material used during questions. Set the explanation depth accordingly. For a spoken presentation, allocate the message between the speaker, screen and supporting material, and check the sequence against the available time. For a deck read alone, keep the context needed without narration. Rehearsal is applicable when speaking is part of the task; the agent can assess timing and transitions provisionally, while the presenter's actual rehearsal is separate evidence.

For each section or slide, establish the reader's question, the point to convey, supporting evidence and an appropriate expression. Choose the slide count from that explanation and any real constraints. A visually prominent number or technically interesting detail does not earn space unless it helps the reader's decision.

## Design and visualization method

Integrate visual decisions while selecting and organizing information. Test content and composition before polishing spacing. A technically precise layout can still emphasize the wrong material.

1. State what the reader needs to understand and which source supports it.
2. Choose an expression: a photo for physical evidence, a diagram for relationships, a table for comparable alternatives, a graph for measured quantities, or prose for reasoning that needs language. Combine them when each has a distinct job.
3. Inspect relevant references. Record the exact page or image seen, the principle to borrow, the adaptation and its limits. Reading text or collecting a URL does not establish that a visual example was inspected.
4. Compare alternatives when the choice matters. Image generation, HTML and canvas can explore composition, scale, crop and layers. Use an existing successful design for routine edits. Tool availability and task size determine the method.
5. Build a representative section with actual content and difficult elements. Check the required final format before expanding to the whole document. A successful cover does not establish that dense diagrams or mixed scripts will work.
6. Compare the result with the brief and accepted work. Inspect the whole document, the reading order on a page and details at intended size. Check adjacent sections for repetition and inconsistent emphasis.
7. Retain a useful method as situation, intended effect, source basis, action, observed result and limitations. Keep rejected approaches when they explain a choice; a list of attractive references is insufficient.

### Methods from the owner's experience

These lessons are generalized from the proposal and the local records described above. Their usefulness across document types still needs the trials in this plan.

| Observed pattern in the records | Method to carry forward | Boundary |
|---|---|---|
| Small formatting improvements preceded a larger correction of purpose and explanation volume. | Check material selection and composition before refining typography and alignment. | Mechanical precision remains useful after the page communicates the right thing. |
| Removing a criticized decoration left an empty, weak composition. | Interpret feedback as a reader problem, then reconsider scale, crop, grouping and evidence. | Avoid permanent bans on shapes, rules, cards or questions based on one correction. |
| A preferred concept lost device placement and connections during implementation. | Name the accepted reading order, relative scale, crop, layers, whitespace and semantic relationships before conversion. | Matching a palette or object count does not establish faithful implementation. |
| Actual product imagery was replaced with a less useful vector recreation. | Preserve real photos for physical evidence; make diagrams and design elements editable where required. | A technique being available does not make it appropriate. |
| Useful prior diagrams were restored after broader edits. | Preserve accepted objects and alter only the required scope, including within a slide. | Source bytes, visual appearance and permitted transforms need separate criteria. |
| Review accumulated explanations and repeated evidence labels. | Consider replacement, deletion, reordering and visual changes alongside additions. | Retain attribution and contribution information the reader needs; do not turn one edit into a rule to remove all sources. |
| A credible reference produced an unhelpful code excerpt in the new document. | Judge transfer by the resulting explanation and reject unsuitable applications. | A prestigious source is not acceptance evidence. |
| Different reading situations used different depth and document roles. | Recompose the material for its audience and use, linking supporting detail where appropriate. | Low word count and uniform layouts are not general quality targets. |

Maintain names and visual meanings across photos, diagrams and text. Use proximity and whitespace to show grouping; apply containers when they convey a useful boundary. Keep the whole system and its details at purposeful relative scales. Review visible edges and glyphs as well as bounding boxes. Crop to preserve the relevant object and working context; effects must not conceal evidence or imply an event the source does not establish.

For technical diagrams, check direction, endpoints, interfaces, branches, entry and recovery conditions against the source. For charts, retain data, units, scales, measurement conditions and sources. Explain what color, size and position mean and avoid color as the sole distinction. For staged reveals, confirm that the static distribution version remains understandable.

Generated concepts can guide appearance. Generated devices, code or measurements cannot serve as factual evidence. A slide-sized image does not satisfy a request for editable text and diagrams. Inserting SVG also does not prove that its internal elements can be edited in the recipient's application.

### External reference program

The following observations come from official documentation, selected source code or research papers read during planning. They are candidates for comparison, not adopted dependencies or tested support claims. Upstream branch links are mutable; pin revisions, record tool and model versions, and recheck capabilities and licenses when running a trial. No external product was installed or benchmarked for this plan.

| Reference and inspected basis | What to investigate | Trial or limitation |
|---|---|---|
| [PPTAgent workflow](https://github.com/icip-cas/PPTAgent/blob/main/skills/pptagent/SKILL.md) and [verification code](https://github.com/icip-cas/PPTAgent/blob/main/skills/pptagent/scripts/pptagent_runtime/core.py) | HTML authoring, editable conversion, source/resource hashes and final PPTX review freshness. | Connect its existing evidence to awkit before building equivalents. The inspected path starts with HTML; preservation of an arbitrary user-edited PPTX remains a separate trial. Recheck platform requirements. |
| [EditPPT paper, version 2](https://arxiv.org/html/2608.20381v2) | Target objects, constrained operations, preservation checks and recovery after failed edits. | Compare requested change and preservation separately. The linked code could not be inspected during planning; paper results are not local verification. |
| [Presenton Template V2](https://github.com/presenton/presenton/blob/main/docs/template-v2.md) and [template workflow](https://docs.presenton.ai/help/create-a-template-in-standard-mode) | Use element structure and rendered examples together; distinguish editable content and fixed decoration; test content capacity. | Vary content density and check the final export. Template generation is distinct from preserving an existing file during a local edit. |
| [Plus AI Remix](https://guide.plusai.com/ai-for-presentations/remix-slides) and [Gamma import](https://help.gamma.app/en/articles/11047840-how-can-i-import-slides-or-content-into-gamma) | Separate content preservation, rewriting and visual reformatting in task controls. | Test exact text and object preservation. Strict mode promises limited rewriting, not a proof of unchanged meaning; Gamma documents static-image imports for some charts. |
| [PowerPoint Copilot](https://support.microsoft.com/en-us/powerpoint/edit-with-copilot-in-powerpoint) | Editing inside the recipient's application and applying existing branding. | Assess targeted edits and final application behavior rather than generation speed alone. |
| [Anthropic PPTX skill](https://github.com/anthropics/skills/blob/main/skills/pptx/SKILL.md) and its [license](https://github.com/anthropics/skills/blob/main/skills/pptx/LICENSE.txt) | Compare authoring, file validation and render review procedures. | The inspected license restricts copying, derivatives and redistribution. Do not treat it as reusable package code. Evaluate prescriptive design rules against the document's purpose. |
| [Duarte Slidedocs](https://www.duarte.com/resources/guides-tools/slidedocs-visual-documents/), [Assertion-Evidence](https://www.craftscicom.org/ae_tutorial.html), [MIT Figure Design](https://mitcommlab.mit.edu/eecs/commkit/figure-design/) | Reader context, message/evidence relationships and the difference between spoken and independently read documents. | Apply to contrasting audiences; do not impose sentence headlines or minimal text on every format. |
| [BrightCarbon design and layout material](https://www.brightcarbon.com/wp/wp-content/uploads/2025/10/BrightCarbon-Communicate-Effectively-with-Dynamic-Visual-PowerPoint-Summary-01-Learning-2025.pdf) | Grid, hierarchy, imagery and explanation sequences; compare actual worked examples. | Reinspect relevant pages visually during the trial. A prior record of viewing a page is distinct from a fresh visual check. |
| [Penrose](https://penrose.cs.cmu.edu/docs/ref/substance/overview), [Napkin](https://help.napkin.ai/en/articles/15923738-getting-started-with-napkin-ai) | Separate relationships from their appearance; generate and compare visual expressions for selected text. | Verify directions and meaning against sources, and editability after export. |
| [Vega-Lite](https://vega.github.io/vega-lite/docs/encoding.html), [Datawrapper](https://www.datawrapper.de/academy/customizing-your-waterfall-chart), [Flourish](https://helpcenter.flourish.studio/hc/en-us/articles/8827970654351-How-to-add-annotations-to-your-visualization) | Data-to-visual mappings, axis and label choices, annotations and guided explanation. | Trace charts to real data and distinguish observed values from interpretation. Inspect static output as well as interactive views. |
| [Slidev animation](https://sli.dev/guide/animations) and [export](https://sli.dev/guide/exporting.html) | Reveal information in explanation order and carry presenter notes through export. | Its editable export documents image fallbacks for unsupported elements; verify required object edits in the target application. |
| [Quarto formats](https://quarto.org/docs/reference/formats/) and [Vale](https://docs.vale.sh/) | Source-based multi-format production and configurable editorial checks. | Use as optional project commands. Test Korean text and destination-specific layout instead of assuming support quality. |
| [Draftable](https://www.draftable.com/products/rest-api), [diff-pdf](https://github.com/vslavik/diff-pdf), [Microsoft PPT-Eval](https://github.com/microsoft/ppteval) | Human-readable comparisons, visual differences and task-based evaluation. | Comparison is not a quality verdict. Assess deployment and maintenance burden; diff-pdf reports inactive development. Benchmark setup is separate from a lightweight project check. |

Also inspect human-authored technical presentations, reports and portfolios. Include dense explanations, decision documents and designs that differ from the owner's usual style. Record reader, purpose, actual page inspected and the resulting adaptation. Public corporate materials do not establish internal templates or hiring preferences.

Use a few representative tasks to compare methods, with the same source facts and constraints. Record omissions, misleading emphasis, usability, editability, export defects, correction effort and operational cost. Prefer existing commands when they meet the need. Adopt a dependency only after a concrete gap, license, deployment and maintenance assessment.

## Integration with awkit

| Existing component | Planned integration |
|---|---|
| [Writing](../kit/writing.md) | Keep audience, preservation, source-based drafting and feedback interpretation authoritative here. Add only missing material-selection and explanation-design steps revealed by trials. |
| [Korean writing](../kit/korean-writing.md) | Reuse its process and per-document conventions; avoid a second Korean rule set. |
| [Work types](../kit/work-types.md) | Connect the common stages to content, design, editability and final-output evidence. |
| [Task records](../kit/protocol.md), [task template](../kit/templates/task.md), [review template](../kit/templates/review.md), [checkpoint](../kit/templates/checkpoint.md) | Express document requirements in existing fields and retain one current task record. |
| [Review implementation](../src/awkit/review.py) and project checks | Run selected authoring, extraction and rendering commands against fixed inputs; retain outputs through `artifacts` and `required_artifacts`. |
| `review verify`, `review accept`, `review compare` | Reuse artifact verification and baselines. Add format-specific evidence through project commands first. |
| Situation skill generation | Evaluate a short presentation supplement, with detailed recipes loaded only when needed. The original `kit/slides.md` and `awkit-slides` names remain candidates. |
| Failure catalogue and hook system | Map a new guard to an observed failure and a reproducible check. Keep ambiguous design and meaning judgments in review. |

At the inspected base, `review verify` checks retained artifact integrity; `review accept` stores an integrity-verified baseline and does not establish human approval or that all checks passed; `review compare` compares registered files by bytes and possible text diffs. It does not identify changed PPTX shapes or establish coverage of every dependency and newly added file. Preserve these meanings when connecting document evidence.

The existing review path requires Git. In the trial, explicitly identify which authoring sources or final editable files enter the snapshot and how external inputs are fixed. Include user edits made in a GUI before capturing the candidate. Keep private trials in an authorized private project; their inputs do not enter this development repository.

Keep standing document conventions in the project's existing profile, source facts and change scope in the task, page roles in the outline, selected features in concept notes, and versioned findings in the review. Execution records need input hashes, commands, environment and output identities. Record who accepted what separately from machine results. A handoff identifies the current file, completed scope, unresolved judgments and next action. Reusable methods and their source evidence remain linked references, not copies of task state.

Independent-session collaboration is optional. Use current channels and records when available; one session must be able to complete the workflow. Document work does not depend on finishing a new collaboration system. After consolidating records, check that important decisions remain and superseded rules have not returned.

Before adding instructions, determine whether an existing rule failed to load, was misunderstood, lacked an execution tool or could not be verified. Address that cause. Keep always-read text and situation guides within the repository's word limits; put detailed recipes in references. New or changed guards require their `Prevents:` or `PREVENTS` declaration and `python scripts/guard_map.py --write` under repository policy. This plan adds no runtime guard.

Candidate mappings are F1 for unchecked output; F14 for Korean conventions; F15 and F34 for reader-oriented composition; F16 for regressions; F18 and F33 for ineffective review; F21 and F29 for handoffs; F22 and F30 for factual meaning; F31 and F32 for applying the reason behind feedback. F17 supports a version-mismatch test, but the proposal did not establish an actual historical delivery incident. Recheck current catalogue evidence before adding occurrences.

Hook changes follow demonstrated need and the existing hook reliability work. Detect relevant operations rather than isolated words. Confirm that required guidance was successfully read. Missing mandatory checks and stale evidence can be machine-detected; persuasion and visual quality do not become automatic blocking scores.

## Candidate supporting tools

Implement these only where the integrated trial exposes a gap. Begin as project check commands and keep the first supported object set explicit. CLI names and output schemas are not settled by this plan.

### Extraction and scoped comparison

Start with actual slide order, dimensions, text and referenced resources. Follow presentation relationships; XML filenames do not establish presentation order. Expand to shape type and geometry, image crop and transforms, groups, mixed text formatting, connectors, tables, charts and freeforms when required by an observed failure. Report unsupported objects and incomplete coverage without silently treating them as empty or unchanged.

Keep the original hash separate from normalized comparison data. Distinguish byte, structural and rendered differences. Follow shared images, themes, masters, layouts and chart dependencies when deciding which slides may be affected. Match slides across insertion, deletion and reordering; report ambiguous correspondence. Resolve protected elements within a changed slide as well as protected slides.

Make inspection read-only. Do not re-save the source, execute macros or refresh external connections merely to compare it. ZIP metadata changes should not be described as design regression. An unchanged slide XML file does not establish unchanged appearance when a dependency changes.

### Rendering and review evidence

Connect available renderers and retain their program/version, font conditions, settings, input hash, PDF, page images and contact sheets. Compare like environments where possible; report renderer differences separately from document changes. Provide side-by-side accepted, candidate and concept views. Use pixel differences to locate changes, with human review determining whether they are intended and useful.

Revalidate evidence after source or dependency changes. Record pass, fail, intentional skip, unavailable tool and execution error distinctly. A mandatory unperformed check leaves completion incomplete. Obtain expected page counts and other invariants from requirements, not from the candidate itself. Check requested text, shape, table and connector edits in the target application; file structure alone is insufficient.

### Content changes and prior tools

Start with extracted text and diffs. Flag changed numbers, units, conditions, negation, contribution and status language for source review where feasible. A detector locates a candidate issue; it does not certify meaning or reward a particular wording.

Inspect the private earlier tools as case evidence in their authorized location. Evaluate extraction/spec exchange, whole-object preservation and slide grafting, in-place edits, fit and visible-glyph measurement, photo provenance, rendering and candidate replacement with recovery. Test relationship remapping, cumulative coordinate transforms, mixed formatting, image bytes, connector rotation and flips. Preserve authoring originals and accepted results; clean disposable candidates under existing retention policy. Reuse awkit ownership and state records instead of importing the earlier handoff system.

The proposal reported three unexecuted code findings: a missing OOXML validator could still permit a pass; a candidate supplied its own expected slide count; and unchanged-slide comparison was conditional on equal counts. Reproduce these failure classes with synthetic fixtures before implementing guards. Historical tool limitations do not establish defects in current upstream versions.

## Implementation sequence and completion

| Phase | Work and output | Exit condition |
|---|---|---|
| A. Prepare the method trial | Map current instructions to the common workflow; select a source bundle and task; inspect relevant external methods and local examples. | Gaps are classified as guidance, execution or evidence problems; trial requirements and preservation targets are explicit. |
| B. Complete one presentation task | Use existing tools from source selection through outline, representative page, editable production, revision and final review. Connect outputs to existing awkit records and checks. | The material serves its specified audience and use; content, design, editability and actual output have separate evidence on the delivered version. |
| C. Exercise human revision and recovery | Incorporate a person's edit, change another region and introduce controlled unintended changes. Try existing comparison tools first. | Requested changes and protected content are checked separately; stale renders and out-of-scope changes are detected or explicitly reported as uncovered. |
| D. Add demonstrated missing tools | Implement the smallest extraction, dependency comparison or evidence adapter needed by B and C. | Important failure paths have reproducible tests; limitations and environment requirements are visible; required-check omissions cannot be reported as complete. |
| E. Apply the method beyond slides | Create a Korean report and a contrasting presentation or standalone reading document using the common workflow. | Structure, explanation depth and conventions adapt to the reader; the method does not require portfolio-specific rules or duplicate writing guides. |
| F. Package proven guidance | Shorten the shared guidance, add only necessary format supplements and a runnable public synthetic example, and integrate generated skills where justified. | Existing checks, packaging and Windows/Linux CI pass for the implemented scope; user correction burden and remaining defects are recorded. |

Proposed first task: a fictional technical system with source notes, a real synthetic measurement dataset, diagrams/assets, decisions, unresolved limitations and clearly separated roles. Produce a short technical presentation for a specified audience and duration. Test a representative page containing a diagram, quantitative evidence and Korean text. Derive a reading document or decision report from the same source bundle later, changing the explanation for its reader rather than exporting the same layout twice. The owner or a designated reader evaluates the actual result; agent review remains labeled as self-review.

Public fixtures must contain enough realistic complexity to expose the recorded failures. A private real task can establish usefulness later without publishing its evidence. Save visible intermediate work so the owner can inspect the direction before the entire document is finished; do not turn every stage into a mandatory approval request.

<a id="next-bounded-evidence-example"></a>

### Bounded evidence example

The public synthetic reading-document example uses the existing review runner. The earlier scoped document trial demonstrated an honestly reported missing visual review and input-hash-based reuse; it did not demonstrate automatic detection. The original documents example checks titles and links. `review verify` checks retained artifact bytes, while `check done` matches the repository tree to a passing run. Neither determines whether a render covers the selected source and style dependencies or whether a required reading pass was recorded.

The handoff supplied one short fictional decision note, a separate requirements record, a shared style file and a declared review record. Source, preservation and rendered-review duties were fixed before producing the candidate. Existing `checks.toml` artifacts retain source/dependency hashes, renderer identity and outputs. An example-specific checker distinguishes an absent required record, a mismatched input hash and an explicitly unavailable review. Matching metadata establishes recorded coverage, not the quality of the reading or the truth of a reviewer declaration.

The [repository example](../examples/document-evidence/README.md) returned at snapshot `eb09d44` and was accepted for cumulative integration. Its focused run passed Ruff, sixteen tests with one Windows symlink-privilege skip, and writing checks. Retained cases distinguish missing review, stale shared CSS with unchanged prose, reusable evidence after an unrelated change, unavailable review, corrupt image, wrong source identity, complete actual evidence and later retained-artifact corruption. The existing `review verify` handles that last case; its success on a retained failed-check run does not convert the check to a pass.

Both executor and planner read the fictional note against independently fixed requirements and inspected the actual Edge captures at 1200 px and 390 px. Example-local attributes preserve exact text and PNG identities through Windows Git checkout. The source, output and rendered-review records remain declarations of coverage, not proof of review truth or author acceptance. The example shipped in `54821fa`; the [delivery receipt](tasks/document-intent-trial.md#delivery-receipt) records cumulative verification, CI and exact installation. Local focused evidence is under `.awkit/handoffs/document-evidence-example/executor/`. This optional example adds no completion hook, global registry or claim that presentation phases are complete.

### Coverage and author intent follow-up

The [document intent trial](tasks/document-intent-trial.md) followed the bounded evidence example. Real-use feedback reported a planned idea mistaken for an omission when only finished outputs were inspected, and author intent weakened during editing. Fictional cases separated incomplete review scope, handoff information, guidance use and missing capability questions. The paired drafting compared direct Korean with the existing English-draft procedure under the same preservation requirements. The task record owns the fixtures, source completeness, evaluation and implementation decision; neither the evidence example nor agent review establishes human acceptance.

That trial delivered source-derived brief guidance in `54821fa` and a reusable fixture in `e5e8d17`. Ordinary records supported the small coverage query; the writer follow-up caught the brief error but still required correction of two new prose assertions. These results do not support a new index or a drafting-method winner. The task record retains the comparison and its limits.

The [representative presentation trial](tasks/presentation-method-trial.md) exercised part of phases A/B with existing tools. It used an independently invented threshold tradeoff and fixed preservation requirements before authoring. Source comparison caught a diagram error after mechanical checks passed; the corrected page supplied final-file rendering and native-object evidence. Full presentation and human revision phases remain open. Further tool additions depend on an observed missing capability.

### Verification scenarios

| Scenario | Expected evidence |
|---|---|
| An attractive but irrelevant detail dominates the document | Content review restores weight to the reader's question and supporting evidence. |
| A revision retains the stated purpose in its plan but changes the body's question, or assigns an omitted argument to an unwritten section | Direct reading identifies the changed purpose and checks actual destination passages; planned work remains pending. |
| A technique useful in a reflective essay is imposed on a decision report or instruction | The result meets its reader's task, retains necessary uncertainty and uses a suitable conclusion; the local technique remains conditional. |
| Compression removes a condition, negation or uncertainty; a plan becomes a completed result; team work becomes personal work | Source comparison identifies the meaning change. |
| Source documents disagree on audience, assumptions or conclusion | The contradiction is surfaced and resolved or retained as uncertainty. |
| A technical report and an administrative attachment inherit the same Korean endings or internal IDs | Review applies each document's conventions and reader knowledge; the rendered form still fits. |
| All configured commands pass but preservation, a required reading pass or rendering is missing | The report distinguishes command success from the omitted duty and identifies what remains unverified. |
| A short correction triggers repeated full-document preparation | Apply the scoped workflow above; retain unchanged evidence and measure work saved and defects missed before changing standing guidance. |
| A report claims a fact was restored, but it never appeared in the preserved original | Correct the revision history and cite the new source instead of inventing lost content. |
| Reviews repeatedly add explanation or react to feedback by deleting all decoration | Compare replacement, deletion, reordering and visual alternatives against reader impact. |
| A representative page works, but denser content breaks it | Test realistic content variation and final-format output before wider reuse. |
| A generated concept is inserted as a full-slide picture | Requested native edits fail the editability check. |
| Protected wording, a photo crop or a complex diagram changes during a local edit | Compare protected objects within and outside the changed slide against the accepted version. |
| Slides are inserted, removed or reordered without corresponding XML filename changes | Report actual order and reliable or uncertain slide correspondence. |
| A shared image, theme, master, layout or chart changes | Include affected slides even when their own XML is unchanged. |
| Connector rotation, flips, mixed formatting or freeform content is lost | Structural and visual checks detect supported cases; unsupported coverage remains explicit. |
| ZIP metadata alone changes | Distinguish byte changes from substantive differences. |
| Validation is missing, crashes, or uses the candidate's count as the expectation | Report missing/error status and compare with independent task requirements. |
| The PPTX or a dependency changes after review | Previous render/review evidence cannot establish completion for the new version. |
| Renderers substitute fonts or differ in spacing | Identify environment differences; inspect the recipient's actual output separately. |
| An old handoff revives a discarded rule or omits a necessary procedure | Compare the handoff with current decisions and preserve an executable next action. |

Keep mechanical fixtures separate from reader judgments and renderer-dependent integration tests. Meaning review is not an exact-match test against an approved sentence. Report the OS, application, renderer, fonts and object coverage actually exercised. HWP/HWPX editing and validation remain unverified future work; PDF conversion alone cannot establish them.

## Success measures and open decisions

Record repeated explanations of the same requirement, restored accepted elements and their cause, defects found after completion, the owner's correction time and correction type, time until usable output, measured usage, missed errors and unnecessary blocks. Keep unmeasured values explicit. Revision counts, generation calls, character counts and automatic pass rates describe activity, not document quality. Repeating the same task with an informed user is not a controlled comparison of workflow effectiveness.

Before implementation, settle the pilot environment and final application, the first audience/use case, required native edits, how acceptance is recorded, and the tool versions to test. Select skill names, new CLI commands, schema changes and dependencies only after evidence of need. Broader DOCX/HWPX editors, comprehensive PPTX object support and extra collaboration infrastructure are later decisions. The common workflow must remain usable with the project's existing tools.

For implementation, follow the repository's CHANGELOG, guard-map, snapshot/check, packaging and CI rules. This planning-only document changes no runtime behavior or supported format. The next implementing session should read current [AGENTS.md](../AGENTS.md) and [development.md](development.md), inspect the live worktree, then propose a scoped Phase A/B assignment without displacing concurrent work.

## Coverage of the incoming proposal

This is a content audit, not evidence that the proposed workflow has been implemented. All proposals judged useful have a destination above; deferred tools remain explicit candidates. Private case narratives and source indexes remain in the original handoff.

| Incoming proposal area | Disposition in this plan |
|---|---|
| Reduce repeated explanation and recovery; use existing awkit | Retained in Outcome, Common workflow and Integration; broadened to document completion across formats. |
| Evidence types, authorship corrections, missing conversations and local privacy | Retained in Basis; case identities and private source locations omitted from the repository. |
| Actual reference inspection and adaptation | Retained in Design method and External reference program, including viewing limits and rejected transfers. |
| Feedback overcorrection, preferred-concept loss and ineffective iteration | Retained in Methods from experience and staged review; no fixed iteration or image-generation quota. |
| Reader-driven material selection and return to original sources | Retained in Common workflow and Content and explanation. |
| Explanation accumulation, handoff loss and visible intermediate results | Retained in Content, Integration and the implementation trial. |
| Successful final edits, different reading situations, correspondence and extended argument | Retained as generalized methods; preserve necessary reasoning and allow greater length when justified. |
| Korean compression, recipient-oriented rewriting, terms, endings and output | Retained in Content and verification; HWP/HWPX remains unverified. |
| Measurement-to-decision, familiar examples and decision requests | Retained as distinct content patterns with conditions, costs and downstream effects. |
| Retrospective choices, field outcomes, document roles and uncertain plans | Retained in Content; source contents establish chronology, not filenames alone. |
| Avoid universal design bans and inferred personal authorship | Retained in Basis, experience boundaries and audience-specific method trials. |
| Scale work to the request; storyboard; image/canvas concepts; native implementation | Retained in Common workflow and Design; representative final-format testing comes early. |
| Accepted-version preservation and four reviews on one file | Retained in Integration, tool evidence and Phase B/C exit conditions. |
| Structure extraction, dependency/scoped comparison, render comparison and text changes | Retained as staged tool candidates; narrowed initial extraction and explicit expansion criteria. |
| Earlier tools and three validator failure paths | Retained in Content changes and prior tools; reproduce before claiming a fix. |
| Short guides, generated skills, existing failures and restrained hooks | Retained in Integration; identifiers and new guards remain conditional. |
| Minimal metadata linking sources, authoring files, outputs, reviews and acceptance | Retained in Integration and Rendering; existing records remain authoritative. |
| End-to-end example, real work, public synthetic fixtures and platform-specific evidence | Retained in Phases A-F and Verification; first trial now covers full document creation. |
| User burden measures, observed limits and implementation handoff | Retained in Success measures, Basis and next-session instructions. |
| Original local source index | Kept private in the hashed handoff; replaced here by generalized evidence and public references. |

Coverage review also preserves these qualifications: actual attribution remains where needed; filenames do not establish chronology; a visually pleasing diagram can be semantically wrong; unavailable tools limit claims; user acceptance, technical checks and delivery are separate; and prior tool limits are not assertions about current versions. External research and the owner's later direction add explicit method comparisons and a common document workflow to the original proposal.
