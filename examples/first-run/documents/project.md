# Project Profile: documents example

A filled-in minimal profile for this example. Copy the shape for your own document folder and extend it with the sections of the kit's project profile template when a task needs them.

## Start here

- Desired result: the three documents under `docs/` link only to files that exist, each starts with a title, and the checked set is retained with hashes.
- Source material: `docs/*.md` in this folder; no external sources.
- Files to change and conditions to preserve: edit `docs/*.md` only; keep the headings, the command examples and the settings table as they are.
- How completion is checked: `awkit review check <commit> --config checks.toml --runs-root .awkit/reviews` returns `passed` and lists the documents under `artifacts`.
- Where results go: the run folder under `.awkit/reviews/`; the fixed documents are committed afterwards.

## Working environment

- Project language and target runtime: Markdown documents; checks run with the Python that runs awkit.
- Focused check commands: `python check_docs.py docs`
- Writing guide: the kit's Korean Writing Guide applies to every document under `docs/`.
