"""Windows device backend: PowerShell Storage cmdlets for enumeration,
`\\\\.\\PhysicalDriveN` for raw access.

Enumeration runs ONE PowerShell script that emits JSON (never scraped
text). Every value is cast to a plain string/number/bool inside PowerShell
so the JSON shape is the same on Windows PowerShell 5.1 and PowerShell 7
— 5.1 serializes enums such as BusType as integers, 7 as strings, and
the parser below accepts both.

System-drive detection is layered (any one is enough to block a disk):
  - Get-Disk IsSystem  (disk holds the EFI/system partition)
  - Get-Disk IsBoot    (disk holds the running Windows boot volume)
  - the disk that holds the partition with %SystemDrive%'s drive letter
If PowerShell fails entirely, no devices are listed (fail closed).

Raw writes: since Windows Vista, writes to sectors that belong to a
mounted volume are refused even for Administrators. open_raw() therefore
takes the disk offline (`Set-Disk -IsOffline $true`) for the duration of a
write and restores the previous online/read-only state afterwards.

STATUS: parsing and safety classification are covered by unit tests with
recorded PowerShell output; enumeration runs in CI on a Windows runner.
A real erase of a physical USB drive on Windows has NOT been performed —
see docs/technical_documentation.md, Platform Support Matrix.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sys

from app.core.devices.backend_base import DeviceBackend, DeviceInfo
from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import run, which_any

logger = get_logger(__name__)

_PHYSICAL_DRIVE_RE = re.compile(r"^\\\\\.\\PhysicalDrive(\d+)$", re.IGNORECASE)

# MSFT_Disk BusType enum values, for PowerShell 5.1 which serializes enums as ints.
_BUS_TYPE_NAMES = {
    0: "Unknown", 1: "SCSI", 2: "ATAPI", 3: "ATA", 4: "1394", 5: "SSA", 6: "Fibre Channel",
    7: "USB", 8: "RAID", 9: "iSCSI", 10: "SAS", 11: "SATA", 12: "SD", 13: "MMC",
    14: "Virtual", 15: "File Backed Virtual", 16: "Storage Spaces", 17: "NVMe",
}
# Buses whose disks are treated as external/removable. Everything else
# (SATA, NVMe, RAID, virtual, unknown, ...) is treated as internal and blocked.
_REMOVABLE_BUSES = {"usb", "sd", "mmc"}

_ENUMERATE_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$sysLetter = ($env:SystemDrive).TrimEnd(':')
$sysDisks = @()
try { $sysDisks = @(Get-Partition -DriveLetter $sysLetter -ErrorAction Stop | ForEach-Object { [int]$_.DiskNumber }) } catch {}
$items = @(Get-Disk | ForEach-Object {
    $d = $_
    $fs = @()
    try {
        $fs = @(Get-Partition -DiskNumber $d.Number -ErrorAction Stop |
                Get-Volume -ErrorAction SilentlyContinue |
                Where-Object { $_.FileSystemType } |
                ForEach-Object { [string]$_.FileSystemType })
    } catch {}
    $media = ''
    try { $media = [string](Get-PhysicalDisk -ErrorAction Stop | Where-Object { [string]$_.DeviceId -eq [string]$d.Number } | Select-Object -First 1).MediaType } catch {}
    [pscustomobject]@{
        Number           = [int]$d.Number
        FriendlyName     = [string]$d.FriendlyName
        SerialNumber     = ([string]$d.SerialNumber).Trim()
        Size             = [uint64]$d.Size
        BusType          = [string]$d.BusType
        MediaType        = $media
        IsSystem         = [bool]$d.IsSystem
        IsBoot           = [bool]$d.IsBoot
        HostsSystemDrive = [bool]($sysDisks -contains [int]$d.Number)
        IsOffline        = [bool]$d.IsOffline
        IsReadOnly       = [bool]$d.IsReadOnly
        FileSystems      = $fs
    }
})
ConvertTo-Json -InputObject $items -Depth 4 -Compress
"""


def _powershell() -> str | None:
    found = which_any("powershell", "pwsh")
    if found:
        return found
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return candidate if os.path.exists(candidate) else None


