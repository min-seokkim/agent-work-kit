#!/bin/bash
# Session start for this repository: in a Claude Code cloud session, install awkit from this checkout
# and the linter and switch on the commit identity hook; in every session where awkit is available,
# record the starting point that `awkit check done` compares against when the agent stops.
# awkit is installed as a copy of the session's starting commit, not in editable mode: the hooks and the
# check runner then keep working while the session changes src/awkit, and a broken change cannot judge
# itself. `awkit review check` still tests each snapshot's own code through PYTHONPATH (checks.toml).
set -euo pipefail

input="$(cat)"
cd "${CLAUDE_PROJECT_DIR:-.}"

if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
    export PATH="$HOME/.local/bin:$PATH"
    if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
    fi
    python3 -m pip install --quiet --root-user-action=ignore --user --force-reinstall --no-deps . >&2
    command -v ruff >/dev/null 2>&1 || python3 -m pip install --quiet --root-user-action=ignore --user ruff >&2
    awkit kit hooks --git >&2
fi

if command -v awkit >/dev/null 2>&1; then
    printf '%s' "$input" | awkit check done --hook
fi
