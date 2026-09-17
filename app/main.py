"""Entry point: launches the QApplication and MainWindow."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme
from app.utils.logging_setup import setup_logging


def _set_windows_app_id() -> None:
    """Gives the app its own taskbar identity on Windows (otherwise it groups
    under python.exe with Python's icon)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SIH149.SecureEraseRecovery")
    except Exception:  # noqa: BLE001 - cosmetic only
        pass


def main() -> int:
    setup_logging()
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("Integrated Secure Erasure & Recovery Tool")
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
