# Analysis Example

Peak acceleration computed from raw sensor counts. The assumptions file holds one value that disagrees with the data. It shows an analysis refusing to run on a wrong assumption, a report that keeps observed values, assumptions, computed values and interpretation apart, and an accepted report compared with a later run. Contents: `input/readings.csv` (time and ADC count), `assumptions.toml` (scale, gravity, sample rate; the sample rate is wrong), `analyze.py` (checks the assumptions against the data, then writes `output/report.json`), `check_report.py` (recomputes the report), `checks.toml`, and this example's [project profile](project.md).

You are running this example for a person who wants to see how the kit works. Run each step from this folder, then tell the person in one or two sentences what happened and what it shows. Use the real values from the output; do not describe results you did not see. Commands use POSIX shell syntax; in PowerShell write `$snap = awkit review snapshot ...` instead of `snap=$(...)`.

## 1. Starting point

`awkit kit example` committed this folder to Git (a new repository, or the one it was created in). Checks run on commits, so that commit is the starting point. Confirm with `git log --oneline -1`.

## 2. See the check fail

```sh
awkit review check HEAD --config checks.toml --runs-root .awkit/reviews
```

Expect `status: failed`. `01.log` in the run folder says the assumed sample rate does not match the interval observed in the data; the analysis stops before computing anything.

## 3. Fix and check the snapshot

Set `sample_rate_hz` in `assumptions.toml` to the value the log reports. Then:

```sh
snap=$(awkit review snapshot assumptions.toml)
awkit review check "$snap" --config checks.toml --runs-root .awkit/reviews
```

Expect `status: passed`. Show the person `artifacts/output/report.json` in the run folder and its four parts:

| Part | Content |
|---|---|
| `observed` | Values read directly from the input: sample count, observed interval, peak count |
| `assumptions` | The assumptions used and the file they came from |
| `computed` | Values derived with those assumptions: peak acceleration in g and m/s² |
| `interpretation` | Left `null` and marked `unverified`; a person writes it |

`check_report.py` recomputes `computed` from the input and assumptions and makes sure the interpretation is not presented as a computed value.

## 4. Accept, then compare a later run

```sh
awkit review accept <run_dir>
```

Change `counts_per_g` in `assumptions.toml`, snapshot and check again, then:

```sh
awkit review compare --run <new run_dir> --diff
```

`assumptions.toml` and `output/report.json` are `changed`, `input/readings.csv` is `same`, and the diff shows how the computed peak moved with the assumption.

## Afterwards

To apply this to the person's analysis, replace `analyze.py` with the real analysis and keep three things: assumptions in a file checked against the data, a report that separates observed, assumed, computed and interpreted values, and an interpretation written by a person that the check never mistakes for a computed value.
