# Release and verification procedure

Use this when testing, building or publishing Agent Work Kit. 0.3.0 was the first release. The [roadmap](roadmap.md) holds the next release goal and work left to meet the gate below; repository working rules are in [AGENTS.md](../AGENTS.md).

## Release gate

Tag only when every condition holds for the commit to be tagged.

| Condition | How it is checked |
|---|---|
| Every stable command group meets the feature bar | The scope table below |
| Windows and Linux CI are green | The CI run of that commit |
| The release build was rehearsed | A manual run of `release.yml` (workflow_dispatch) built the wheel and the skills ZIP from that commit |
| No incompatible change is planned | The roadmap's Ready and owner tables hold none |
| PyPI can accept the upload | The `pypi` environment and trusted publisher are configured; the version has never been uploaded |
| The owner said to release | The owner's message |

### Feature scope

A stable group is one 0.3.0 promises. Its bar: every command the kit shows parses against the CLI (`tests/test_kit_commands.py`); its failure paths have tests; it passes Windows and Linux CI; it was used in real work at least once.

| Group | Status | Left to do |
|---|---|---|
| kit, doctor, check, hook runner and default rules, review, channel | Stable, bar met | Used throughout this repository's own development |
| session | Stable, bar met | The owner saw an unopened awkit root probe under the Codex project after restarting the app. Claude SDK sessions open with `claude --resume <native_id>`; picker visibility moved after 0.3.0 by the owner's decision. Current Codex on three operating systems, Claude SDK range checks and macOS session tests passed CI at `dacf8f8` |
| usage | Stable, bar met | Format 4 and sanitized real logs passed Windows and Linux CI at `0484121` |
| pipeline, publish, ui | Removed | No recorded real use; installed-wheel CI uses `review` |

## Release

1. Set the same release version in `pyproject.toml` and `src/awkit/__init__.py`, and complete its CHANGELOG section. Keep the installers on PyPI and check both READMEs. The wheel's PyPI description comes from `README.md` at build time; changing the repository afterward does not update it.
2. Check the frozen revision with `awkit review check` and `checks.toml`, push to `dev`, and confirm Windows and Linux CI. Run `release.yml` manually on that commit and confirm the wheel, skills ZIP and `SHA256SUMS`. Inspect the wheel's version and README metadata. Confirm the remaining gate conditions before tagging.
3. Push a tag matching the checked version (for example, `v0.3.1`). `.github/workflows/release.yml` tests, builds the release files, creates the GitHub release and uploads the wheel to PyPI through a trusted publisher. Approve the `pypi` environment deployment under the owner's release authorization. A version uploaded to PyPI can never be reused.
4. Check the release assets and the version's PyPI description. On Windows and Linux, install `agent-work-kit==VERSION` from PyPI into a fresh pipx environment, run `awkit --version` and `awkit doctor`, and confirm the expected version. Replace `VERSION` with the release number. Close the roadmap row only after these checks pass.

One-time setup by the owner before the first tag: in the GitHub repository settings, create an environment named `pypi` with yourself as required reviewer; on PyPI, add a pending publisher for project `agent-work-kit`, repository `min-seokkim/agent-work-kit`, workflow `release.yml`, environment `pypi`. The name `agent-work-kit` was free on PyPI at `31c4d6d`.

## Testing and building

```sh
python scripts/run_tests.py
ruff check .
python -m pip install "setuptools>=77" wheel && python scripts/build_release.py
```

Tests use only the standard library, need Git and no network. `scripts/run_tests.py` runs each test module in its own process, as many at once as there are CPUs; `PYTHONPATH=src python -m unittest discover -s tests -v` runs them all in one. `tests/support.py` gives child processes an absolute `PYTHONPATH`. The browser test runs only with `AWKIT_UI_TEST=1` and Playwright (`AWKIT_BROWSER_CHANNEL=msedge` for Edge). Symbolic link tests skip where the OS refuses links.
