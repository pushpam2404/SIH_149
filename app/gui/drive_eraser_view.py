"""Secure Drive Eraser tab: pick a safe target, pick a standard, confirm, erase, verify, report."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config.settings import REPORTS_DIR
from app.core.audit.ledger import AuditLedger
from app.core.devices.enumerator import disk_image_info, get_backend, list_devices
from app.core.devices.fingerprint import fingerprint
from app.core.devices.safety import classify_target
from app.core.erasure.drive_eraser import DriveEraseResult, run_drive_erase
from app.core.erasure.standards import list_standards
from app.core.reporting.json_report import save_json
from app.core.reporting.pdf_report import render_pdf
from app.core.reporting.report_builder import build_drive_erase_report
from app.gui.widgets.confirm_dialog import ConfirmDestructiveDialog
from app.gui.widgets.device_table import DeviceTable
from app.gui.widgets.progress_panel import ProgressPanel
from app.gui.workers import Worker
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


class DriveEraserView(QWidget):
    def __init__(self, ledger: AuditLedger, parent=None):
        super().__init__(parent)
        self._ledger = ledger
        self._backend = get_backend()
        self._worker: Worker | None = None
        self._selected_image_path: str | None = None

        layout = QVBoxLayout(self)

        button_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.clicked.connect(self._refresh_devices)
        button_row.addWidget(refresh_btn)

        pick_image_btn = QPushButton("Select Disk Image File...")
        pick_image_btn.clicked.connect(self._pick_disk_image)
        button_row.addWidget(pick_image_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._table = DeviceTable()
        layout.addWidget(self._table)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Wipe standard:"))
        self._standard_combo = QComboBox()
        for standard in list_standards():
            self._standard_combo.addItem(standard.display_name, userData=standard.id)
        options_row.addWidget(self._standard_combo)

        self._simulation_checkbox = QCheckBox("Simulation mode (wipe a scratch copy, not the original)")
        self._simulation_checkbox.setChecked(True)
        options_row.addWidget(self._simulation_checkbox)
        options_row.addStretch()
        layout.addLayout(options_row)

        erase_btn = QPushButton("Erase Selected Target")
        erase_btn.clicked.connect(self._start_erase)
        layout.addWidget(erase_btn)

        self._progress = ProgressPanel()
        layout.addWidget(self._progress)

        self._refresh_devices()

    def _refresh_devices(self) -> None:
        try:
            devices = list_devices()
        except Exception as exc:
            logger.error("device enumeration failed: %s", exc)
            devices = []
        if self._selected_image_path:
            devices = [disk_image_info(self._selected_image_path)] + devices
        self._table.set_devices(devices, self._backend)

    def _pick_disk_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select disk image file", "", "Disk images (*.img *.dd *.dmg);;All files (*)")
        if path:
            self._selected_image_path = path
            self._refresh_devices()

    def _start_erase(self) -> None:
        info = self._table.selected_device()
        if info is None:
            QMessageBox.warning(self, "No target selected", "Select a device or disk image from the table first.")
            return

        verdict = classify_target(info, self._backend)
        if not verdict.allowed:
            QMessageBox.critical(self, "Target refused", f"This target cannot be erased: {verdict.reason}")
            return

        confirm_token = fingerprint(info)[:8]
        warning = (
            f"You are about to irreversibly erase:\n\n{info.display_name} ({info.path})\n\n"
            f"Standard: {self._standard_combo.currentText()}\n"
            f"Simulation mode: {'ON — a scratch copy will be wiped, original untouched' if self._simulation_checkbox.isChecked() else 'OFF — this is a REAL wipe'}"
        )
        if not ConfirmDestructiveDialog.confirm(self, warning, confirm_token):
            return

        standard_id = self._standard_combo.currentData()
        simulation_mode = self._simulation_checkbox.isChecked()

        self._progress.start(f"Erasing {info.display_name}...")
        self._worker = Worker(
            run_drive_erase,
            info=info,
            backend=self._backend,
            standard_id=standard_id,
            ledger=self._ledger,
            simulation_mode=simulation_mode,
            user_confirmed=True,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.succeeded.connect(lambda result: self._on_success(result, info))
        self._worker.failed.connect(self._on_failure)
        self._worker.start()

    def _on_progress(self, message: str) -> None:
        self._progress.log(message)

    def _on_success(self, result: DriveEraseResult, info) -> None:
        status = "PASS" if result.ok else f"FAIL: {result.error}"
        self._progress.finish(f"Erase complete — {status}")

        report = build_drive_erase_report(result, info)
        base = REPORTS_DIR / f"drive_erase_{report.report_id}"
        save_json(report, str(base.with_suffix(".json")))
        render_pdf(report, str(base.with_suffix(".pdf")))

        if result.ok:
            QMessageBox.information(self, "Erase complete", f"Verification PASSED.\nReport saved to {base}.pdf")
        else:
            QMessageBox.critical(self, "Erase failed", f"{result.error}\nReport saved to {base}.pdf")

    def _on_failure(self, error: str) -> None:
        self._progress.finish(f"Error: {error}")
        QMessageBox.critical(self, "Erase failed", error)
