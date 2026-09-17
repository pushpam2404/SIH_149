"""Linux device backend: lsblk -J for enumeration, losetup for loopback images.

NOTE: this backend is written to the same interface as backend_macos.py but
has not been exercised on the macOS dev machine this project was built on
(see docs/technical_documentation.md, "Known Limitations"). Validate on a
real Linux box before relying on it.
"""
from __future__ import annotations

import contextlib
import json

from app.core.devices.backend_base import DeviceBackend, DeviceInfo
from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import require, run

logger = get_logger(__name__)


def _lsblk_json() -> dict:
    lsblk = require("lsblk")
    result = run(
        [lsblk, "-J", "-b", "-o", "NAME,SIZE,RM,RO,TYPE,MOUNTPOINT,MODEL,SERIAL,FSTYPE,ROTA"],
        timeout=30.0,
    )
    if not result.ok:
        raise RuntimeError(f"lsblk failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _boot_device_name() -> str | None:
    """Best-effort: the block device backing the root filesystem."""
    result = run(["findmnt", "-n", "-o", "SOURCE", "/"], timeout=10.0)
    if not result.ok:
        return None
    source = result.stdout.strip()
    # Strip partition suffix (e.g. /dev/sda1 -> sda, /dev/nvme0n1p1 -> nvme0n1)
    name = source.rsplit("/", 1)[-1]
    while name and name[-1].isdigit():
        name = name[:-1]
    name = name.rstrip("p") if name.endswith("p") else name
    return name or None


class LinuxDeviceBackend(DeviceBackend):
    def list_devices(self) -> list[DeviceInfo]:
        data = _lsblk_json()
        boot_name = _boot_device_name()
        devices = []
        for entry in data.get("blockdevices", []):
            if entry.get("type") != "disk":
                continue
            devices.append(self._to_device_info(entry, boot_name))
        return devices

    def get_device_info(self, path: str) -> DeviceInfo:
        name = path.rsplit("/", 1)[-1]
        data = _lsblk_json()
        boot_name = _boot_device_name()
        for entry in data.get("blockdevices", []):
            if entry.get("name") == name:
                return self._to_device_info(entry, boot_name)
        raise RuntimeError(f"device {path} not found via lsblk")

    def _to_device_info(self, entry: dict, boot_name: str | None) -> DeviceInfo:
        name = entry.get("name", "")
        removable = bool(entry.get("rm"))
        return DeviceInfo(
            path=f"/dev/{name}",
            display_name=entry.get("model") or name,
            size_bytes=int(entry.get("size") or 0),
            is_disk_image=False,
            is_removable=removable,
            is_internal=not removable,
            is_system_container=(boot_name is not None and name == boot_name),
            filesystem=entry.get("fstype") or None,
            model=entry.get("model") or None,
            serial=entry.get("serial") or None,
            topology_type="magnetic" if entry.get("rota") == "1" else "ssd",
            has_hpa_dco=False,  # Can use hdparm -N /dev/xxx for HPA in a real implementation
            is_sed=False,       # Can use hdparm -I /dev/xxx for SED detection
            ieee_2883_capabilities=["Clear", "Purge"] if str(entry.get("rota")) == "0" else ["Clear"],
        )

    def is_system_drive(self, info: DeviceInfo) -> bool:
        return info.is_internal or info.is_system_container

    @contextlib.contextmanager
    def open_raw(self, info: DeviceInfo, mode: str):
        f = open(info.path, mode)
        try:
            yield f
        finally:
            f.close()


def attach_loopback(image_path: str) -> str:
    """Attaches a disk image file via losetup, returns the /dev/loopN path."""
    losetup = require("losetup")
    result = run([losetup, "--find", "--show", image_path], timeout=15.0)
    if not result.ok:
        raise RuntimeError(f"losetup failed: {result.stderr.strip()}")
    return result.stdout.strip()


def detach_loopback(loop_path: str) -> None:
    losetup = require("losetup")
    run([losetup, "--detach", loop_path], timeout=15.0)
