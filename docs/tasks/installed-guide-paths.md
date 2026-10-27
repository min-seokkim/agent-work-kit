# Installed guide paths

## Current status

Completed correction and isolated repair trial. Package guide paths shipped in `8c4cd7e`; the project diagnostic shipped through `2d41ba1`. Existing capabilities restored the selected fixture reference.

Next action: Reuse the documented targeted repair when authorized. Real-project repair, native reloading and different-version migration remain unassigned; this case selected no general updater.

## Earlier scope and evidence

The following sections retain the original assignments and observations. Their stage-specific status statements are historical; use the current status above when resuming.

Status: the package correction shipped in `8c4cd7e`; the read-only project diagnostic is implemented in `335270b` and delivered through repair commit `2d41ba1`, as reported in `R-048` and the execution receipt below. Preserved malformed project settings remain unrepaired. Original base: `aca1ab9512159ec291e4eef50c71b2e72bb2cb7f`. Planning owns development feedback and scope; implementation owns execution records, verification and delivery under `M-081`. The original implementation session owned the assigned source, tests, CHANGELOG and generated guard mapping. Channel `.awkit/document-feedback-implementation.sqlite3` used main for the planner and reviewer for the implementer; this was informed collaboration, not independent review. M-001 assigned the correction; R-002 returned its candidate.

## Report and reproduced behavior

A separate document project reported a generated `rules.toml` whose kit value was a `MultiplexedPath(...)` representation. Its feedback channel remains outside this repository. The owner's explicit boundary is technical awkit feedback only: this development session does not plan, review or approve that project's documents. Private source material is neither needed nor copied here.

The planner reproduced the defect with the installed `aca1ab9` package and isolated Python 3.14.7. Both a project using bundled default rules and a project with newly drafted rules emitted a nonexistent `MultiplexedPath(...)/work-types.md` reference. The packaged guide itself exists. A local-kit control emitted `kit/work-types.md` and that file was readable. These were explicit hook CLI calls on fictional inputs, not observations of automatic execution by a native client.

Evidence is under `.awkit/handoffs/document-pilot-feedback/resource-path-lh2pwn2f/`; its helper is `probe_resource_path.py` in the parent folder. The initial `resource-path-nr5f2e8a` probe remains retained: only its generated-rules case supports this finding. Its other cases discovered ancestor repository rules and were confounded. The corrected probe uses temporary projects outside any ancestor with rules.

`hooks.kit_folder` stringifies `kit_root()` for an installed fallback, and `kit_hooks.draft_rules` persists that value. Installed namespace resources and checkout paths have different representations. Existing source-tree tests exercise the latter, so their pass does not establish the installed reference's usability.

## Acceptance and ownership

The emitted guide reference must locate readable content and remain usable after the generating command exits. Cover bundled defaults and newly generated rules, preserving project-local kit precedence and resource reading. Verify the correction against a built, isolated installed artifact as well as meaningful regressions. Do not replace the live installation during candidate work.

Custom rules and the other project's files remain unchanged. Previously generated malformed values need an explicit migration or repair decision; a package correction alone does not establish their repair. No automatic migration, writing-policy change, enforcement change, dependency or version bump is assigned. Unsupported installation formats remain explicit rather than inferred from the tested package.

The accepted three-file candidate changes `kit_root()` to look up `kit/` from the regular `awkit` package. It adds a regression that reproduces the installed namespace layout and checks emitted guide references after the process exits. The regression failed before the correction; both project-local controls already passed. Frozen run `.awkit/reviews/review-pdvm_25p` passed Ruff, 82 affected tests without skips and complete CHANGELOG writing checks. This is focused verification, not the full repository suite.

The executor built a wheel from the accepted snapshot and installed it in an isolated temporary environment. Its loaded modules matched the frozen source. Four actual CLI cases checked bundled rules, drafted rules, local kit and local precedence; referenced guides remained readable after exit. A malformed prior value plus a fictional user edit survived hook installation unchanged. The planner inspected the full product diff, regression and artifact helpers, actual reports and failure records. The existing live installation was not replaced during candidate review.

Evidence is under `.awkit/handoffs/document-feedback-implementation/executor/`. The first artifact helper failed on an incorrect API import before running its fixtures; the corrected helper passed without a product change. The initial channel notice was refused for using a reply field with a notice, then corrected. These orchestration failures and a restricted evidence-read failure remain distinct from the reproduced product defect. Final repository checks, normal dev push, exact-head Windows/Linux CI and installed-content comparison belong in `.awkit/handoffs/document-feedback-implementation/delivery/validation.json`.

