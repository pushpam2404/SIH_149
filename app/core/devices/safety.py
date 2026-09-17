"""Deny-list-first safe-target enforcement for drive erasure.

This is the single highest-stakes correctness requirement in the project
(see the plan's risk list): a false negative here — failing to recognize
a device as the system drive — is the worst possible bug. The policy is
therefore "only explicitly-recognized-safe things are allowed", never
"anything not flagged as dangerous is allowed".

Safe targets are exactly:
  - disk image files (.img/.dd/etc, created or selected by the user)
  - devices the backend reports as removable/external AND NOT the system
    container AND NOT internal

Everything else — including any device the backend can't confidently
classify — is denied.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.devices.backend_base import DeviceBackend, DeviceInfo


class UnsafeTargetError(Exception):
    """Raised when erasure is attempted against a target that failed the safety check."""


@dataclass(frozen=True)
class SafetyVerdict:
    allowed: bool
    reason: str


def classify_target(info: DeviceInfo, backend: DeviceBackend) -> SafetyVerdict:
    if info.is_disk_image:
        return SafetyVerdict(True, "disk image file — safe by construction")

    if info.is_system_container:
        return SafetyVerdict(False, "device is (or backs) the system/boot drive")

    if info.is_internal and not info.is_removable:
        return SafetyVerdict(
            False, "internal, non-removable device — only external/removable devices or disk images are permitted"
        )

    if backend.is_system_drive(info):
        # Defense-in-depth: the backend flagged this device as unsafe even
        # though the DeviceInfo fields above didn't catch it.
        return SafetyVerdict(False, "backend flagged this device as unsafe to write to")

    if info.is_removable and not info.is_internal:
        return SafetyVerdict(True, "external/removable device")

    # Anything ambiguous (backend couldn't clearly classify) fails closed.
    return SafetyVerdict(False, "could not confidently classify device as a safe target")


def assert_safe(info: DeviceInfo, backend: DeviceBackend) -> None:
    verdict = classify_target(info, backend)
    if not verdict.allowed:
        raise UnsafeTargetError(f"refusing to erase {info.path!r}: {verdict.reason}")
