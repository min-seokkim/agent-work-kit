# Korean Writing Guide

Use this guide with the [Writing Guide](writing.md) when writing or reviewing Korean text for people: documents, UI text, CLI output, notifications, handoffs, and commit and PR descriptions. The Writing Guide covers the reader, the preservation list, plain style, corrections and the completion check; this guide adds what is specific to Korean. Preserve code identifiers and machine-readable formats. The instructions are in English; Korean wording examples remain in Korean. The two grades in the Writing Guide apply: a reply that stays in the conversation keeps the endings, the pattern list and Describe actions and is read once before sending; Korean that leaves the conversation follows the whole writing process below.

## Writing process

1. **Decide the reader and list what must be preserved,** as in the Writing Guide.
2. **Write an actual English draft** of the actions and outcomes the reader needs, not a literal rendering of Korean structure or a list of facts. For a partial edit, draft only the changed passage and affected content.
3. **Rewrite the meaning in natural Korean.** Do not copy English subjects and word order or translate word by word.
4. **Review three times, each for one purpose:** facts against the preservation list and source (for implementation claims, also the code and check results); the Korean read on its own, for word order, translation artifacts, repetition and unclear references; and the overall order, duplication, terms and links. This is not three full rewrites. Style scores, comma counts and sentence lengths are not acceptance criteria.

Prevents: F14, F33.

## Tone and terminology

Use `-습니다` for explanations to people and `-하세요` for action instructions, including documents people and agents share. Forms, slides and administrative reports often end items with nouns (`-함`, `-음`); follow the document's convention. Korean instructions only for agents may keep `-다`. Keep one style per text: do not mix `-하세요`, `-하십시오` and `-하시오`. Preserve historical records, code and quotations as written.

Use one name for each concept and match the project's UI terms and verified role names. Reduce unnecessary English glosses while keeping exact identifiers (Python, JSON, API, commit). Do not use italics, and do not join words with middle dots (`·`) where a sentence or list can say the relationship. This toolkit uses `모의` for mock material and `다운로드` for downloading files.

Prevents: F14.

## Revise sentences

Make one claim per sentence and let the next develop it.

**Describe actions.** Say what is displayed, stored, sent or checked, and by whom, instead of repeating vague verbs such as `제공한다` or `보여준다`. Give a program its actual operation, not a person's action: a hook does not `침묵한다`, `말한다` or `울린다`; it `출력하지 않는다`, `거부한다`, `한 줄을 넣는다` or `기록한다`.

**Separate distinct subjects.** Do not bundle subjects with different states under an `A와 B` label, and do not replace it with a slash, a middle dot or a uniform four-character name. State each result, or name what each category holds.

**Turn noun chains into actions.** Instead of `의존성 추가 시 이유와 영향 기록`, say why existing tools are insufficient and how the dependency affects maintenance. Words such as `경계`, `기반`, `정합성`, `정제`, `권위 순서` and `흐름` often hide several meanings; say who may do what or which values must agree.

**Remove translation artifacts and stock phrases.** Avoid repeated `~에 있어서`, `가지고 있다`, double passives and abstract nouns. Replace `혁신적`, `주목할 만하다` or `시사하는 바가 크다` with verified results. Do not mechanically add `첫째`, `또한`, `나아가` or `A가 아니라 B`. Expand slash- or arrow-separated conditions into sentences.

Before delivery, read the Korean on its own, without the English draft.

Prevents: F14, F31.

## Style reference

This guide adapts material from the `humanize-korean` skill in [epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai), with local revisions, additions and an English translation. The upstream copyright and full MIT license are preserved in [Third-party notices](THIRD_PARTY_NOTICES.md). Include that notice when redistributing the adapted guide.

Prevents: none (credit for the adapted material).
