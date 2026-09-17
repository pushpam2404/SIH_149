"""Main window: tab container for the dashboard + 3 modules + audit/reports."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.config.constants import APP_NAME
from app.config.settings import AUDIT_DB_PATH, ensure_data_dirs
from app.core.audit.ledger import AuditLedger
from app.gui.audit_log_view import AuditLogView
from app.gui.dashboard_view import DashboardView
from app.gui.drive_eraser_view import DriveEraserView
from app.gui.file_eraser_view import FileEraserView
from app.gui.recovery_view import RecoveryView
from app.gui.report_view import ReportView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 750)

        ensure_data_dirs()
        self._ledger = AuditLedger(AUDIT_DB_PATH)

        self._dashboard = DashboardView(self._ledger)
        self._drive_eraser = DriveEraserView(self._ledger)
        self._file_eraser = FileEraserView(self._ledger)
        self._recovery = RecoveryView(self._ledger)
        self._audit_log = AuditLogView(self._ledger)
        self._reports = ReportView()

        tabs = QTabWidget()
        tabs.addTab(self._dashboard, "Dashboard")
        tabs.addTab(self._drive_eraser, "Drive Eraser")
        tabs.addTab(self._file_eraser, "File & Folder Eraser")
        tabs.addTab(self._recovery, "Recovery")
        tabs.addTab(self._audit_log, "Audit Log")
        tabs.addTab(self._reports, "Reports")
        tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(tabs)
        self._tabs = tabs

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if widget is self._dashboard:
            self._dashboard.refresh()
        elif widget is self._audit_log:
            self._audit_log.refresh()
        elif widget is self._reports:
            self._reports.refresh()

    def closeEvent(self, event) -> None:
        self._ledger.close()
        super().closeEvent(event)
