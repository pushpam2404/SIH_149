"""macOS device backend: diskutil for enumeration/info, hdiutil for disk images.

Uses `-plist` output modes and plistlib rather than scraping text output,
so parsing doesn't depend on diskutil's human-readable formatting.
"""
from __future__ import annotations

import contextlib
import plistlib

from app.core.devices.backend_base import DeviceBackend, DeviceInfo
from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import require, run

logger = get_logger(__name__)


def _diskutil_plist(subcommand: str, *rest: str) -> dict:
    """`-plist` must directly follow the subcommand (e.g. `info -plist disk0`),
    not trail the whole argument list — diskutil rejects it otherwise."""
    diskutil = require("diskutil")
    result = run([diskutil, subcommand, "-plist", *rest], timeout=30.0)
    if not result.ok:
        raise RuntimeError(f"diskutil {subcommand} failed: {result.stderr.strip()}")
    return plistlib.loads(result.stdout.encode("utf-8"))


class MacOSDeviceBackend(DeviceBackend):
    def list_devices(self) -> list[DeviceInfo]:
        data = _diskutil_plist("list")
        whole_disks = data.get("WholeDisks", [])
        devices = []
        for identifier in whole_disks:
            try:
                devices.append(self.get_device_info(f"/dev/{identifier}"))
            except RuntimeError:
                logger.warning("could not fetch diskutil info for %s", identifier)
        return devices

    def get_device_info(self, path: str) -> DeviceInfo:
        identifier = path.rsplit("/", 1)[-1]
        info = _diskutil_plist("info", identifier)
        return DeviceInfo(
            path=f"/dev/{identifier}",
            display_name=info.get("MediaName") or info.get("VolumeName") or identifier,
            size_bytes=int(info.get("Size", 0)),
            is_disk_image=False,
            is_removable=bool(info.get("RemovableMedia") or info.get("Ejectable")),
            is_internal=bool(info.get("Internal", True)),
            is_system_container=self._is_system_container(identifier),
            filesystem=info.get("FilesystemName") or None,
            model=info.get("MediaName") or None,
            serial=info.get("MediaUUID") or None,
            topology_type="ssd" if info.get("SolidState") else "magnetic",
            has_hpa_dco=False,  # Hard to reliably detect via diskutil without I/O kit bridging
            is_sed=False,       # Would require deeper I/O Kit querying on macOS
            ieee_2883_capabilities=["Clear", "Purge"] if info.get("SolidState") else ["Clear"],
        )

    def _is_system_container(self, identifier: str) -> bool:
        """True if `identifier` is (or is the parent whole disk of) the boot volume."""
        try:
            boot_info = _diskutil_plist("info", "/")
        except RuntimeError:
            # If we can't determine the boot disk, fail closed: treat every
            # device as a potential system drive until proven otherwise.
            return True
        boot_whole_disk = boot_info.get("ParentWholeDisk") or boot_info.get("DeviceIdentifier")
        return boot_whole_disk == identifier

    def is_system_drive(self, info: DeviceInfo) -> bool:
        return info.is_internal or info.is_system_container

    @contextlib.contextmanager
    def open_raw(self, info: DeviceInfo, mode: str):
        f = open(info.path, mode)
        try:
            yield f
        finally:
            f.close()


def create_disk_image(image_path: str, size_mb: int) -> None:
    """Creates a blank raw disk image file via `dd`, for simulation-mode targets."""
    from app.utils.subprocess_utils import run as _run

    result = _run(
        ["dd", "if=/dev/zero", f"of={image_path}", "bs=1m", f"count={size_mb}"],
        timeout=120.0,
    )
    if not result.ok:
        raise RuntimeError(f"failed to create disk image: {result.stderr.strip()}")
