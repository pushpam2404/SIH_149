"""GUI tests run headless: the offscreen Qt platform needs no display, so
they work on CI runners (Windows, Linux, macOS) and over SSH."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from app.gui import dashboard_view, drive_eraser_view, main_window, recovery_view, report_view  # noqa: E402
from app.gui.theme import apply_theme  # noqa: E402


@pytest.fixture()
def window(qtbot, qapp, tmp_path, monkeypatch):
    """MainWindow wired to a throwaway audit DB and reports folder, with device
    enumeration stubbed out so results don't depend on the machine's disks."""
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(main_window, "AUDIT_DB_PATH", tmp_path / "audit.sqlite3")
    monkeypatch.setattr(main_window, "ensure_data_dirs", lambda: None)
    monkeypatch.setattr(dashboard_view, "REPORTS_DIR", reports)
    monkeypatch.setattr(report_view, "REPORTS_DIR", reports)
    monkeypatch.setattr(drive_eraser_view, "list_devices", lambda: [])
    monkeypatch.setattr(recovery_view, "list_devices", lambda: [])
    apply_theme(qapp)
    win = main_window.MainWindow()
    qtbot.addWidget(win)
    win.show()
    yield win
    win.close()
