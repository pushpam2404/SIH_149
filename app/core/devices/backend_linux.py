"""Linux device backend: `lsblk -J` for enumeration, losetup for loopback images.

System-disk detection walks lsblk's device tree: a whole disk is the
system container if ANY descendant (partition, LVM volume, LUKS mapping,
...) is mounted at a system mount point or used as swap. This catches
root-on-LVM/LUKS layouts that a "strip the partition number off
findmnt's source" approach misses.

lsblk's JSON types differ between util-linux versions (older releases
print "rm": "0" as strings, newer ones print booleans), so every flag is
parsed explicitly — `bool("0")` is True in Python and would silently mark
internal disks as removable.

STATUS: parsing and safety classification are covered by unit tests with
recorded lsblk output, and enumeration runs in CI on an Ubuntu runner. A
real erase of a physical drive on Linux has NOT been performed.
"""
from __future__ import annotations

import contextlib
import json

from app.core.devices.backend_base import DeviceBackend, DeviceInfo
from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import require, run

logger = get_logger(__name__)

_SYSTEM_MOUNTPOINTS = {"/", "/boot", "/boot/efi", "/efi", "/usr", "/var", "/home", "[SWAP]"}


def _lsblk_json() -> dict:
    lsblk = require("lsblk")
    result = run(
        [lsblk, "-J", "-b", "-o", "NAME,SIZE,RM,RO,TYPE,MOUNTPOINT,MODEL,SERIAL,FSTYPE,ROTA,TRAN"],
        timeout=30.0,
    )
    if not result.ok:
        raise RuntimeError(f"lsblk failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def as_flag(value) -> bool:
    """lsblk flag parsing that works for both `true`/`false` and `"1"`/`"0"`."""
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def _mountpoints(entry: dict) -> set[str]:
    points = set()
    single = entry.get("mountpoint")
    if single:
        points.add(single)
    for point in entry.get("mountpoints") or []:
        if point:
            points.add(point)
    return points


def hosts_system_mount(entry: dict) -> bool:
    if _mountpoints(entry) & _SYSTEM_MOUNTPOINTS:
        return True
    return any(hosts_system_mount(child) for child in entry.get("children") or [])


def _filesystems(entry: dict) -> list[str]:
    found = [entry["fstype"]] if entry.get("fstype") else []
    for child in entry.get("children") or []:
        found.extend(_filesystems(child))
    return found


def entry_to_device_info(entry: dict) -> DeviceInfo:
    name = entry.get("name", "")
    transport = str(entry.get("tran") or "").lower()
    # HOTPLUG is deliberately ignored: hot-swap SATA/SAS bays report it for
    # internal data disks, which must stay blocked.
    removable = as_flag(entry.get("rm")) or transport in ("usb", "mmc")
    rotational = as_flag(entry.get("rota"))
    filesystems = list(dict.fromkeys(_filesystems(entry)))
    return DeviceInfo(
        path=f"/dev/{name}",
        display_name=(entry.get("model") or "").strip() or name,
        size_bytes=int(entry.get("size") or 0),
        is_disk_image=False,
        is_removable=removable,
        is_internal=not removable,
        is_system_container=hosts_system_mount(entry),
        filesystem=", ".join(filesystems) or None,
        model=(entry.get("model") or "").strip() or None,
        serial=(entry.get("serial") or "").strip() or None,
        topology_type="magnetic" if rotational else ("nvme" if transport == "nvme" else "ssd"),
        has_hpa_dco=False,  # would need hdparm -N
        is_sed=False,  # would need hdparm -I / sedutil
        ieee_2883_capabilities=["Clear"],
    )


def parse_lsblk(data: dict) -> list[DeviceInfo]:
    return [
        entry_to_device_info(entry)
        for entry in data.get("blockdevices", [])
        if entry.get("type") == "disk"
    ]


class LinuxDeviceBackend(DeviceBackend):
    def list_devices(self) -> list[DeviceInfo]:
        return parse_lsblk(_lsblk_json())

    def get_device_info(self, path: str) -> DeviceInfo:
        target = f"/dev/{path.rsplit('/', 1)[-1]}"
        for info in self.list_devices():
            if info.path == target:
                return info
        raise RuntimeError(f"device {path} not found via lsblk")

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
