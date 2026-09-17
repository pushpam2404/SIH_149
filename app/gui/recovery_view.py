"""Advanced File Carving and Recovery tab: pick a source, scan, review
classified/scored candidates, export selected files, generate a report."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config.settings import DATA_DIR, REPORTS_DIR
from app.core.audit.ledger import AuditLedger
from app.core.devices.enumerator import list_devices
from app.core.recovery.confidence import confidence_label
from app.core.recovery.engine_base import RecoveredFileCandidate
from app.core.recovery.scan_service import ScanSummary, run_recovery_scan
from app.core.reporting.json_report import save_json
from app.core.reporting.pdf_report import render_pdf
from app.core.reporting.report_builder import build_recovery_report
from app.gui.widgets.progress_panel import ProgressPanel
from app.gui.workers import Worker
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

_RESULT_COLUMNS = ["Name", "Engine", "File Type", "Size (bytes)", "Confidence", "Fragmented", "SHA-256", "Fuzzy Hash (ppdeep)"]
_ARTIFACT_COLUMNS = ["Artifact File", "Size (bytes)"]


class RecoveryView(QWidget):
    def __init__(self, ledger: AuditLedger, parent=None):
        super().__init__(parent)
        self._ledger = ledger
        self._worker: Worker | None = None
        self._last_summary: ScanSummary | None = None
        
        self._standard_candidates: list[RecoveredFileCandidate] = []
        self._artifact_candidates: list[RecoveredFileCandidate] = []

        layout = QVBoxLayout(self)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source:"))
        self._source_input = QLineEdit()
        self._source_input.setPlaceholderText("Path to a disk image file, or pick an attached device below")
        source_row.addWidget(self._source_input)

        browse_btn = QPushButton("Browse Image...")
        browse_btn.clicked.connect(self._browse_image)
        source_row.addWidget(browse_btn)
        layout.addLayout(source_row)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Or attached device:"))
        self._device_combo = QComboBox()
        self._device_combo.addItem("(none)", userData=None)
        for device in self._safe_list_devices():
            self._device_combo.addItem(f"{device.display_name} ({device.path})", userData=device.path)
        self._device_combo.currentIndexChanged.connect(self._on_device_selected)
        device_row.addWidget(self._device_combo)
        device_row.addStretch()
        layout.addLayout(device_row)

        scan_btn = QPushButton("Start Recovery Scan")
        scan_btn.clicked.connect(self._start_scan)
        layout.addWidget(scan_btn)

        self._progress = ProgressPanel()
        layout.addWidget(self._progress)

        self._results_table = QTableWidget(0, len(_RESULT_COLUMNS))
        self._results_table.setHorizontalHeaderLabels(_RESULT_COLUMNS)
        self._results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("Recovered Files:"))
        layout.addWidget(self._results_table)

        self._artifacts_table = QTableWidget(0, len(_ARTIFACT_COLUMNS))
        self._artifacts_table.setHorizontalHeaderLabels(_ARTIFACT_COLUMNS)
        self._artifacts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._artifacts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._artifacts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._artifacts_table.itemSelectionChanged.connect(self._show_artifact_contents)
        layout.addWidget(QLabel("PII / Metadata Artifacts (Bulk Extractor):"))
        layout.addWidget(self._artifacts_table)

        result_actions = QHBoxLayout()
        export_btn = QPushButton("Export Selected File...")
        export_btn.clicked.connect(self._export_selected)
        result_actions.addWidget(export_btn)

        report_btn = QPushButton("Generate Forensic Report")
        report_btn.clicked.connect(self._generate_report)
        result_actions.addWidget(report_btn)
        result_actions.addStretch()
        layout.addLayout(result_actions)

    def _safe_list_devices(self):
        try:
            return list_devices()
        except Exception as exc:
            logger.error("device enumeration failed: %s", exc)
            return []

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select disk image to scan", "", "Disk images (*.img *.dd *.dmg);;All files (*)")
        if path:
            self._source_input.setText(path)
            self._device_combo.setCurrentIndex(0)

    def _on_device_selected(self, index: int) -> None:
        path = self._device_combo.currentData()
        if path:
            self._source_input.setText(path)

    def _start_scan(self) -> None:
        source = self._source_input.text().strip()
        if not source:
            QMessageBox.warning(self, "No source", "Enter a disk image path or pick an attached device.")
            return

        output_dir = str(DATA_DIR / "recovery_output" / f"scan_{int(time.time())}")
        self._progress.start(f"Scanning {source}...")
        self._results_table.setRowCount(0)

        self._worker = Worker(run_recovery_scan, source_path=source, output_dir=output_dir, ledger=self._ledger)
        self._worker.progress.connect(self._progress.log)
        self._worker.succeeded.connect(self._on_scan_success)
        self._worker.failed.connect(self._on_scan_failure)
        self._worker.start()

    def _on_scan_success(self, summary: ScanSummary) -> None:
        self._last_summary = summary
        unavailable_note = (
            f" (engines unavailable: {', '.join(summary.engines_unavailable)})"
            if summary.engines_unavailable
            else ""
        )
        self._progress.finish(f"Scan complete — {len(summary.candidates)} candidate(s) found{unavailable_note}")
        self._populate_results(summary.candidates)

    def _on_scan_failure(self, error: str) -> None:
        self._progress.finish(f"Error: {error}")
        QMessageBox.critical(self, "Scan failed", error)

    def _populate_results(self, candidates: list[RecoveredFileCandidate]) -> None:
        self._standard_candidates = [c for c in candidates if c.source_engine != "bulk_extractor"]
        self._artifact_candidates = [c for c in candidates if c.source_engine == "bulk_extractor"]
        
        self._results_table.setRowCount(len(self._standard_candidates))
        for row, candidate in enumerate(self._standard_candidates):
            score = candidate.confidence_score or 0
            values = [
                candidate.suggested_name,
                candidate.source_engine,
                candidate.file_type or "unknown",
                str(candidate.size_bytes),
                f"{score} ({confidence_label(score)})",
                "yes" if candidate.is_fragmented else "no",
                (candidate.sha256 or "")[:16] + "...",
                (candidate.fuzzy_hash or "")[:16] + "..." if candidate.fuzzy_hash else ("skipped (>4 MiB)" if candidate.size_bytes > 4 * 1024 * 1024 else "N/A"),
            ]
            for col, value in enumerate(values):
                self._results_table.setItem(row, col, QTableWidgetItem(value))
                
        self._artifacts_table.setRowCount(len(self._artifact_candidates))
        for row, candidate in enumerate(self._artifact_candidates):
            values = [
                candidate.suggested_name,
                str(candidate.size_bytes)
            ]
            for col, value in enumerate(values):
                self._artifacts_table.setItem(row, col, QTableWidgetItem(value))

    def _show_artifact_contents(self) -> None:
        row = self._artifacts_table.currentRow()
        if row < 0 or row >= len(self._artifact_candidates):
            return
        candidate = self._artifact_candidates[row]
        try:
            with open(candidate.recovered_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(3000)
            if len(content) == 3000:
                content += "\n... [truncated]"
            QMessageBox.information(
                self, f"Artifact: {candidate.suggested_name}",
                content if content.strip() else "(Empty artifact file)"
            )
        except OSError as exc:
            QMessageBox.warning(self, "Error reading artifact", str(exc))

    def _export_selected(self) -> None:
        if not self._last_summary:
            return
        row = self._results_table.currentRow()
        if row < 0 or row >= len(self._standard_candidates):
            QMessageBox.warning(self, "No selection", "Select a recovered file from the results table first.")
            return
        candidate = self._standard_candidates[row]
        dest, _ = QFileDialog.getSaveFileName(self, "Save recovered file as", candidate.suggested_name or "recovered_file")
        if dest:
            shutil.copyfile(candidate.recovered_path, dest)
            QMessageBox.information(self, "Exported", f"Saved to {dest}")

    def _generate_report(self) -> None:
        if not self._last_summary:
            QMessageBox.warning(self, "No scan yet", "Run a recovery scan first.")
            return
        report = build_recovery_report(self._last_summary)
        base = REPORTS_DIR / f"recovery_{report.report_id}"
        save_json(report, str(base.with_suffix(".json")))
        render_pdf(report, str(base.with_suffix(".pdf")))
        QMessageBox.information(self, "Report generated", f"Saved to {base}.pdf")
