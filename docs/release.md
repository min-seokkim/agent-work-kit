# Release and verification procedure

Use this when testing, building or publishing Agent Work Kit. Check the [roadmap](roadmap.md) for unfinished prerequisites and the [evidence record](history/evidence.md#verification-record) for verified environments. Repository working rules remain in [AGENTS.md](../AGENTS.md).

## Release

Release conditions, all required before the first tag:

1. The kit is restructured by situation, the extras are moved, and no further change to command names or file locations is planned.
2. The real tasks in [roadmap item 5](history/roadmap.md#next-work) have been run and their findings applied.
3. No change is planned to formats other tools read: check configuration, `result.json`, artifact manifests, usage results.

Until then users install from `dev` with `install.ps1` or `install.sh`, or with `pipx install "git+https://github.com/min-seokkim/agent-work-kit@dev"`. The installers pin the `dev` branch in their default source; change it to the release when one exists.

Procedure: confirm CI is green, finalize the CHANGELOG section, push a tag matching the version (`v0.3.0`). `.github/workflows/release.yml` tests, builds the wheel, the kit ZIP and `SHA256SUMS` with `scripts/build_release.py`, creates the GitHub release and uploads the wheel to PyPI through a trusted publisher. One-time setup before the first tag: create a `pypi` environment in the GitHub repository settings (add a required reviewer to approve uploads), and add a pending publisher on PyPI for project `agent-work-kit`, this repository, workflow `release.yml`, environment `pypi`. Without it only the PyPI job fails. A version uploaded to PyPI can never be reused. The name `agent-work-kit` was free on PyPI when last checked; check again before the first tag.

## Testing and building

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
ruff check .
python -m pip install "setuptools>=77" wheel && python scripts/build_release.py
```

Tests use only the standard library, need Git and no network. `tests/support.py` gives child processes an absolute `PYTHONPATH`. The browser test runs only with `AWKIT_UI_TEST=1` and Playwright (`AWKIT_BROWSER_CHANNEL=msedge` for Edge). Symbolic link tests skip where the OS refuses links.
