"""Progress bar + scrolling status log, shared by every long-running view."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget


class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._status_label = QLabel("Idle")
        layout.addWidget(self._status_label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)  # indeterminate by default; call set_determinate() for known totals
        self._bar.setVisible(False)
        layout.addWidget(self._bar)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(500)
        layout.addWidget(self._log)

    def start(self, status: str = "Working...") -> None:
        self._status_label.setText(status)
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
        self._bar.setVisible(False)
        self._log.appendPlainText(status)
