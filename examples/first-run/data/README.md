# Data Example

Order data summarised per item, with one deliberately wrong column name in the input. It shows a processing step failing on bad input, the fix checked on a snapshot, the input and output retained together with hashes, and an accepted result compared with a later run. Contents: `input/orders.csv` (`quantity` is misspelled as `qty`), `process.py` (writes `output/summary.csv`), `check_output.py` (recomputes the totals from the input), `checks.toml` (runs `process.py` as setup and `check_output.py` as the check, retaining input and output), and this example's [project profile](project.md).

You are running this example for a person who wants to see how the kit works. Run each step from this folder, then tell the person in one or two sentences what happened and what it shows. Use the real values from the output; do not describe results you did not see. Commands use POSIX shell syntax; in PowerShell write `$snap = awkit review snapshot ...` instead of `snap=$(...)`.

## 1. Starting point

`awkit kit example` committed this folder to Git (a new repository, or the one it was created in). Checks run on commits, so that commit is the starting point. Confirm with `git log --oneline -1`.

## 2. See the check fail

```sh
awkit review check HEAD --config checks.toml --runs-root .awkit/reviews
```

Expect `status: failed`. The setup step `process` failed, so the check did not run, and `missing_artifacts` lists `output/summary.csv`. `01.log` in the run folder names the missing column.

## 3. Fix and check the snapshot

In the first line of `input/orders.csv`, change `qty` to `quantity`. Then:

```sh
snap=$(awkit review snapshot input/orders.csv)
awkit review check "$snap" --config checks.toml --runs-root .awkit/reviews
```

Expect `status: passed`, with `input/orders.csv` and `output/summary.csv` under `artifacts`. The summary was produced in the check's worktree, so it is in the run folder's `artifacts/`, not in this folder.

## 4. Verify the retained files

```sh
awkit review verify <run_dir>
```

Both files are `ok`. The same input checked again gives the same hashes, which is how an output is traced back to its input.

## 5. Accept, then compare a later run

```sh
awkit review accept <run_dir>
```

Change one quantity in `input/orders.csv`, snapshot and check again as in step 3, then compare the new run with the accepted one:

```sh
awkit review compare --run <new run_dir> --diff
```

The input and the summary are `changed`, with diffs. Without `--run`, the comparison uses this folder, where the summary does not exist; it shows as `missing` with a note explaining why.

## Afterwards

To apply this to the person's data, replace `process.py` with the real processing command and `check_output.py` with a check that recomputes something from the input, and list inputs and outputs under `artifacts`. For large or external inputs, record their identifier and hash instead of the file.
