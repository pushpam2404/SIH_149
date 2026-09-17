"""Stable device fingerprinting for audit-log identifiers.

Producing the same ID for the same physical device/image across runs
(and across macOS/Linux backends) matters for the audit trail's
"tamper-resistant reporting" story — the report should always point at
the same logical target.
"""
from __future__ import annotations

import hashlib
import os

from app.core.devices.backend_base import DeviceInfo


def fingerprint(info: DeviceInfo) -> str:
    if info.is_disk_image:
        basis = f"image:{os.path.abspath(info.path)}"
    elif info.serial:
        basis = f"serial:{info.serial}:{info.model or ''}:{info.size_bytes}"
    else:
        # No serial available (common on macOS for some external media) —
        # fall back to path+model+size, which is stable within one session
        # but not guaranteed unique across re-enumeration if paths shift.
        basis = f"path:{info.path}:{info.model or ''}:{info.size_bytes}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