## Subagent-use evaluation

The owner requested evaluation and improvement of subagent use during this work. One read-only scout located existing hook-path tests and wheel CI entry points. It owned no implementation files, performed no reproduction and ran no tests. The requested configuration was `gpt-6-luna` with low reasoning effort; actual model execution and task cost have not been independently verified.

The scout returned relevant locations in `tests/test_hooks.py`, `tests/test_hook_rules.py` and the wheel CI workflow. The planner read the two affected assertion blocks to check the report, then passed the locations to the implementer. The source-tree fallback test asserts `str(kit_root())` in the message and a filesystem path derived from it; an installed-package regression must exercise the resource representation that the source test lacks.

The scout reported three shell tool calls and no source-file exploration. These are self-reported activity counts, not measured API calls or savings. Some full test method names requested in the handoff were absent from the returned report; the planner recovered them while reading the located assertions. Future location handoffs should include exact symbols with line references so the receiver can run the intended tests directly.

The implementer's R-002 feedback reports that its source-only fallback assertion discovery preceded the scout handoff. That portion overlapped existing work. The implementer subsequently reused the long-path test and wheel-CI locations without another broad search. No additional scout or independent verifier was used. The planner also checked the cited CI block. This establishes specific reuse and overlap, not time or cost savings.

For subsequent delegation, agree on the still-unsearched portion before starting parallel discovery, and include executable test identifiers in the returned locations. The owner added subagent evaluation after this implementation had begun, which contributed to overlap. Existing delegation guidance already requires separated ownership and useful handoffs, so this observation calls for applying those instructions more precisely rather than adding another standing rule. Keep measured automated timings separate from unmeasured active work and waiting.

## Delivery and remaining scope

