# Documents Example

A small Korean document set with one deliberately broken link. It shows a check failing, a fix checked on a snapshot, the checked documents retained with hashes, and an accepted version compared with a later edit. Contents: three documents under `docs/`, `check_docs.py` (titles and links), `checks.toml`, and this example's [project profile](project.md).

You are running this example for a person who wants to see how the kit works. Run each step from this folder, then tell the person in one or two sentences what happened and what it shows. Use the real values from the output; do not describe results you did not see. Commands use POSIX shell syntax; in PowerShell write `$snap = awkit review snapshot ...` instead of `snap=$(...)`.

## 1. Starting point

`awkit kit example` committed this folder to Git (a new repository, or the one it was created in). Checks run on commits, so that commit is the starting point. Confirm with `git log --oneline -1`.

## 2. See the check fail

```sh
awkit review check HEAD --config checks.toml --runs-root .awkit/reviews
```

Expect `status: failed` and exit code 1. Open `01.log` in the printed `run_dir`: it names the document and the broken link.

## 3. Fix and check the snapshot

Fix the link in `docs/index.md` so it points at a file that exists. Then freeze only that file and check it:

```sh
snap=$(awkit review snapshot docs/index.md)
awkit review check "$snap" --config checks.toml --runs-root .awkit/reviews
```

Expect `status: passed`, with the three documents listed under `artifacts` with sizes and SHA-256, and copies under `artifacts/docs/` in the new run folder. The branch and working tree were not changed by the snapshot.

## 4. Verify the retained documents

```sh
awkit review verify <run_dir>
```

Use the `run_dir` from step 3. Every file is `ok` and the exit code is 0. To show what tampering looks like, edit one file under the run folder's `artifacts/` and run it again: that file becomes `changed`.

## 5. Accept, then compare a later edit

```sh
awkit review accept <run_dir>
```

Change one sentence in `docs/guide.md`, then:

```sh
awkit review compare --diff
```

The edited file is `changed` with a diff; the others are `same`. Explain that this is how a regression against an approved document becomes visible.

## Afterwards

Commit the fix. To use this on the person's own documents, follow "Connect the kit to a project" in the kit's agent instructions; for Korean text, follow the kit's Korean Writing Guide.
