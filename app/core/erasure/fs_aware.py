"""Filesystem-aware file deletion safety logic.

Detects the filesystem under a path and returns plain-language warnings
about features that can defeat file-level overwriting (copy-on-write,
snapshots, journals, MFT-resident data, FAT directory entries), and
invokes TRIM where the OS allows it.

Detection is cached per device (st_dev): every file on the same volume
has the same filesystem, and the previous per-file subprocess calls made
folder erasure cost ~0.2 s per file on macOS.
"""
from __future__ import annotations

import os
import platform
import time

from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import run, which

logger = get_logger(__name__)

_COPY_ON_WRITE = {"apfs", "btrfs", "zfs", "refs", "bcachefs"}


def _device_id(path: str) -> int | None:
    try:
        return os.stat(path).st_dev
    except OSError:
        return None


def _detect_windows(path: str) -> str:
    import ctypes

    kernel32 = ctypes.windll.kernel32
    volume = ctypes.create_unicode_buffer(261)
    if not kernel32.GetVolumePathNameW(ctypes.c_wchar_p(os.path.abspath(path)), volume, 261):
        return "unknown"
    fs_name = ctypes.create_unicode_buffer(261)
    if not kernel32.GetVolumeInformationW(ctypes.c_wchar_p(volume.value), None, 0, None, None, None, fs_name, 261):
        return "unknown"
    return fs_name.value.lower() or "unknown"


def _detect_macos(path: str) -> str:
    # statfs(2) returns the filesystem type name directly (f_fstypename at
    # offset 72 of the 64-bit struct statfs) — no subprocess needed.
    import ctypes
    import ctypes.util

    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        statfs = getattr(libc, "statfs64", None) or libc.statfs
        buf = ctypes.create_string_buffer(4096)
        if statfs(os.fsencode(path), buf) == 0:
            name = buf.raw[72:88].split(b"\0", 1)[0].decode("ascii", "ignore").lower()
            if name.isalnum():
                return name
    except (OSError, AttributeError):
        pass
    # Fallback: the `mount` table, longest matching mount point wins.
    res = run(["mount"], timeout=5.0)
    if not res.ok:
        return "unknown"
    real = os.path.realpath(path)
    best, best_fs = "", "unknown"
    for line in res.stdout.splitlines():
        if " on " not in line or " (" not in line:
            continue
        mount_point = line.split(" on ", 1)[1].rsplit(" (", 1)[0]
        fs_name = line.rsplit(" (", 1)[1].split(",", 1)[0].strip(") ").lower()
        if (real == mount_point or real.startswith(mount_point.rstrip("/") + "/")) and len(mount_point) > len(best):
            best, best_fs = mount_point, fs_name
    return best_fs


def _detect_linux(path: str) -> str:
    res = run(["df", "-T", path], timeout=5.0)
    if res.ok:
        lines = res.stdout.strip().splitlines()
        if len(lines) > 1 and len(lines[1].split()) > 1:
            return lines[1].split()[1].lower()
    return "unknown"


_FS_BY_DEVICE: dict[int, str] = {}
_SNAPSHOTS_BY_DEVICE: dict[int, list[str]] = {}


def _detect_uncached(path: str) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            return _detect_windows(path)
        if system == "Darwin":
            return _detect_macos(path)
        if system == "Linux":
            return _detect_linux(path)
    except Exception as exc:  # noqa: BLE001 - detection is best-effort
        logger.debug("filesystem detection failed for %s: %s", path, exc)
    return "unknown"


def detect_filesystem(path: str) -> str:
    """Best-effort filesystem name for the volume holding `path` (lowercase),
    e.g. "apfs", "ntfs", "ext4", "vfat"/"msdos"/"fat32", or "unknown"."""
    device_id = _device_id(path)
    if device_id is None:
        return "unknown"
    # All paths on one device share a filesystem, so detect once per device.
    if device_id not in _FS_BY_DEVICE:
        _FS_BY_DEVICE[device_id] = _detect_uncached(path)
    return _FS_BY_DEVICE[device_id]


