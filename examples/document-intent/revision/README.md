# Review and successive revision

Use this optional example to assess an accepted fictional passage or revise a fictional equipment-return procedure across two requests. All needed source material is linked below. Choose an empty local run directory in your project, outside this example, and keep each result there. Use the current [Writing Guide](../../../kit/writing.md) and [Korean Writing Guide](../../../kit/korean-writing.md), recording their checkout revision or file hashes in your existing task notes. Direct Korean drafting and an intermediate language are both available unless the task explicitly chooses one. Retain an intermediate draft only when you use one.

Read this entry and the selected participant files first. Keep `evaluator/` and `walkthrough/` outside the participant's reading scope until the selected route's outputs are saved. This is a reading instruction, not an access-control boundary. Disclose earlier exposure; an informed practice run is still useful. These are repository examples; `awkit kit example` does not install this folder. Use a checkout of the repository, or copy this example with its linked guides while preserving relative paths.

## Review only

Read [the review request and passage](participant/review.md). Save the assessment as `review.md` in your run directory. Assessment alone does not authorize rewriting; a well-supported decision to leave the passage unchanged completes this route. Then read the review section of [the evaluator criteria](evaluator/criteria.md) and retain the comparison in your usual task notes.

## Successive revision

1. Read [the source document](participant/source.md) and [the first request](participant/stage-1.md). Save the full first Korean result as `stage-1.md` in your run directory. Put the method used, source comparison and any intermediate draft in separate notes. Preserve the first result if it has a defect; save corrections under new names and record the reason.
2. After retaining that result, read [the subsequent request](participant/stage-2.md). Its baseline is this run's actual `stage-1.md`, or a separately retained corrected version if one was needed. Record the selected baseline path and its SHA-256 before editing. Treat that version as adopted only for this fictional scenario. Keep the source, first request and prior notes available as ordinary context. Save the full later result as `stage-2.md`; keep the selected baseline unchanged.
3. After saving both stages, read [the evaluator criteria](evaluator/criteria.md). Compare stage 1 with the supplied source, then stage 2 with the selected actual stage-1 baseline. Record requested improvements, unintended edits, unresolved defects and any extra explanation needed to follow this entry. Keep unsuccessful outputs and later corrections separately. A successful rerun does not erase an earlier failure.

Use your project's existing task record for file identities, method, guide revision, comparison and limits. For file comparison, Git accepts complete local paths: `git diff --no-index -- "path/to/stage-1.md" "path/to/stage-2.md"` (exit 1 means differences). In PowerShell, `Get-FileHash -Algorithm SHA256 -LiteralPath "path/to/stage-1.md"` records the baseline identity. Substitute actual paths; neither command judges meaning. No custom run format is required.

## Continue in a separate session (optional)

To split successive revision across independent sessions, use your project's ordinary entry and current task record. In an isolated example project, these may be `README.md`, `docs/tasks/equipment-return.md` and `runs/equipment-return/`. The producer creates the record if it is absent; the receiver continues in the producer's run directory. Keep the copied example and linked guides' relative paths intact.

1. Producer: perform step 1 of Successive revision only. Save the actual full result and required notes, then create or update your own current task record using the project's [checkpoint guidance](../../../kit/protocol.md#resume-after-interruption), with its [template](../../../kit/templates/checkpoint.md) as the fallback. Make that record reachable from the ordinary project entry. Stop before reading stage 2, evaluator material or walkthroughs.
2. Receiver: start a separate conversation at the project entry. Follow its current record to locate and verify the actual result and relevant inputs, then perform step 2 of Successive revision and update that same record. Use the existing baseline-identity and retention instructions. If necessary state cannot be located, report what is missing. Do not replace producer state with a transcript, walkthrough output or operator-written handoff.

Preserve the producer's record as it stood at handoff in ordinary history or an unchanged evidence copy before the receiver updates it; keep one current record. If files move between projects, preserve their bytes and working relative links. Record relocation without rewriting the producer's handoff for the receiver.

Keep evaluator material and walkthroughs unread until both stages are saved. Then the receiver follows step 3 of Successive revision unless a separate evaluator is assigned. Record any extra location hint or repair needed to continue, and disclose prior exposure. A report of missing state is useful evidence; it does not establish successful continuation.

## Inspect a completed execution

The optional [historical walkthrough](walkthrough/README.md) supplies actual earlier outputs and their provenance. It used the then-current intermediate-language instruction. It is an example to inspect after practice, not a replacement for your run's stage-1 result or a required phrasing. Agent reading, mechanical comparisons, rendered inspection and real-reader acceptance are separate observations. This exercise alone establishes no lasting memory, fewer owner reminders, language-method superiority or causal benefit.
