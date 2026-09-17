"""Overview tab: recent audit activity and chain-integrity status at a glance."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config.constants import APP_NAME, APP_VERSION
from app.core.audit.ledger import AuditLedger

_RECENT_LIMIT = 15
_COLUMNS = ["Timestamp (UTC)", "Action", "Target"]


class DashboardView(QWidget):
    def __init__(self, ledger: AuditLedger, parent=None):
        super().__init__(parent)
        self._ledger = ledger

        layout = QVBoxLayout(self)

        title = QLabel(f"{APP_NAME}  ·  v{APP_VERSION}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self._status_label = QLabel()
        layout.addWidget(self._status_label)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

        layout.addWidget(QLabel("Recent activity:"))
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self._table)

        self.refresh()

    def refresh(self) -> None:
        entries = self._ledger.get_entries()
        chain = self._ledger.verify_chain()
        chain_status = "intact" if chain.ok else f"BROKEN at entry {chain.broken_at_entry_id}"
        self._status_label.setText(
            f"Audit entries: {len(entries)}  ·  Chain integrity: {chain_status}"
        )

        recent = entries[-_RECENT_LIMIT:][::-1]
        self._table.setRowCount(len(recent))
        for row, entry in enumerate(recent):
            values = [entry.timestamp, entry.action, entry.target]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))
