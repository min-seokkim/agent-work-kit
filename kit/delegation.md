# Agent Delegation and Model Use

The main agent reads this guide before splitting work, delegating to subagents, or selecting models. Projects that do not delegate can use the kit without it; do not preload it every session. Subagents follow their [role template](templates/roles/README.md) and handoff instead. Record project-specific settings under "Delegation and models" in the [project profile](templates/project.md).

## 1. Objective

Reduce the credits required to complete the user's requested outcome while maintaining the quality gates. Call count, concurrency and model tier are not measures of success. Measure cost per completed task, including corrections and revalidation, rather than per call.

The numbers in this guide are starting values, not measured optima. The handoff limits in section 5 come from 55 handoffs in one project; the concurrency, scouting and premium-call limits are unmeasured defaults. Change them in the project profile when your own records (section 8) disagree.

## 2. When to delegate

Delegate only when one of these conditions holds:

- Independent reading can be split to conserve the main agent's context.
- Write ownership can be separated without overlap, and each result can be verified independently.
- A separate judgment is needed to deliver the requested outcome or prevent a serious regression.

The main agent handles short document edits, straightforward changes within one file, sequential lookups, and tasks whose evidence it has already read. If it needs to read several files outside its assigned ownership (three or more by default), first use a scout to locate the relevant material. Do not delegate when briefing and integration would cost more than doing the work directly.

Run at most three independent reading tasks concurrently. Delegate implementation sequentially when shared decisions remain, even if files do not overlap. Interface shape, naming and error handling are examples: concurrent subagents cannot see each other's decisions. Before parallel implementation, settle the shared decisions and put the same wording in every handoff.

## 3. Risk and premium calls

Classify risk by the consequences of failure, not the number of files.

| Risk | Criteria | Default execution |
|---|---|---|
| `low` | Typos, wording, straightforward configuration, reversible local changes | Main agent directly; efficient-tier exploration only when useful |
| `normal` | Ordinary code, tests or documentation with clear rules | Standard-tier builder; main agent integrates and verifies |
| `high` | Permissions, state transitions, concurrent changes, migrations, money, personal data, publication or deployment settings | One premium judgment plus relevant verification |

Record project-specific examples of `high` risk in the project profile.

Manage judge-tier and higher calls through one `premium_slot` per task: `none`, `upfront` or `final`. Use `upfront` before implementation when invariants or design are unclear. Use `final` after implementation when the specification is clear but accumulated changes carry risk. After using `upfront`, the main agent checks its acceptance criteria and tests before committing; do not add a separate `final` by default.

A second premium call is allowed only when:

- High or Major findings remain unresolved.
- Relevant tests fail.
- New scope or decisions arise, or evidence conflicts.
- The first call fails to execute.

The main agent records the reason. Even under these conditions, premium calls are capped at three per task, adjustable in the project profile. At the cap, pass unresolved High and Major findings to the user as `decision-needed`. This prevents an endless review loop in which every correction produces a new finding.

## 4. Roles and execution paths

| Role | Tier | Access | Responsibility | Exclusions |
|---|---|---|---|---|
| `scout` | `efficient` | Read | Locate assigned paths, call relationships, related tests and supplied URLs | Security or design judgments, proposed solutions |
| `analyst` | `judge` | Read | Assess rule conflicts, impact, invariants and acceptance criteria before implementation (`upfront`) | Unapproved constraints or procedures |
| `builder` | `standard` | Write | Implement features or fix confirmed defects within assigned files; run focused tests | New business decisions, reverting others' changes, commits |
| `verifier` | `judge` | Read | Independently examine diffs, code, tests and supplied screenshots (`final`) | File edits or scope expansion |
| `writer` | `standard` | Write | Draft or revise assigned documents using verified facts and a fact-check record | New research, overstated implementation, new conclusions |

Subagents do not delegate further. Only the main agent makes additional calls. When designs across modules conflict or the same issue causes two content failures, call an analyst once at the top tier. Occasional work such as checking record consistency or editing reports stays with the main agent or goes to a builder or writer with a specific handoff.

| Situation | Execution path |
|---|---|
| `low`, or the main agent has already read all evidence | Main agent, then necessary automated checks |
| Clear `normal` implementation | Builder, main-agent diff review, relevant tests and one full run if needed |
| `high` with unclear rules | Analyst `upfront`, builder or main-agent implementation, main-agent integration and verification |
| Broad `high` change with clear rules | Split builder work, one verifier `final`, necessary fixes, main-agent verification |
| Two failures or a design conflict | One top-tier analyst call, then only the remaining fixes by the main agent or a new builder |
| New document or major rewrite | Writer draft and fact-check record, main-agent fact check, verifier if needed |

