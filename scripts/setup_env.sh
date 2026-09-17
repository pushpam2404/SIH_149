#!/usr/bin/env bash
# Installs system dependencies BEFORE the pip packages that wrap them
# (pytsk3 needs sleuthkit's libtsk; python-magic needs libmagic).
# Run this before `pip install -r requirements.txt`.
set -euo pipefail

OS="$(uname -s)"

if [ "$OS" = "Darwin" ]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew is required. Install it from https://brew.sh first." >&2
        exit 1
    fi
    echo "Installing sleuthkit, testdisk, libmagic via Homebrew..."
    brew install sleuthkit testdisk libmagic
    brew install bulk_extractor || echo "Optional: bulk_extractor could not be installed; the PII/artifact panel will stay empty." >&2
elif [ "$OS" = "Linux" ]; then
    echo "Installing sleuthkit, testdisk, libmagic via apt..."
    sudo apt-get update
    sudo apt-get install -y sleuthkit testdisk libmagic1 libmagic-dev
    sudo apt-get install -y bulk-extractor || echo "Optional: bulk_extractor could not be installed; the PII/artifact panel will stay empty." >&2
else
    echo "Unsupported OS: $OS. Install sleuthkit, testdisk, and libmagic manually." >&2
    exit 1
fi

echo
echo "System dependencies installed. Next steps:"
echo "  python3.11 -m venv .venv   # pin to 3.11/3.12 — pytsk3 wheels may lag very new Python releases"
echo "  .venv/bin/pip install -r requirements.txt"
echo "  .venv/bin/python -m pytest tests/"
echo "  .venv/bin/python -m app.main"
