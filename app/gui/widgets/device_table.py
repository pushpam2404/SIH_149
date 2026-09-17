"""Device list table for the Drive Eraser view.

A thin QTableWidget wrapper (rather than a full QAbstractTableModel) —
the device list is small and refreshed wholesale on each rescan, so the
extra model/view separation wouldn't buy anything here.
"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from app.core.devices.backend_base import DeviceInfo
from app.core.devices.safety import classify_target

_COLUMNS = ["Name", "Path", "Size", "Type", "Filesystem", "Safety"]


class DeviceTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, len(_COLUMNS), parent)
        self.setHorizontalHeaderLabels(_COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._devices: list[DeviceInfo] = []

    def set_devices(self, devices: list[DeviceInfo], backend) -> None:
        self._devices = devices
        self.setRowCount(len(devices))
        for row, info in enumerate(devices):
            verdict = classify_target(info, backend)
            kind = "Disk Image" if info.is_disk_image else ("Removable" if info.is_removable else "Internal")
            size_gb = info.size_bytes / (1024**3)
            values = [
                info.display_name,
                info.path,
                f"{size_gb:.2f} GB",
                kind,
                info.filesystem or "-",
                "SAFE" if verdict.allowed else f"BLOCKED: {verdict.reason}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if not verdict.allowed:
                    item.setForeground(QColor("#c0392b"))
                self.setItem(row, col, item)

    def selected_device(self) -> DeviceInfo | None:
        row = self.currentRow()
        if row < 0 or row >= len(self._devices):
            return None
        return self._devices[row]
