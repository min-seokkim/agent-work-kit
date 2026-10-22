#!/bin/bash
# Session start for this repository: in a Claude Code cloud session, install awkit from this checkout
# and the linter and switch on the commit identity hook; in every session where awkit is available,
# record the starting point that `awkit check done` compares against when the agent stops.
set -euo pipefail

input="$(cat)"
cd "${CLAUDE_PROJECT_DIR:-.}"

if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
    export PATH="$HOME/.local/bin:$PATH"
    if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
    fi
    python3 -m pip install --quiet --root-user-action=ignore --user --editable . >&2
    command -v ruff >/dev/null 2>&1 || python3 -m pip install --quiet --root-user-action=ignore --user ruff >&2
    awkit kit hooks --git >&2
fi

if command -v awkit >/dev/null 2>&1; then
    printf '%s' "$input" | awkit check done --hook
fi
