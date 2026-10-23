# Installed guide paths

Status: implementation accepted at `17401d1346315130fdcb5fc3f0cf391e968a5049`; cumulative delivery is tracked in the receipt below. Base: `aca1ab9512159ec291e4eef50c71b2e72bb2cb7f`. The planner owns development feedback, scope and this record. The existing implementation session owns the assigned source, tests, CHANGELOG and generated guard mapping. Channel `.awkit/document-feedback-implementation.sqlite3` uses main for the planner and reviewer for the implementer; this is informed collaboration, not independent review. M-001 assigns the correction; R-002 returns its candidate.

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

## Next action

Complete cumulative delivery after planner record and rendered-output review. Continue receiving technical feedback from the application project without requesting document work or treating its paused writing task as permission to resume. Existing malformed rules require that project's separate repair decision. Broader archive-install support, native automatic-hook execution and quantitative delegation productivity remain unverified.