The retained delivery receipt identifies commit `8c4cd7e`, matching snapshot `264db64`, and full run `.awkit/reviews/review-ty9je3hh`: 308 tests with five skips. All seventeen jobs passed in [CI run 39931659200](https://github.com/min-seokkim/agent-work-kit/actions/runs/39931659200). The receipt also records exact installation/content comparisons and four installed CLI cases with readable references after exit. These results are under `.awkit/handoffs/document-feedback-implementation/delivery/validation.json`. The task's earlier pending-delivery wording was stale and is corrected here.

Continue receiving technical feedback without taking over application drafting. Existing malformed rules require a separate scoped repair. Broader archive-install support, native automatic-hook execution and quantitative delegation productivity remain unverified.

## Existing-project update follow-up

At installed commit `b273d95`, the owner asked whether reinstalling awkit also updates every connected project. The platform installer replaces the shared package and regenerates user skills, but does not visit projects to rewrite their rules, check configuration, copied guides or project skills. An active session's previously read instructions are not evidence of a reload. The [writing-outcome delivery](writing-outcome-evaluation.md#delivery) verifies the new shared files separately.

Authorized read-only inspection found that the application still had its old `MultiplexedPath(...)` kit value in `rules.toml`, without a copied kit or project skills. The current rule loader uses that configured string. `doctor` identified the installed commit and matching version but emitted no rules-path finding. No project file was repaired, and this inspection did not run an automatic client hook. Generalized technical evidence is under `.awkit/handoffs/writing-outcome-evaluation/project-update-observation.json`.

`M-072` assigned bounded preparation, returned in `R-041`. Seven invented projects showed explicit guide-message use, implicit failure-reference use, a valid project-relative kit, an unused stale setting, and separate TOML, rule-validation and decoding failures. Doctor reported no rules finding in those cases and preserved file bytes/mtime without creating runtime state. Later controlled, command-free hook invocations confirmed emitted references and loader problems; these were not native client executions. Local evidence is under `.awkit/handoffs/project-rules-diagnostic-preparation/`.

Planning accepted the contract in `M-075` and assigned four files: `src/awkit/doctor.py`, `tests/test_doctor.py`, the existing reference explanation and CHANGELOG. Reuse rule validation; report invalid input separately from path readiness. For valid rules, inspect the configured/default literal directory when an effective message/command expansion or failure citation consumes it. Resolve relative paths from the selected project root, preserve inspection errors as unavailable, and leave unused settings alone. Existing directories do not establish individual guide availability, freshness or client loading. Preserve finding fields, nonfatal warnings and read-only behavior.

Keep custom rules, copied records and hook commands unchanged. Detecting a stale generated value does not authorize replacing it or establish a migration of every project. Existing project repair remains a separate scoped action; automatic migration and new project registries are unassigned. Implementation ownership excludes this task record and application files.

During working-candidate review, planning reproduced a consistency defect with controlled successive reads of two individually valid fictional rule documents. The diagnostic parsed one version and validated another, then raised an exception while matching their rules. This was a controlled input change, not an observed concurrent edit in the application. `M-076` authorized a narrow shared validation helper in `src/awkit/hooks.py` so diagnosis can use one captured input without changing hook evaluation. The original passing candidate and the new regression's expected failure remain retained.

Planning also clarified both READMEs' existing update paragraph: shared installation and managed user skills update, while project settings, hooks, copied guides and project-local skills remain intact. Active agents may need to reread the updated guides. This explains existing installer behavior and does not add migration or establish that every project uses the shared installation.

## Diagnostic candidate acceptance

`R-043` returned five-file snapshot `ae59426`. Frozen run `.awkit/reviews/review-y05d0027` passed Ruff, 73 focused tests without skips, writing checks and the seven retained CLI cases. Used legacy paths, including implicit failure references, now warn; a valid relative directory is present; an unused setting produces no path finding. Invalid input produces a rules warning without a path-readiness claim. Original rules bytes/mtime and controlled hook output stayed unchanged, and doctor created no runtime state. The helper extraction preserves the existing loader's validation and public behavior.

The regression also covers equal-length changed rules that previously produced a false directory finding. Separate test-edit errors, a duplicated test and its accidental over-removal, were caught and corrected; their evidence is retained in `implementation/double-read-findings.md` under the preparation folder. The final frozen suite includes exactly one regression exercising both counterexamples. No real permissions change or native client hook was used.

Planning read the exact diff, helper, regressions, retained failures and before/after results, compared the working files with the snapshot, and inspected the changed reference and CHANGELOG rendered in Edge. `M-078` accepted this candidate for cumulative integration with the [snapshot recipe](snapshot-path-recipe.md); full repository verification, CI and exact installation were pending at that stage. Delivery is recorded below. Neither focused checks nor directory presence establish repaired project settings, actual guide loading or improved writing.

Planning then ran a read-only source invocation against the authorized application project. The changed source files matched the accepted snapshot before and after the call. It reported valid rules with execution unverified and a directory-inspection warning for the preserved malformed value; rules bytes and mtime stayed unchanged. This was candidate source, not an installed CLI or native client hook. The metadata-only receipt is `.awkit/handoffs/project-update-delivery/application-source-observation.json`; no project repair or editorial work occurred.

## Windows CI path identity and delivery ownership

The first cumulative snapshot `5fe139f` passed Ruff and 360 local tests with seven skips in `.awkit/reviews/review-to19108v`. Commit `335270b` reached `dev`, but [CI run 40068654398](https://github.com/min-seokkim/agent-work-kit/actions/runs/40068654398) failed on Windows Python 3.11–3.14. All four failures compared the temporary path's `RUNNER~1` spelling against the same directory reported through `runneradmin`; the directory finding was `ok`. The original CI report and logs remain in `.awkit/handoffs/project-update-delivery/`. No installation update occurred after that failed CI; the shared installation remained `b273d95`.

The repair changes the CLI test to compare the reported directory with the expected project-root directory using `Path.samefile`. The CLI still starts from a subfolder, requires directory presence, preserves rules bytes/mtime, creates no runtime state and preserves nonfatal warning behavior. The eight affected diagnostics tests pass locally. This is a test assertion correction, without a product behavior change or an additional CHANGELOG entry. Windows CI must verify the alias-path case; the local interpreter does not reproduce the runner account's spelling.

Under `M-081`, implementation owns code review, test fixes, full checks, normal owner-authored delivery, all Windows/Linux CI results and exact-commit installation/content comparisons. Planning supplies outcomes and bounded requirements rather than routine code acceptance. The current execution stage and retained verification/installation receipts are in `.awkit/handoffs/project-update-delivery/validation.json`. Failed CI evidence remains separate from later passes. Project settings remain unrepaired; diagnostic visibility establishes neither actual guide loading nor writing improvement.

## Reported delivery and product consequence

`R-048` and the final execution receipt report delivery at `2d41ba1`: frozen snapshot `d30386f` passed Ruff and 360 tests with seven skips, and all seventeen Windows/Linux jobs passed in [CI run 40069950544](https://github.com/min-seokkim/agent-work-kit/actions/runs/40069950544). The exact-commit platform installation matched 26 source files, 29 kit files and sixteen managed user-skill payloads with recorded line-ending normalization. Three installed CLI fixture cases covered malformed consumed paths, a valid relative directory and invalid TOML without changing fixture files. Planning records this implementation evidence without repeating its code review or checks.

Rendered inspection of the two repair task-record edits was unperformed because the browser refused the local file URL; the receipt retains that limit. The original failed CI remains separately recorded. Later planning edits have no coverage from this delivered snapshot. No application project was repaired or inspected during this delivery.

The diagnostic makes a connection problem visible. Restoring the selected project's intended connection remains a separate product outcome; shared installation does not establish it.

## Selected-project repair proposal

Status: M-095 completed in R-055 with an isolated repair using existing capabilities. The product disposition below retains the existing procedure; this case does not justify a helper. No real application-project repair is assigned.

The intended flow is to inspect one explicitly selected project, identify the consumed broken reference, choose its intended available guide source, show the proposed change, and apply it within the task's authorization. Preserve custom rules, commands, comments, checks and record locations. An old setting can be valid and intentional. General project discovery and unattended migration are outside the first unit.

Use an invented project with a malformed legacy kit value and a custom rule/comment, plus a valid project-relative directory as a control. The broken reference should become usable while the control stays unchanged. If inputs change after planning, recalculate the proposal before applying it. Retain a reversible before/after record; restoration must preserve later unrelated edits or report a conflict. Check whether the selected replacement survives a subsequent shared package update rather than assuming that any absolute installed path is durable.

Existing init, hooks and skills commands may already supply the required operation after the source is selected. An ordinary agent edit may suffice for one malformed value. Promote a helper only when a repeated, mechanically identifiable operation remains that existing commands do not safely provide. Use known installation provenance; missing provenance does not establish ownership of matching files.

Keep three results distinct: updated shared files, repaired project settings, and observed guide or hook use. Controlled invocations establish their tested behavior; native client execution and active-context reload require separate observations. Neither a synthetic repair nor a passing diagnostic establishes better writing or fewer user reminders. The application's technical-feedback authorization does not assign its repair.

M-095 requires executing the proposed repair in an isolated fixture that explicitly intends to use shared installed guides. Its valid local-guide control must remain unchanged; unrelated edits after planning must survive, and malformed/unreadable input must stay unresolved. Use existing capabilities and inert invocations, retaining actual before/repair/after output. An isolated package refresh should identify the exact tested revision/location transition; a same-artifact reinstall does not prove all future upgrades. No real project, shared runtime or tracked product file is changed by the trial. Evidence belongs in `.awkit/handoffs/project-repair-trial/`.

## Repair trial product disposition

Existing capabilities restored the fixture's guide access. R-055 reports a targeted edit from the broken file reference to `awkit kit guide writing`; the planner read the retained before/after hook output and the printed guide opening. A separate absolute-directory alternative also restored a readable reference. The command-reference route already exists in the shipped guide documentation, so this observation adds no new product requirement.

The message edit leaves the legacy kit value unused, not repaired. A rule that still expands `{kit}` or supplies implicit failure citations needs a valid directory. Preserve that distinction when choosing a repair: a readable message alone does not establish a healthy configuration for every consumer.

The executor reports preservation of custom rules/comments, checks and task records, unrelated edits made after the proposal, and the intentional local-guide control. Field-only restoration retained later edits and refused a conflicting target. Malformed TOML and a non-file input remained unresolved. The isolated A reinstall and B location selection used the same `2d41ba1` artifact; they establish neither a different-version upgrade nor automatic interpreter selection. Native client execution, active-context reload and real-project repair remain unverified.

Retain the scoped edit procedure and reopen a helper proposal only for an observed operation that this route cannot serve. No general updater or migration is assigned. Evidence is in `.awkit/handoffs/project-repair-trial/report.md`, `results.json` and the retained command outputs. Planning assessed the user journey and limits; implementation owns its execution assertions. This trial does not measure fewer reminders, saved time or writing quality.
