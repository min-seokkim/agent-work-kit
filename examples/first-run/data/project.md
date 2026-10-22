# Project Profile: data example

A filled-in minimal profile for this example. Copy the shape for your own data task and extend it with the sections of the kit's project profile template when needed.

## Start here

- Desired result: `output/summary.csv` with one row per item giving total quantity and total amount, computed from `input/orders.csv`.
- Source material: `input/orders.csv` in this folder. The file is small enough to retain as a whole.
- Files to change and conditions to preserve: fix column names in `input/orders.csv` only; keep every order row and its values.
- How completion is checked: `awkit review check <commit> --config checks.toml --runs-root .awkit/reviews` returns `passed`; `check_output.py` recomputes the totals from the input.
- Where results go: the run folder under `.awkit/reviews/` holds the checked input and output with hashes.

## Working environment

- Project language and target runtime: CSV processed with the Python that runs awkit; standard library only.
- Focused check commands: `python process.py input/orders.csv output/summary.csv`, then `python check_output.py input/orders.csv output/summary.csv`
- Resources to isolate: none; the scripts read and write files in the working directory only.
