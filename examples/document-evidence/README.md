# Document review evidence example

A fictional cache decision note shows what recorded review coverage can establish. Requirements and four measurements were fixed before writing the note. The shipped evidence includes actual Windows Edge captures and executor self-review; it establishes neither intended-reader acceptance nor writing quality.

From this directory, with awkit installed:

```sh
python preview.py check
python check_evidence.py --json
snap=$(awkit review snapshot .gitattributes README.md requirements.json note.md inputs/source-facts.md inputs/measurements.csv inputs/unrelated-source.md styles/shared.css preview.py check_evidence.py checks.toml evidence/preview.html evidence/preview.json evidence/render.json evidence/review.json evidence/wide.png evidence/narrow.png)
awkit review check "$snap" --config checks.toml
awkit review verify <run_dir>
```

In PowerShell, use `$snap = awkit review snapshot ...`. The runner retains required files and hashes, including failed checks. `verify` checks retained bytes, while this example checks the declared input/output links.

To revise the note, run `python preview.py build`. This updates HTML and generation metadata only. Capture full-page images at the two viewports in `requirements.json`, record the actual renderer/version and font conditions in `evidence/render.json`, then read the sources and inspect both captures before updating `evidence/review.json`. The existing records show the schema. Obtain current duty hashes with:

```sh
python -c "import check_evidence as c, preview, json; print(json.dumps({k: preview.identities(preview.root_path(), v) for k, v in c.DUTIES.items()}, indent=2))"
```

Hashes never create performed review declarations. Record unavailable work with its reason; missing, unavailable and stale evidence refuse a pass. Preserve failed runs before correcting them. CSS changes invalidate rendered coverage; unrelated-source changes do not invalidate this note. Record source reading and preservation separately from rendered inspection and author approval.

From the repository root, the focused test is `PYTHONPATH=src python -m unittest discover -s tests -p test_document_evidence.py`. Its constructed records are explicitly simulated and refused by normal execution. This optional repository example adds no mandatory workflow or package support.
