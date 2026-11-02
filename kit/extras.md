# Extras for web projects

Commands for web projects: delivery runs with verification and rollback, static site publishing and page capture. They live in `src/awkit/extras/` with their command names unchanged, are not mentioned in the READMEs, and leave the package if real use does not need them The rest of the command reference is in [reference.md](reference.md).

### pipeline

`awkit pipeline --config FILE plan|deploy RELEASE|rollback|status|reconcile|history [--allow-unhealthy-current] [--json]` runs the project's delivery commands in a fixed order and verifies the target's actual state. Its statuses (`passed`, `failed-restored` and the rest) describe one run, not the state of a task. Release IDs are 7 to 64 lowercase hex characters; use full commit or artifact hashes.

```toml
schema_version = 1

[pipeline]
target = "web"                   # letters, digits, . _ -
state_dir = ".awkit/releases"    # relative to this file
timeout_seconds = 120            # per command
required_checks = ["service"]
auto_rollback = false            # needs a rollback command

[commands]                       # argument arrays, no shell
preflight = ["{python}", "{project}/adapter.py", "preflight", "{target}", "{release}"]
backup    = ["{python}", "{project}/adapter.py", "backup", "{target}", "{release}"]    # optional
deploy    = ["{python}", "{project}/adapter.py", "deploy", "{target}", "{release}"]
verify    = ["{python}", "{project}/adapter.py", "verify", "{target}", "{release}"]
rollback  = ["{python}", "{project}/adapter.py", "rollback", "{target}", "{release}"]  # optional
```

Placeholders: `{python}`, `{project}` (the config folder), `{target}`, `{release}`, `{previous}`, `{run_dir}`. The command contract:

- `preflight` prints `{"target": T, "release": ID or null}` without changing anything.
- `deploy` and `rollback` finish all work before exiting; nothing left in the background.
- `verify` reads the release actually running and prints `{"target": T, "release": ID, "checks": [{"name": N, "ok": true}]}`, exiting 0 even when a check fails. Every `required_checks` name must appear. A wrong target, a release other than the requested one, or malformed JSON fails the step. Echoing the requested release defeats verification.
- Omit `backup` and `rollback` for one-way deliveries (submissions, uploads). Then `rollback` and `auto_rollback` are refused, and a failure after the target changed is `failed-unrecovered`.

Order: preflight, verify-current, backup, deploy, verify. A deploy stops at `verify-current` when the current release fails its checks, unless `--allow-unhealthy-current`. Deploying the running healthy release only verifies (`outcome: already-current`). `rollback` takes no release; it walks back one healthy release from `history.json` per run.

| Status | Meaning |
|---|---|
| `passed` | The requested release runs and every check passes. |
| `failed` | Failed before the target changed. |
| `failed-restored` | Deploy failed; automatic rollback restored and verified the previous release. Exit 1. |
| `failed-unrecovered` | Failed after the target changed; recovery not confirmed. |
| `rollback-failed` | Automatic rollback or its verification failed. |
| `uncertain` | Timeout or interruption; state unknown. |

After `running`, `uncertain`, `rollback-failed` or `failed-unrecovered`, every deploy and rollback is blocked. Inspect the real target, recover it, then run `reconcile`: it records `reconciled` (exit 0) or `reconciled-unhealthy` (exit 1) and lifts the block. Do not delete records to skip this. One run per `state_dir` at a time (SQLite lock); there is no lock on the target itself. State: `last-run.json`, `history.json`, `runs/<id>/result.json`, `runs/<id>/logs/`. Logs keep raw output, so keep secrets out of arguments and output. Exit codes: 0 passed, reconciled or healthy (`status`); 1 any other outcome; a project command's own code when it fails with 1 to 125; 2 cannot run; 130 interrupted. A file-only mock is in `examples/local-release/` of the awkit repository.

### publish

`awkit publish --output DIR --project NAME build --source DIR --files LIST.json` publishes a trusted static HTML build. `LIST.json` is a JSON array of relative paths and must include `index.html`; only listed files are copied. Before publishing, every HTML link, anchor and simple CSS `url()` must point at a listed file; external pages may be linked, external resources may not. `@import`, `srcset`, `srcdoc` and `base` are refused. Each version goes to `versions/<content hash>/`, is verified, and only then the entry `index.html` is replaced atomically. `restore VERSION` re-verifies and switches back. The output folder must be empty on first use. One publisher per output folder at a time; the lock does not work across machines or sync folders.

### ui

`awkit ui --config pages.json --output DIR [--channel chrome|msedge|chromium]` captures full-page PNGs of the listed pages at each width and builds `index.html`, `sheet.png` and `result.json` in an empty output folder.

```json
{"base_url": "http://127.0.0.1:8765", "widths": [320, 1440], "timeout_ms": 15000,
 "pages": [{"name": "Home", "path": "/index.html"}]}
```

`base_url` is an origin without credentials or path; 1 to 20 pages, 1 to 6 distinct widths between 240 and 3840. Only same-origin GET and HEAD requests are allowed; other requests, service workers and WebSockets are blocked. Findings per page and width: `horizontal-overflow`, `control-outside-viewport`, `http-error`, `capture-error` and `resource-blocked`. Any finding makes the exit code 1. Judge layout and content from the images yourself.

