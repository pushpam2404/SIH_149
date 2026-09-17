"""Platform device-backend interface.

Every backend (macOS, Linux, future Windows) must return this single
normalized DeviceInfo shape, so the audit ledger and safety checks never
have to special-case platform-specific field names.
"""
from __future__ import annotations

import contextlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeviceInfo:
    path: str  # OS device path (e.g. /dev/disk4) or absolute path to a disk image file
    display_name: str  # human-readable label for the GUI/reports
    size_bytes: int
    is_disk_image: bool  # True for a plain image file (.img/.dd), not a block device
    is_removable: bool  # reported removable/external status from the OS
    is_internal: bool  # reported internal/fixed status from the OS
    is_system_container: bool  # True if this device backs the running OS's boot/system volume
    filesystem: str | None = None
    model: str | None = None
    serial: str | None = None
    
    # Advanced Compliance / Firmware fields
    topology_type: str | None = None  # e.g. "magnetic", "ssd", "nvme"
    has_hpa_dco: bool = False  # Hidden Protected Area or Device Configuration Overlay present
    is_sed: bool = False  # Self-Encrypting Drive
    ieee_2883_capabilities: list[str] = field(default_factory=list)  # Supported purge commands (Clear, Purge, Sanitize)


class DeviceBackend(ABC):
    @abstractmethod
    def list_devices(self) -> list[DeviceInfo]:
        """Enumerate candidate devices (does not include arbitrary disk image files)."""

    @abstractmethod
    def get_device_info(self, path: str) -> DeviceInfo:
        """Look up full info for a specific device path."""

    @abstractmethod
    def is_system_drive(self, info: DeviceInfo) -> bool:
        """True if writing to this device could destroy the running OS."""

    @abstractmethod
    @contextlib.contextmanager
    def open_raw(self, info: DeviceInfo, mode: str):
        """Context manager yielding a raw binary file object for the device or image."""
