"""Picks the right DeviceBackend for the running OS and provides
convenience helpers for building DeviceInfo objects."""
from __future__ import annotations

import os
import platform

from app.core.devices.backend_base import DeviceBackend, DeviceInfo


def get_backend() -> DeviceBackend:
    system = platform.system()
    if system == "Darwin":
        from app.core.devices.backend_macos import MacOSDeviceBackend

        return MacOSDeviceBackend()
    if system == "Linux":
        from app.core.devices.backend_linux import LinuxDeviceBackend

        return LinuxDeviceBackend()
    if system == "Windows":
        from app.core.devices.backend_windows import WindowsDeviceBackend

        return WindowsDeviceBackend()
    raise RuntimeError(f"unsupported platform: {system}")


def list_devices() -> list[DeviceInfo]:
    return get_backend().list_devices()


def disk_image_info(path: str) -> DeviceInfo:
    """Builds a DeviceInfo for a user-selected disk image file (always a safe target)."""
    abs_path = os.path.abspath(path)
    size = os.path.getsize(abs_path)
    return DeviceInfo(
        path=abs_path,
        display_name=os.path.basename(abs_path),
        size_bytes=size,
        is_disk_image=True,
        is_removable=True,
        is_internal=False,
        is_system_container=False,
    )
