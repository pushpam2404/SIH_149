"""Audit ledger viewer: lists every logged action and can verify the hash chain."""
from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QFileDialog,
)

from app.core.audit.ledger import AuditLedger
from app.core.audit.certificate import CertificateGenerator

_COLUMNS = ["ID", "Timestamp (UTC)", "Actor", "Action", "Target", "Entry Hash"]


class AuditLogView(QWidget):
    def __init__(self, ledger: AuditLedger, parent=None):
        super().__init__(parent)
        self._ledger = ledger

        layout = QVBoxLayout(self)

        button_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        button_row.addWidget(refresh_btn)

        verify_btn = QPushButton("Verify Chain Integrity")
        verify_btn.clicked.connect(self._verify_chain)
        button_row.addWidget(verify_btn)
        
        cert_btn = QPushButton("Generate Certificate (Sec. 63-style)")
        cert_btn.clicked.connect(self._generate_certificate)
        button_row.addWidget(cert_btn)
        
        button_row.addStretch()
        layout.addLayout(button_row)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.itemSelectionChanged.connect(self._show_selected_payload)
        layout.addWidget(self._table)

        self.refresh()

    def refresh(self) -> None:
        entries = self._ledger.get_entries()
        self._entries = entries
        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                str(entry.entry_id),
                entry.timestamp,
                entry.actor,
                entry.action,
                entry.target,
                entry.entry_hash[:16] + "...",
            ]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))

    def _verify_chain(self) -> None:
        result = self._ledger.verify_chain()
        if result.ok:
            QMessageBox.information(
                self, "Chain verified",
                f"Audit chain is intact — {result.entries_checked} entries verified, no tampering detected.",
            )
        else:
            QMessageBox.critical(
                self, "Chain verification FAILED",
                f"Tampering detected at entry {result.broken_at_entry_id}:\n{result.reason}",
            )

    def _show_selected_payload(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(getattr(self, "_entries", [])):
            return
        entry = self._entries[row]
        QMessageBox.information(
            self, f"Entry {entry.entry_id} details",
            json.dumps(entry.payload, indent=2)[:3000],
        )

    def _generate_certificate(self) -> None:
        entries = self._ledger.get_entries()
        if not entries:
            QMessageBox.warning(self, "No Entries", "The audit log is empty.")
            return
            
        targets = sorted(list(set(e.target for e in entries)))
        if not targets:
            QMessageBox.warning(self, "No Targets", "No targets found in the audit log.")
            return

        target, ok = QInputDialog.getItem(
            self, "Select Target", "Select device/target for the certificate:", targets, 0, False
        )
        if not ok or not target:
            return

        operator_name, ok = QInputDialog.getText(self, "Operator Name", "Enter the operator's name:")
        if not ok or not operator_name:
            return

        org_name, ok = QInputDialog.getText(self, "Organization Name", "Enter the organization's name:")
        if not ok or not org_name:
            return
            
        wipe_status, ok = QInputDialog.getText(self, "Wipe Status", "Enter wipe status as you verified it (e.g. 'Clear - overwrite verified'):", text="Clear - overwrite verified")
        if not ok or not wipe_status:
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Certificate", f"certificate_{operator_name.replace(' ', '_')}.json", "JSON Files (*.json)"
        )
        if not out_path:
            return

        try:
            generator = CertificateGenerator(self._ledger, operator_name, org_name)
            generator.generate_json_certificate(target, wipe_status, out_path)
            QMessageBox.information(self, "Success", f"Certificate generated and saved to:\n{out_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to generate certificate:\n{exc}")
