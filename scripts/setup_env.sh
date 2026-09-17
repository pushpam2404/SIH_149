#!/usr/bin/env bash
# Installs system dependencies BEFORE the pip packages that wrap them
# (python-magic needs libmagic; PySide6 needs Qt's X11/EGL runtime libraries on Linux).
# pytsk3 installs as a prebuilt wheel with libtsk bundled.
# Run this before `pip install -r requirements.txt`.
set -euo pipefail

OS="$(uname -s)"

if [ "$OS" = "Darwin" ]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew is required. Install it from https://brew.sh first." >&2
        exit 1
    fi
    echo "Installing testdisk (PhotoRec), libmagic and sleuthkit (CLI tools, optional) via Homebrew..."
    brew install testdisk libmagic sleuthkit
    brew install bulk_extractor || echo "Optional: bulk_extractor could not be installed; the PII/artifact panel will stay empty." >&2
elif [ "$OS" = "Linux" ]; then
    if command -v apt-get >/dev/null 2>&1; then
        echo "Installing testdisk (PhotoRec), libmagic and Qt runtime libraries via apt..."
        sudo apt-get update
        sudo apt-get install -y python3-venv testdisk libmagic1 \
            libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 \
            libxcb-shape0 libxcb-xinerama0 libdbus-1-3 libfontconfig1
        sudo apt-get install -y bulk-extractor || echo "Optional: bulk_extractor could not be installed; the PII/artifact panel will stay empty." >&2
    elif command -v dnf >/dev/null 2>&1; then
        echo "Installing testdisk (PhotoRec), file-libs (libmagic) and Qt runtime libraries via dnf..."
        sudo dnf install -y testdisk file-libs mesa-libEGL libxkbcommon-x11 xcb-util-cursor xcb-util-wm xcb-util-keysyms
    else
        echo "Unknown package manager. Install testdisk and libmagic manually." >&2
    fi
else
    echo "Unsupported OS: $OS. On Windows, run: powershell -ExecutionPolicy Bypass -File scripts\\setup_env.ps1" >&2
    exit 1
fi

echo
echo "System dependencies installed. Next steps:"
echo "  python3.12 -m venv .venv   # Python 3.10-3.13"
echo "  .venv/bin/pip install -r requirements.txt"
echo "  .venv/bin/python -m pytest tests/"
echo "  .venv/bin/python -m app.main"
