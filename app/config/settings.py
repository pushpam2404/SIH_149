"""App-wide runtime configuration.

Paths default to a `data/` directory under the project root so the audit
ledger, generated reports, and demo images stay out of the source tree
(see .gitignore). Override via environment variables for testing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_base_dir() -> Path:
    """Running from source: the project root (as before). Running as a
    PyInstaller bundle: the per-user app-data folder, because the bundle's
    own directory is a temporary extraction folder that is deleted on exit."""
    if not getattr(sys, "frozen", False):
        return PROJECT_ROOT
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "SIH149-SecureEraseRecovery"


BASE_DIR = _default_base_dir()
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BASE_DIR / "data"))
REPORTS_DIR = Path(os.environ.get("APP_REPORTS_DIR", BASE_DIR / "reports"))
AUDIT_DB_PATH = Path(os.environ.get("APP_AUDIT_DB", DATA_DIR / "audit_ledger.sqlite3"))

# When true, drive-erase operations are redirected to a scratch copy of the
# selected disk image instead of writing to the real target. Always safe to
# leave on for demos; must be explicitly disabled to touch a real device.
SIMULATION_MODE_DEFAULT = True

LOG_LEVEL = os.environ.get("APP_LOG_LEVEL", "INFO")


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
