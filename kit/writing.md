# Writing Guide

Use this guide when writing or revising text people read: documents, reports, UI text, CLI output, notifications, handoffs, and commit and PR descriptions. For Korean text, also follow the [Korean Writing Guide](korean-writing.md). Current user instructions and established project terminology take precedence. Record a project's audiences, terms and per-document requirements (length, endings, layout) in the [project profile](templates/project.md); a requirement given for one document does not apply to every document.

## Before writing

Decide these first, because text written for the wrong reader has to be rewritten rather than edited:

- **The kind of document and its reader.** A resume, a status report for stakeholders and a README need different content even from the same facts.
- **What the reader must understand, decide or do.** Include what serves that. Leave the rest out or link to it.
- **What must be preserved.** Facts, decisions, numbers, dates, IDs, commands, quotations, links and heading anchors; conditions, negations and the direction of each cause and effect; who did what; and whether each item is planned, decided, implemented, verified or in use.

Write from the reader's needs and use existing documents and the conversation only as sources of facts. A developer document reworded for stakeholders keeps the developer's structure, and the user's own words pasted in keep the conversation's framing. State decisions and their reasons directly instead of describing the conversation that produced them.

## Write plainly

State the conclusion first, then the evidence. Name who does what and what results. Explain or replace terms the reader does not know. Keep tracking codes (task IDs, commit IDs, decision-record numbers) in records for agents and out of text people read; readers cannot decode them.

Readers recognize these patterns as generated text, so remove them: contrasts against a claim nobody made ("not X but Y"), lead-ins ("here's"), closing lines that repeat the paragraph, slogans and promotional headlines, sales and consulting words, labels that repeat an entry's title, decorative bold, em dashes, and lists of what a project does not do. Keep dates out of current guidance and file names; they belong to historical records.

Shorten by removing repetition and wordy phrasing, never items on the preservation list. Dense text may run past one page.

The pattern list is for the agent's own prose. Leave a listed pattern alone inside a quotation, a title, a passage that discusses the pattern, or a writing sample the user gave to match. Applying the list mechanically produces its own pattern, the same clipped skeleton in every text, which readers recognize just as well.

Use paragraphs for connected explanation, lists for parallel items and steps, tables for items compared on the same criteria, and a figure or screenshot where it explains better than text.

## Preserve facts and judgments

Keep plans, approved decisions, implementation, check results and actual operation distinct; completing implementation does not establish verification or use. Keep unverified figures marked as unverified. Do not merge work from different projects or people, and do not turn possibility into certainty or permission into obligation while shortening.

When revising accepted text, keep its adopted wording, structure and design unless the task changes them, and compare the revision with the accepted version. A style edit must not imply fresh fact-checking. If a style edit changes more than about a third of the text, it has become a rewrite: stop and confirm the scope with the user before continuing. For numbers, prices and external capabilities, keep the source and the date it was checked. Check incoming links when changing heading anchors.

## Corrections

When the user corrects text, identify the reader's problem behind the correction and check the fix against that problem. Changing only the named words recreates the problem in another form.

Then search every text people read (other documents, UI text, CLI output) for the same pattern and fix each occurrence, or list those left and why. The user should not have to point at each one.

## Rewriting and collaboration

If a text has been revised more than twice, or has accumulated additions and repetition, reconsider its structure: make a preservation list, draft from a blank document, compare with the source and keep the prior content recoverable. Maintain one authoritative document per topic and link to it; keep historical records without maintaining them as duplicate current procedures.

A review comment names the passage, the problem and the fix. After a fix, check that passage and the affected content instead of rescoring resolved issues. When reviews conflict, the main agent decides; established terms are not changed to suit a reviewer. A full rewrite gets one independent review where the project authorizes it. Before splitting writing among agents, finish one representative section and hand off the audience, purpose, preservation list, sources and drafts.

## Completion check

- The rendered output (line breaks, tables, page fit, links) was inspected, not only the source text.
- Every item on the preservation list is in the text, with plans, implementation, verification and use distinguished.
- The patterns above were searched for in everything changed.
- Endings, terms and actors are consistent.

Report what the final text is and what was checked; following these steps does not show that it reads well. The main agent reads the final text before delivery.
