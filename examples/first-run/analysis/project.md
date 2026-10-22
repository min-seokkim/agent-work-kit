# Project Profile: analysis example

A filled-in minimal profile for this example. Copy the shape for your own analysis and extend it with the sections of the kit's project profile template when needed.

## Start here

- Desired result: `output/report.json` giving the peak acceleration from `input/readings.csv`, with observed values, assumptions, computed values and interpretation kept apart.
- Source material and its version: `input/readings.csv` and `assumptions.toml` in this folder; both are retained with hashes by the check.
- Files to change and conditions to preserve: correct `assumptions.toml` only; keep every reading and the assumption sources.
- How completion is checked: `awkit review check <commit> --config checks.toml --runs-root .awkit/reviews` returns `passed`; `check_report.py` recomputes the peak from the input.
- Where results and records go: the run folder under `.awkit/reviews/`; an accepted run is kept with `awkit review accept`.

## Working environment

- Project language and target runtime: CSV and TOML processed with the Python that runs awkit; standard library only.
- Focused check commands: `python analyze.py input/readings.csv assumptions.toml output/report.json`, then `python check_report.py input/readings.csv assumptions.toml output/report.json`
- Interpretation: written by a person into `interpretation` with `interpretation_status` set to `reviewed`; the check rejects an interpretation that is present but not reviewed.
