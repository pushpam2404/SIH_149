"""Picks the right DeviceBackend for the running OS and provides
convenience helpers for building DeviceInfo objects."""
from __future__ import annotations

import os
import platform
import sys

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


def is_raw_device_path(path: str) -> bool:
    return path.startswith("\\\\.\\") or path.startswith("/dev/")


def raw_access_problem(path: str, write: bool = False) -> str | None:
    """Plain-language reason the current process can't read a raw device, or
    None if it looks fine (or `path` is a regular file). Checked up front so a
    permission problem isn't reported as "0 files recovered"."""
    if not is_raw_device_path(path):
        return None
    if sys.platform == "win32":
        from app.core.devices.backend_windows import is_admin

        if not is_admin():
            action = "Erasing" if write else "Reading"
            return f"{action} a physical drive on Windows requires starting the app as Administrator."
        return None
    if not os.path.exists(path):
        return f"{path} does not exist."
    if not os.access(path, os.W_OK if write else os.R_OK):
        return (
            f"This user can't {'write to' if write else 'read'} {path}. Run the app with elevated rights "
            "(e.g. sudo on Linux; on macOS, sudo plus Full Disk Access for the terminal)."
        )
    return None


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