If a change only addresses findings and adds no behavior or scope, the main agent can finish by inspecting the diff. For a sequence of commits, inspect the cumulative diff before the final commit. If the user has opened an independent review session, its `final` fills `premium_slot = final`; follow [Review Session Collaboration](review-session.md).

## 5. Handoffs and results

Use the four sections of the [task handoff](templates/task.md) in this order: goal, output, tools and evidence, scope. Start with the limits below and adjust them in the project profile after measuring actual handoffs. These starting values came from measuring 55 handoffs in one project and comparing two output instructions.

| Item | Starting limit |
|---|---|
| Exploration handoff | 2KB, including evidence |
| Implementation or judgment handoff | 5KB |
| Result | 30 lines; put larger tables or reproduction material in a temporary file of at most 8KB and return its path |

Do not send the entire repository, raw logs, completed exploration results or the full conversation. Exclude credentials, environment variables and sensitive information. Narrow large inputs with searches and targeted reads.

Start the result with one of the following statuses. Then list files examined, checks run and conclusions. Separate anything that remains unverified.

| Status | Meaning | Main-agent action |
|---|---|---|
| `DONE` | All acceptance criteria were checked. | Read the diff and directly affected callers, then integrate. |
| `DONE_WITH_CONCERNS` | Work is complete, with residual concerns. | Decide whether to accept or address the concerns. |
| `NEEDS_CONTEXT` | Required evidence or decisions were missing from the handoff. | Supply what is missing and continue once in the same thread. |
| `BLOCKED` | Work cannot proceed within the current scope or permissions. | Split the task, revise the plan, raise the tier or take over. |

Do not call another subagent at the same tier with an unchanged handoff. Change something first.

## 6. Failures and retries

The main agent handles failures involving executables, permissions, dependencies, networks or DB connections as execution failures, not reasoning failures. For incorrect content, narrow the evidence and remaining issue, then allow one correction in the same thread. If it fails again, stop calling; the main agent takes over or calls a top-tier analyst once under the conditions in section 4. Minor findings, stylistic opinions and a review with no findings do not justify another call.

Switch providers only for temporary issues such as usage limits or connectivity. Do not switch providers to evade a security refusal, content failure or failed verification.

Builders run focused tests. The main agent runs the full suite once after integration and repeats it only for new changes or failures.

## 7. Model tiers

| Tier | Use |
|---|---|
| `efficient` | Independent exploration, supplied URL checks, locating relevant sections and patterns in large inputs |
| `standard` | Ordinary implementation and tests, document drafts, status checks |
| `judge` | Rule, security, permission, concurrency and deliverable judgments assigned through `premium_slot` |
| `top` | User-requested use, or high-risk root-cause analysis after a judge-tier correction also fails |

Map tiers to actual models for each provider in the project profile. These are operational categories, not claims of equivalent performance. With `awkit kit roles`, Claude Code roles receive tier defaults; Codex roles receive models for the tiers explicitly configured. See [Role Templates](templates/roles/README.md) for provider-specific behavior.

Confirm the actual model from execution logs rather than a subagent's self-report or configuration alone. Check actual permissions as well: restrictions in role files may not be enforced by the provider. `awkit usage` collects models and tokens from execution logs.

## 8. Measurement

Record the following per task in the session record. Mark unavailable values as `unverified`.

- Risk and `premium_slot`; the reason for a second premium call.
- Roles invoked, actual models and reasoning effort, calls and retries.
- Fresh input, cache-write, cache-read and output tokens; credits when available.
- Wall-clock minutes and the number of messages the user had to send after the first instruction (`awkit usage` reports both per thread).
- High and Major findings, who found each one and at which stage, and defects found after acceptance.

Evaluate delegation against main-agent-only execution on comparable tasks. Alternate similar tasks between the approaches rather than doing the same work twice. Keep any claimed advantage `unverified` until there are at least three tasks per approach. Compare quality in this order: the proportion of tasks with High or Major findings, the proportion with significant defects discovered after acceptance, and corrections per task. Improvement in a later measure does not offset deterioration in an earlier one. If a defect appears later, reopen the measurement and include its correction cost.

Keep this guide and the role files short. Put examples, measurement history and prices in session records. Before adding a rule for a recurring failure, check whether an existing rule already covers it.
