#!/bin/sh
# Install Agent Work Kit (awkit) on macOS or Linux.
#   curl -fsSL https://raw.githubusercontent.com/min-seokkim/agent-work-kit/dev/install.sh | sh
# Installs Git, Python and pipx with Homebrew on macOS when they are missing, then awkit with pipx,
# then runs `awkit doctor`. On Linux it says which package to install instead of using sudo.
# AWKIT_SOURCE overrides what pipx installs (default: the dev branch on GitHub).
set -eu

SOURCE="${AWKIT_SOURCE:-git+https://github.com/min-seokkim/agent-work-kit@dev}"
OS="$(uname -s)"

say() { printf '%s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
need() {
    say "Missing: $1."
    say "Install it with: $2"
    say "Then run this installer again."
    exit 1
}
brew_install() {
    if ! have brew; then
        need "$1" "Homebrew from https://brew.sh, then: brew install $2"
    fi
    say "Installing $1 with Homebrew..."
    brew install "$2"
}

python_ok() {
    have "$1" && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null
}

if ! have git; then
    case "$OS" in
        Darwin) brew_install Git git ;;
        *) need Git "your package manager, for example: sudo apt install git" ;;
    esac
fi

PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11; do
    if python_ok "$candidate"; then PYTHON="$candidate"; break; fi
done
if [ -z "$PYTHON" ]; then
    case "$OS" in
        Darwin) brew_install "Python 3.12" python@3.12; PYTHON="$(brew --prefix)/bin/python3.12" ;;
        *) need "Python 3.11 or later" "your package manager, for example: sudo apt install python3 python3-venv" ;;
    esac
fi

if have pipx; then
    PIPX="pipx"
elif [ "$OS" = Darwin ] && have brew; then
    brew install pipx
    PIPX="pipx"
elif "$PYTHON" -m pipx --version >/dev/null 2>&1; then
    PIPX="$PYTHON -m pipx"
else
    say "Installing pipx for $PYTHON..."
    if ! "$PYTHON" -m pip install --user pipx >/dev/null 2>&1; then
        need pipx "your package manager, for example: sudo apt install pipx"
    fi
    PIPX="$PYTHON -m pipx"
fi

say "Installing awkit from $SOURCE..."
$PIPX install --force "$SOURCE"
$PIPX ensurepath >/dev/null 2>&1 || true

AWKIT="$HOME/.local/bin/awkit"
[ -x "$AWKIT" ] || AWKIT="awkit"
say ""
"$AWKIT" --version
"$AWKIT" doctor || true
say ""
say "Open a new terminal if the awkit command is not found. Fix anything marked missing above, then run"
say "awkit kit init in your project folder."
