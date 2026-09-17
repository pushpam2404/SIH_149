"""Progress bar + scrolling status log, shared by every long-running view."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget

from app.gui.widgets.ui import Badge


def _tone_for_finish(status: str) -> tuple[str, str]:
    lowered = status.lower()
    if lowered.startswith("error") or "fail" in lowered:
        return "Failed", "danger"
    return "Done", "success"


class ProgressPanel(QWidget):
    def __init__(self, parent=None, log_min_height: int = 120):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self._badge = Badge("Idle", "neutral")
        status_row.addWidget(self._badge)
        self._status_label = QLabel("Idle")
        self._status_label.setObjectName("StatusText")
        self._status_label.setWordWrap(True)
        status_row.addWidget(self._status_label, 1)
        layout.addLayout(status_row)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)  # indeterminate by default; call set_determinate() for known totals
        self._bar.setTextVisible(False)
        self._bar.setVisible(False)
        layout.addWidget(self._bar)

        self._log = QPlainTextEdit()
        self._log.setObjectName("Log")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(500)
        self._log.setMinimumHeight(log_min_height)
        self._log.setPlaceholderText("Activity for this operation will appear here.")
        layout.addWidget(self._log)

    def start(self, status: str = "Working...") -> None:
        self._status_label.setText(status)
        self._badge.set("Running", "info")
        self._bar.setRange(0, 0)
        self._bar.setVisible(True)
        self._log.clear()

    def set_determinate(self, current: int, total: int) -> None:
        self._bar.setRange(0, max(total, 1))
        self._bar.setValue(current)

    def log(self, message: str) -> None:
        self._status_label.setText(message)
        self._log.appendPlainText(message)

    def finish(self, status: str) -> None:
        self._status_label.setText(status)
        self._badge.set(*_tone_for_finish(status))
        self._bar.setVisible(False)
        self._log.appendPlainText(status)