def _run_powershell(script: str, timeout: float = 30.0):
    ps = _powershell()
    if ps is None:
        return None
    return run([ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout=timeout)


def parse_disks_json(raw: str) -> list[dict]:
    """Parses the enumeration script's JSON. Accepts a list or a single
    object (defensive: older ConvertTo-Json unwraps 1-element arrays)."""
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("could not parse PowerShell disk JSON")
        return []
    if isinstance(data, dict):
        data = [data]
    return [d for d in data if isinstance(d, dict)]


def normalize_bus_type(value) -> str:
    if value is None or value == "":
        return "Unknown"
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return _BUS_TYPE_NAMES.get(int(value), "Unknown")
    return str(value)


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def disk_to_device_info(disk: dict) -> DeviceInfo:
    number = int(disk.get("Number"))
    bus = normalize_bus_type(disk.get("BusType"))
    bus_key = bus.lower()
    removable = bus_key in _REMOVABLE_BUSES
    is_system = (
        _as_bool(disk.get("IsSystem"))
        or _as_bool(disk.get("IsBoot"))
        or _as_bool(disk.get("HostsSystemDrive"))
    )
    media = str(disk.get("MediaType") or "").lower()
    if media == "ssd":
        topology = "nvme" if bus_key == "nvme" else "ssd"
    elif media == "hdd":
        topology = "magnetic"
    else:
        topology = "nvme" if bus_key == "nvme" else None
    filesystems = [str(f) for f in (disk.get("FileSystems") or []) if f]
    name = str(disk.get("FriendlyName") or "").strip()
    serial = str(disk.get("SerialNumber") or "").strip()
    return DeviceInfo(
        path=rf"\\.\PhysicalDrive{number}",
        display_name=name or f"PhysicalDrive{number}",
        size_bytes=int(disk.get("Size") or 0),
        is_disk_image=False,
        is_removable=removable,
        is_internal=not removable,
        is_system_container=is_system,
        filesystem=", ".join(dict.fromkeys(filesystems)) or None,
        model=name or None,
        serial=serial or None,
        topology_type=topology,
        ieee_2883_capabilities=["Clear"],
    )


def parse_physical_drive_number(path: str) -> int:
    match = _PHYSICAL_DRIVE_RE.match(path.strip())
    if not match:
        raise ValueError(f"not a Windows physical drive path (expected \\\\.\\PhysicalDriveN): {path!r}")
    return int(match.group(1))


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001 - any failure means "can't confirm admin"
        return False


class WindowsDeviceBackend(DeviceBackend):
    def _disks(self) -> list[dict]:
        result = _run_powershell(_ENUMERATE_SCRIPT)
        if result is None:
            logger.warning("PowerShell not found; cannot enumerate disks")
            return []
        if not result.ok:
            logger.warning("PowerShell disk enumeration failed: %s", result.stderr.strip()[:500])
            return []
        return parse_disks_json(result.stdout)

    def list_devices(self) -> list[DeviceInfo]:
        devices = []
        for disk in self._disks():
            try:
                devices.append(disk_to_device_info(disk))
            except (TypeError, ValueError) as exc:
                logger.warning("skipping unparseable disk entry %r: %s", disk, exc)
        return devices

    def get_device_info(self, path: str) -> DeviceInfo:
        number = parse_physical_drive_number(path)
        for info in self.list_devices():
            if parse_physical_drive_number(info.path) == number:
                return info
        raise RuntimeError(f"device {path} not found")

    def is_system_drive(self, info: DeviceInfo) -> bool:
        # Fail closed: anything not on a removable bus is treated as unsafe.
        return info.is_system_container or info.is_internal

    def _set_disk_state(self, number: int, *, offline: bool | None = None, read_only: bool | None = None) -> None:
        parts = []
        if offline is not None:
            parts.append(f"Set-Disk -Number {number} -IsOffline ${str(offline).lower()}")
        if read_only is not None:
            parts.append(f"Set-Disk -Number {number} -IsReadOnly ${str(read_only).lower()}")
        if not parts:
            return
        result = _run_powershell("$ErrorActionPreference = 'Stop'; " + "; ".join(parts), timeout=60.0)
        if result is None or not result.ok:
            detail = "PowerShell not found" if result is None else result.stderr.strip()[:500]
            raise OSError(f"could not change state of disk {number}: {detail}")

    @contextlib.contextmanager
    def open_raw(self, info: DeviceInfo, mode: str):
        number = parse_physical_drive_number(info.path)
        writing = any(flag in mode for flag in ("+", "w", "a"))
        if not writing:
            f = open(info.path, "rb", buffering=0)
            try:
                yield f
            finally:
                f.close()
            return

        if not is_admin():
            raise PermissionError(
                "Erasing a physical drive on Windows requires running the app as Administrator."
            )

        current = next((d for d in self._disks() if int(d.get("Number", -1)) == number), None)
        if current is None:
            raise OSError(f"disk {number} disappeared before erase started")
        was_offline = _as_bool(current.get("IsOffline"))
        was_read_only = _as_bool(current.get("IsReadOnly"))

        # Offline first (dismounts every volume on the disk), then clear read-only.
        if not was_offline:
            self._set_disk_state(number, offline=True)
        try:
            if was_read_only:
                self._set_disk_state(number, read_only=False)
            # Unbuffered: raw device handles need sector-aligned I/O, which the
            # chunked writer/verifier provide; a Python buffer could misalign it.
            f = open(info.path, "r+b", buffering=0)
            try:
                yield f
            finally:
                f.close()
        finally:
            try:
                if was_read_only:
                    self._set_disk_state(number, read_only=True)
            finally:
                if not was_offline:
                    self._set_disk_state(number, offline=False)
