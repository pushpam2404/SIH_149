"""QThread wrapper so long-running core operations never block the GUI thread.

Every drive-erase, file-erase-batch, and recovery-scan call from the GUI
goes through Worker so progress/result/error land back on the main
thread via Qt signals instead of a blocking call.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, **kwargs):
        super().__init__()
        self._fn = fn
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(progress_cb=self._emit_progress, **self._kwargs)
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001 - surface any core error to the GUI
            self.failed.emit(str(exc))

    def _emit_progress(self, *args) -> None:
        self.progress.emit(" ".join(str(a) for a in args))
