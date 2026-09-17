"""Lists generated reports (from the reports/ directory) and opens them."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config.settings import REPORTS_DIR


class ReportView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        button_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        button_row.addWidget(refresh_btn)

        open_btn = QPushButton("Open PDF")
        open_btn.clicked.connect(self._open_selected)
        button_row.addWidget(open_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self._list)

        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        if not REPORTS_DIR.exists():
            return
        for pdf_path in sorted(REPORTS_DIR.glob("*.pdf"), reverse=True):
            self._list.addItem(pdf_path.name)

    def _open_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            QMessageBox.warning(self, "No selection", "Select a report from the list first.")
            return
        path = REPORTS_DIR / item.text()
        if not path.exists():
            QMessageBox.critical(self, "Not found", f"{path} no longer exists.")
            self.refresh()
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