def check_apfs_snapshots(path: str) -> list[str]:
    """Checks if there are Time Machine local snapshots on the volume containing the path."""
    if platform.system() != "Darwin":
        return []
    try:
        res = run(["df", path], timeout=5.0)
        if not res.ok:
            return []
        mount = res.stdout.splitlines()[-1].split()[-1]
        tmutil = which("tmutil")
        if tmutil:
            snap_res = run([tmutil, "listlocalsnapshots", mount], timeout=10.0)
            if snap_res.ok and "com.apple.TimeMachine" in snap_res.stdout:
                return [line for line in snap_res.stdout.splitlines() if "com.apple.TimeMachine" in line]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to check APFS snapshots: %s", exc)
    return []


def warnings_for_filesystem(fs_type: str, file_size: int) -> list[str]:
    """Pure function (no I/O) so the wording per filesystem is unit-testable."""
    fs = fs_type.lower()
    warnings: list[str] = []
    if fs in _COPY_ON_WRITE:
        warnings.append(
            f"{fs.upper()} is a copy-on-write filesystem. Overwrites may be written to new blocks, "
            "leaving the original data on disk until it is reused."
        )
    if fs == "ntfs":
        if file_size < 1024:
            warnings.append(
                "NTFS: small files (under about 1 KB) can be stored inside their MFT record. "
                "Overwriting the file may not clear that MFT record."
            )
        warnings.append(
            "NTFS: Volume Shadow Copies / System Restore points may keep earlier versions of the file, "
            "and alternate data streams attached to it are not overwritten."
        )
    elif fs.startswith("ext") or fs in ("xfs", "jfs", "reiserfs"):
        warnings.append(f"{fs.upper()}: journaling may retain fragments of the file's metadata or data.")
    elif fs in ("vfat", "msdos", "fat", "fat12", "fat16", "fat32", "exfat"):
        warnings.append(
            f"{fs.upper()}: the file's contents are overwritten, but FAT keeps a deleted directory entry, "
            "so most of the ORIGINAL file name can still be recovered."
        )
    return warnings


def get_file_warnings(path: str) -> list[str]:
    """Returns a list of warnings about why this file might not be completely erased."""
    if not os.path.exists(path):
        return []
    fs_type = detect_filesystem(path)
    warnings = warnings_for_filesystem(fs_type, os.path.getsize(path))
    if fs_type == "apfs":
        device_id = _device_id(path)
        if device_id not in _SNAPSHOTS_BY_DEVICE:
            _SNAPSHOTS_BY_DEVICE[device_id] = check_apfs_snapshots(path)
        snapshots = _SNAPSHOTS_BY_DEVICE[device_id]
        if snapshots:
            warnings.insert(
                0,
                f"APFS snapshots detected ({len(snapshots)}). The file data may persist "
                f"in snapshots until they are deleted.",
            )
    return warnings


_TRIM_ATTEMPTS: dict[int, float] = {}
_TRIM_RETRY_SECONDS = 60.0


def invoke_trim(path: str) -> bool:
    """Best-effort TRIM/discard on the volume containing the path.

    Only implemented on Linux (`fstrim`, which needs root). Attempted at most
    once a minute per volume, so erasing a folder doesn't run fstrim per file.
    macOS and Windows: not invoked (returns False) — APFS and NTFS issue TRIM
    for freed blocks automatically when the OS decides to.
    """
    if platform.system() != "Linux":
        return False
    device_id = _device_id(path)
    now = time.monotonic()
    if device_id is not None and now - _TRIM_ATTEMPTS.get(device_id, -_TRIM_RETRY_SECONDS) < _TRIM_RETRY_SECONDS:
        return False
    if device_id is not None:
        _TRIM_ATTEMPTS[device_id] = now
    try:
        fstrim = which("fstrim")
        if not fstrim:
            return False
        res = run(["df", path], timeout=5.0)
        if not res.ok:
            return False
        mount = res.stdout.splitlines()[-1].split()[-1]
        return run([fstrim, mount], timeout=60.0).ok
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to invoke TRIM: %s", exc)
        return False
