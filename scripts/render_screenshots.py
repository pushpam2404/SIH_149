"""Render every page and the main dialogs to PNG files, to compare the UI
across Windows, Linux and macOS.

    python -m scripts.render_screenshots out_dir

Uses a throwaway audit DB and reports folder and real device enumeration
(read-only). Nothing is erased or scanned. Run it with the platform's normal
display (not QT_QPA_PLATFORM=offscreen) to see real font rendering; CI does
this on each OS.
"""
from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots")
    out.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="sih149_shots_")
    os.environ["APP_DATA_DIR"] = tmp
    os.environ["APP_REPORTS_DIR"] = os.path.join(tmp, "reports")
    os.environ["APP_AUDIT_DB"] = os.path.join(tmp, "audit.sqlite3")

    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from app.gui.theme import apply_theme
    from app.gui.widgets import file_dialogs
    from app.gui.widgets.confirm_dialog import ConfirmDestructiveDialog

    app = QApplication(sys.argv)
    apply_theme(app)
    from app.gui.main_window import MainWindow

    window = MainWindow()
    window.resize(1280, 820)
    window.show()
    window._ledger.append_entry("file_erase", "/example/secret.txt", {"ok": True})
    tag = platform.system().lower()

    def settle():
        for _ in range(5):
            app.processEvents()

    for key in window._page_index:
        window._navigate_to(key)
        settle()
        window.grab().save(str(out / f"{tag}_{key}.png"))

    dialog = file_dialogs._dialog(window, "Select disk image file", QFileDialog.ExistingFile,
                                  "Disk images (*.img *.dd *.dmg);;All files (*)")
    dialog.setDirectory(str(Path(__file__).resolve().parents[1]))
    dialog.show()
    settle()
    dialog.grab().save(str(out / f"{tag}_file_dialog.png"))
    dialog.close()

    confirm = ConfirmDestructiveDialog("You are about to irreversibly erase 1 file(s).", "ERASE FILES", window)
    confirm.show()
    settle()
    confirm.grab().save(str(out / f"{tag}_confirm_dialog.png"))
    confirm.close()

    box = QMessageBox(QMessageBox.Warning, "Not enough permissions", "Example warning message.", parent=window)
    box.show()
    settle()
    box.grab().save(str(out / f"{tag}_message_box.png"))
    box.close()

    # Short window: pages must scroll, not overlap (regression seen on a 1024×768 screen).
    window.resize(1000, 600)
    for key in ("file_eraser", "drive_eraser"):
        window._navigate_to(key)
        settle()
        window.grab().save(str(out / f"{tag}_{key}_small_window.png"))

    window.close()
    print(f"Saved {len(list(out.glob(tag + '_*.png')))} screenshots to {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
