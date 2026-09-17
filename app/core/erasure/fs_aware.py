"""Filesystem-aware file deletion safety logic.

Checks for filesystem-specific features (APFS snapshots, NTFS MFT residency,
ext4 journaling) that could defeat file-level wiping, and invokes TRIM where possible.
"""
from __future__ import annotations

import os
import shutil
import platform
from pathlib import Path

from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import run, which

logger = get_logger(__name__)


def detect_filesystem(path: str) -> str:
    """Best-effort detection of the filesystem underlying a path."""
    sys_plat = platform.system()
    if sys_plat == "Darwin":
        try:
            # On macOS, diskutil info can tell us the filesystem of the volume
            res = run(["df", "-T", path], timeout=5.0)
            if res.ok:
                # df -T isn't standard on macOS df, but `df -Y` or `stat -f %ST` works
                res2 = run(["stat", "-f", "%ST", path], timeout=5.0)
                if res2.ok:
                    fs = res2.stdout.strip().lower()
                    if "apfs" in fs:
                        return "apfs"
                    if "hfs" in fs:
                        return "hfs"
            
            # Alternative fallback: diskutil
            res3 = run(["df", path], timeout=5.0)
            if res3.ok:
                mount = res3.stdout.splitlines()[-1].split()[-1]
                res4 = run(["diskutil", "info", mount], timeout=10.0)
                if res4.ok and "APFS" in res4.stdout:
                    return "apfs"
        except Exception:
            pass
            
    elif sys_plat == "Linux":
        try:
            # On Linux, df -T is reliable
            res = run(["df", "-T", path], timeout=5.0)
            if res.ok:
                lines = res.stdout.strip().splitlines()
                if len(lines) > 1:
                    return lines[1].split()[1].lower()
        except Exception:
            pass
            
    return "unknown"


def check_apfs_snapshots(path: str) -> list[str]:
    """Checks if there are APFS snapshots on the volume containing the path."""
    sys_plat = platform.system()
    if sys_plat != "Darwin":
        return []
        
    try:
        # Find mount point
        res = run(["df", path], timeout=5.0)
        if not res.ok:
            return []
        mount = res.stdout.splitlines()[-1].split()[-1]
        
        # List snapshots
        tmutil = which("tmutil")
        if tmutil:
            snap_res = run([tmutil, "listlocalsnapshots", mount], timeout=10.0)
            if snap_res.ok and "com.apple.TimeMachine" in snap_res.stdout:
                return [line for line in snap_res.stdout.splitlines() if "com.apple.TimeMachine" in line]
    except Exception as exc:
        logger.debug("Failed to check APFS snapshots: %s", exc)
        
    return []


def get_file_warnings(path: str) -> list[str]:
    """Returns a list of warnings about why this file might not be completely erased."""
    warnings = []
    
    if not os.path.exists(path):
        return warnings
        
    fs_type = detect_filesystem(path)
    file_size = os.path.getsize(path)
    
    if fs_type == "apfs":
        snapshots = check_apfs_snapshots(path)
        if snapshots:
            warnings.append(
                f"APFS snapshots detected ({len(snapshots)}). The file data may persist "
                f"in snapshots until they are deleted."
            )
        warnings.append("APFS is a Copy-on-Write filesystem. Overwrites may be written to new blocks.")
        
    elif "ntfs" in fs_type and file_size < 1024:
        warnings.append("NTFS: Small file (<1KB) may be resident in the MFT ($I30). Overwriting it may not clear the MFT record.")
        
    elif "ext" in fs_type:
        warnings.append(f"{fs_type.upper()}: Journaling (JBD2) may retain fragments of the file metadata or data.")
        
    return warnings


def invoke_trim(path: str) -> bool:
    """Best-effort invocation of TRIM/discard on the volume containing the path."""
    sys_plat = platform.system()
    try:
        if sys_plat == "Linux":
            fstrim = which("fstrim")
            if fstrim:
                # Find mount point
                res = run(["df", path], timeout=5.0)
                if res.ok:
                    mount = res.stdout.splitlines()[-1].split()[-1]
                    trim_res = run([fstrim, mount], timeout=60.0)
                    return trim_res.ok
                    
        elif sys_plat == "Darwin":
            # diskutil secureErase freespace doesn't exactly TRIM in APFS, 
            # but it is the closest standard macOS tool for free space wiping.
            pass
            
    except Exception as exc:
        logger.debug("Failed to invoke TRIM: %s", exc)
        
    return False
