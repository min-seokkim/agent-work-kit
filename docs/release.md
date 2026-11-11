# Release and verification procedure

Use this when testing, building or publishing Agent Work Kit. The goal is 0.3.0, the first release. The [roadmap](roadmap.md) holds the work left to meet the gate below; repository working rules are in [AGENTS.md](../AGENTS.md).

## The 0.3.0 gate

Tag only when every condition holds for the commit to be tagged.

| Condition | How it is checked |
|---|---|
| Every stable command group meets the feature bar | The scope table below |
| Windows and Linux CI are green | The CI run of that commit |
| The release build was rehearsed | A manual run of `release.yml` (workflow_dispatch) built the wheel and the skills ZIP from that commit |
| No incompatible change is planned | The roadmap's Ready and owner tables hold none |
| PyPI can accept the upload | The owner created the `pypi` environment and the PyPI pending publisher (below) |
| The owner said to release | The owner's message |

### Feature scope

A stable group is one 0.3.0 promises. Its bar: every command the kit shows parses against the CLI (`tests/test_kit_commands.py`); its failure paths have tests; it passes Windows and Linux CI; it was used in real work at least once.

| Group | Status | Left to do |
|---|---|---|
| kit, doctor, check, hook runner and default rules, review, channel | Stable, bar met | Used throughout this repository's own development |
| session | Stable, bar not met | Codex automatic sidebar registration remains unresolved: a fresh awkit root probe appeared after exact-ID app navigation. Claude picker visibility remains unmet; the owner retains the picker condition and holds the release. Current Codex on three operating systems, Claude SDK range checks and macOS session tests passed CI at `dacf8f8` |
| usage | Stable, bar met | Format 4 and sanitized real logs passed Windows and Linux CI at `0484121` |
| pipeline, publish, ui | Removed | No recorded real use; installed-wheel CI uses `review` |

## Release

1. Confirm the gate, and that the CHANGELOG's 0.3.0 section is complete.
2. In one commit, point the installers' default source and both READMEs at the PyPI package `agent-work-kit` instead of the `dev` branch.
3. Push a tag matching the version (`v0.3.0`). `.github/workflows/release.yml` tests, builds the wheel, the skills ZIP and `SHA256SUMS` with `scripts/build_release.py`, creates the GitHub release and uploads the wheel to PyPI through a trusted publisher. A version uploaded to PyPI can never be reused.
4. Check the release page and the PyPI page, then install with `pipx install agent-work-kit` on Windows and Linux and run `awkit --version`.

One-time setup by the owner before the first tag: in the GitHub repository settings, create an environment named `pypi` with yourself as required reviewer; on PyPI, add a pending publisher for project `agent-work-kit`, repository `min-seokkim/agent-work-kit`, workflow `release.yml`, environment `pypi`. The name `agent-work-kit` was free on PyPI at `31c4d6d`.

## Testing and building

```sh
python scripts/run_tests.py
ruff check .
python -m pip install "setuptools>=77" wheel && python scripts/build_release.py
```

Tests use only the standard library, need Git and no network. `scripts/run_tests.py` runs each test module in its own process, as many at once as there are CPUs; `PYTHONPATH=src python -m unittest discover -s tests -v` runs them all in one. `tests/support.py` gives child processes an absolute `PYTHONPATH`. The browser test runs only with `AWKIT_UI_TEST=1` and Playwright (`AWKIT_BROWSER_CHANNEL=msedge` for Edge). Symbolic link tests skip where the OS refuses links.
