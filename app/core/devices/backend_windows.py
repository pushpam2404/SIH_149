"""Windows device backend — stub for future work, not implemented in this MVP.

A real implementation would enumerate via WMI (`Win32_DiskDrive`) or
`diskpart list disk` scripting, and would need to identify the system
drive via `diskpart` (`list disk` + the boot disk's index from
`Get-Disk | where IsBoot`) before any write path is exposed. Raw device
I/O on Windows requires opening `\\\\.\\PhysicalDriveN` with the Win32
API (not a plain Python `open()`), typically via `pywin32` or `ctypes`.
"""
from __future__ import annotations

import contextlib
import json

from app.core.devices.backend_base import DeviceBackend, DeviceInfo
from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import run, require

logger = get_logger(__name__)


def _get_ps_disks() -> list[dict]:
    # Use PowerShell to get disk information in JSON format
    ps = require("powershell")
    if not ps:
        # Fallback to powershell.exe if 'powershell' is not exactly in PATH but usually is on Windows
        ps = "powershell.exe"
        
    cmd = [
        ps, 
        "-NoProfile", 
        "-Command", 
        "Get-Disk | Select-Object Number, FriendlyName, Size, IsSystem, IsBoot, BusType | ConvertTo-Json"
    ]
    
    result = run(cmd, timeout=15.0)
    if not result.ok:
        logger.warning("PowerShell Get-Disk failed: %s", result.stderr)
        return []
        
    out = result.stdout.strip()
    if not out:
        return []
        
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            return [data]
        return data
    except json.JSONDecodeError:
        logger.warning("Failed to parse PowerShell JSON output")
        return []


class WindowsDeviceBackend(DeviceBackend):
    def list_devices(self) -> list[DeviceInfo]:
        disks = _get_ps_disks()
        devices = []
        for disk in disks:
            num = disk.get("Number")
            if num is None:
                continue
            devices.append(self._to_device_info(disk))
        return devices

    def get_device_info(self, path: str) -> DeviceInfo:
        # path is expected to be \\.\PhysicalDriveX
        if not path.startswith(r"\\.\PhysicalDrive"):
            raise ValueError(f"Invalid Windows physical drive path: {path}")
            
        try:
            num = int(path.replace(r"\\.\PhysicalDrive", ""))
        except ValueError:
            raise ValueError(f"Invalid Windows physical drive path: {path}")
            
        disks = _get_ps_disks()
        for disk in disks:
            if disk.get("Number") == num:
                return self._to_device_info(disk)
                
        raise RuntimeError(f"Device {path} not found")

    def _to_device_info(self, disk: dict) -> DeviceInfo:
        num = disk.get("Number")
        path = rf"\\.\PhysicalDrive{num}"
        is_sys = bool(disk.get("IsSystem") or disk.get("IsBoot"))
        bus_type = str(disk.get("BusType", "")).lower()
        
        topology_type = "ssd" if bus_type in ("nvme", "sas", "sata") else "magnetic"  # simplified heuristic
        
        return DeviceInfo(
            path=path,
            display_name=disk.get("FriendlyName") or f"PhysicalDrive{num}",
            size_bytes=int(disk.get("Size") or 0),
            is_disk_image=False,
            is_removable=bus_type in ("usb", "sd"),
            is_internal=bus_type not in ("usb", "sd"),
            is_system_container=is_sys,
            filesystem=None,  # Need Get-Volume for FS
            model=disk.get("FriendlyName"),
            serial=None,
            topology_type=topology_type,
            has_hpa_dco=False,
            is_sed=False,
            ieee_2883_capabilities=["Clear"],
        )

    def is_system_drive(self, info: DeviceInfo) -> bool:
        return info.is_system_container

    @contextlib.contextmanager
    def open_raw(self, info: DeviceInfo, mode: str):
        # On Windows, raw disk access requires running as Administrator.
        # It expects the \\.\PhysicalDriveN path format.
        f = open(info.path, mode)
        try:
            yield f
        finally:
            f.close()
