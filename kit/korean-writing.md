# Korean Writing Guide

Use this guide when writing or reviewing Korean project text for people. It covers new documents, partial edits, full rewrites, UI text, CLI output, notifications, handoffs, session records, and commit and PR descriptions. Preserve code identifiers and machine-readable formats. The instructions here are in English; Korean wording examples remain in Korean.

Projects that adopt this guide use the following process by default. Current user instructions and established project terminology take precedence. Record project-specific terminology and audiences in the [project profile](templates/project.md), rather than duplicating these rules across documents.

## Writing process

Before writing, identify the audience, what readers should understand or do, and the document's purpose. User guides focus on actions and expected results; operational guides focus on execution and recovery.

1. **List what must be preserved.** Separate facts, decisions, states, conditions and prohibitions. Include numbers, dates, IDs, commands, quotations, links and heading anchors.
2. **Write an actual English draft.** Explain the actions and outcomes the reader needs. Do not substitute a literal rendering of Korean sentence structure or a list of facts for the draft.
3. **Rewrite the meaning in natural Korean.** Do not copy English subjects and word order or translate word by word. Preserve technical terms and turn abstract noun chains into descriptions of actions.
4. **Review facts, sentences and overall flow in sequence.** Each review has a distinct purpose, described below.

For a partial edit, draft only the changed passage and affected content. For a full rewrite, draft the entire document in English. The three reviews do not mean rewriting the whole document three times.

| Review | What to check |
|---|---|
| Facts | Compare against the preservation list and source. For implementation claims, also inspect the relevant code and check results. |
| Korean sentences | Read the Korean on its own. Correct unnatural word order, translation artifacts, repetition and ambiguous references. |
| Overall flow | Check whether readers can find and understand what they need. Review paragraph order, duplication, terminology, contents and links. |

Do not use style scores, comma counts or sentence lengths as acceptance criteria. Link and rendering checks find technical errors; they do not replace a readability judgment.

## Preserve facts and judgments

Distinguish plans, approved decisions, implementation, check results and actual operation. Completing implementation does not establish verification or operational use. Leave unverified figures and states marked as unverified.

When editing style, preserve facts, proper names, numbers, dates, IDs, code identifiers, commands and quotations. Do not claim that unread material lacks evidence. Do not add certainty, restrictions, risks or priorities absent from the source. Do not turn possibility into certainty or permission into an obligation while shortening a sentence.

For numbers, pricing assumptions and external capabilities, retain the source and verification date. A style-only edit must not imply fresh fact-checking. Check incoming links when changing heading anchors.

## Tone and terminology

Use `-습니다` for explanations to people and `-하세요` for action instructions. Shared human-and-agent documents also use polite Korean. Korean instructions exclusively for agents may retain `-다`. Preserve completed historical records, code and quotations as written.

Do not mix `-하세요`, `-하십시오` and `-하시오` within one guide. Short noun phrases are appropriate in headings and tables. Use one name for each concept and match the project's established UI terminology.

Reduce unnecessary English glosses, while preserving Python, JSON, API, commit and exact code identifiers. Use role names verified for the project; do not import another project's business roles or terminology as universal rules. This toolkit uses `모의` for mock material and `다운로드` for downloading files.

## Revise sentences

State the conclusion first, then give evidence and necessary explanation. Make one claim per sentence and let the next sentence develop it. Review sentence length and endings without forcing a fixed character count or repetition quota.

**Describe actions.** Say what is displayed, stored, sent or checked. Do not rely repeatedly on vague verbs such as `제공한다` or `보여준다`. Procedures must make the responsible actor clear.

**Separate results for distinct subjects.** Do not bundle subjects with different states under an `A와 B` label. Replacing the conjunction with a slash or middle dot is not enough: state each result or explain the relationship.

**Turn noun chains into actions.** Instead of `의존성 추가 시 이유와 영향 기록`, explain why existing tools are insufficient and how the dependency affects maintenance. When words such as `경계`, `기반` or `정합성` hide several meanings, state who may do what or which values must agree. Preserve precise technical terms where appropriate.

**Remove translation artifacts and stock phrases.** Avoid repeated `~에 있어서`, `가지고 있다`, double passives and abstract nouns. Replace evaluations such as `혁신적`, `주목할 만하다` or `시사하는 바가 크다` with verified results. Do not mechanically add `첫째`, `둘째`, `또한`, `나아가` or the pattern `A가 아니라 B`.

**Explain relationships compressed into symbols.** Expand slash- or arrow-separated conditions into sentences that clarify order and conditions. Reduce unnecessary English glosses, decorative emphasis and quotation marks. Preserve code and fixed notation.

Use paragraphs for connected explanations, lists for parallel items or steps, and tables for items assessed on the same criteria. Do not force equal heading lengths or add promotional language.

## Document purpose and records

Authoritative documents explain decisions, reasons for changes and current behavior directly. Do not repeat conversational history throughout the text. Keep request and approval provenance in the relevant evidence or session record when needed.

Maintain one authoritative document per topic and link to it elsewhere. Preserve historical records without also maintaining them as duplicate current procedures. Do not add formulaic warnings or disclaimers unrelated to the document's purpose.

## Rewriting and collaboration

If a text has been revised more than twice, or has accumulated dated additions and repetition, reconsider its structure. Make a preservation list, draft from a blank document and compare with the source. Keep the prior content recoverable.

A review comment identifies the passage, problem and corrective direction. After a fix, check that passage and affected content rather than repeatedly scoring resolved issues. When reviews conflict or a problem recurs, the main agent determines the cause and direction. Do not replace established terms to suit a reviewer's taste.

For a full rewrite, prepare a fact-check record and obtain one independent review through the project's authorized collaboration process. This guide itself does not authorize agent calls or data transfers. Do not add approval steps for routine editing decisions. Ask the user about unsettled policy or choices that change meaning.

Before splitting work among writers, the main agent completes one representative document or section. Each handoff includes audience, purpose, preservation requirements, authoritative sources, English and Korean drafts, and the fact-check record. Keep file ownership separate; the main agent performs final editing.

After interruption, reuse completed drafts and reviews. If another session is editing a document, work in a separate draft and compare with the latest source before applying it. Avoid accumulating temporary drafts and fact-check records as competing copies of current documents.

## Completion check

- Does every major claim have evidence, with plans, implementation, verification and operational state distinguished?
- Are numbers, dates, proper names, IDs, commands, quotations and degrees of certainty preserved?
- Are tone and terminology consistent, with actors and subjects clear?
- Have translation artifacts, exaggeration, mechanical transitions and unnecessary decoration been removed?
- Can readers find what they need, with duplication and links resolved?

The main agent reads the final text itself and removes remaining awkward wording and repetition before delivery.

## Style reference

The style reference is the `humanize-korean` skill from `epoko77-ai/im-not-ai`. This guide is not a copy of that skill's distribution or complete rule set.
