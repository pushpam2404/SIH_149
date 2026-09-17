"""Drive erasure orchestration: safety check -> confirm -> write passes ->
verify -> audit -> report.

Every step is mandatory and in this order — nothing here writes to a
device without first passing app.core.devices.safety.assert_safe(), and
nothing is reported as successful without verify_pass() actually reading
data back.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.config.constants import ACTION_DRIVE_ERASE
from app.core.audit.ledger import AuditLedger
from app.core.devices.backend_base import DeviceBackend, DeviceInfo
from app.core.devices.fingerprint import fingerprint
from app.core.devices.safety import assert_safe
from app.core.erasure.standards import WipeStandard, get_standard
from app.core.erasure.verifier import VerificationResult, verify_pass
from app.core.erasure.writer import write_pass
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[str, int, int], None]  # (pass_label, bytes_written, total_bytes)


class ConfirmationRequiredError(Exception):
    """Raised when a destructive call is made without explicit user confirmation."""


class SimulationModeMismatchError(Exception):
    """Raised when simulation-mode/target-type combination is unsafe or nonsensical."""


@dataclass
class DriveEraseResult:
    ok: bool
    device_fingerprint: str
    standard_id: str
    simulation_mode: bool
    effective_target_path: str
    pass_results: list[VerificationResult] = field(default_factory=list)
    error: str | None = None


def run_drive_erase(
    info: DeviceInfo,
    backend: DeviceBackend,
    standard_id: str,
    ledger: AuditLedger,
    *,
    simulation_mode: bool = True,
    user_confirmed: bool = False,
    simulation_scratch_dir: Path | None = None,
    progress_cb: ProgressCallback | None = None,
) -> DriveEraseResult:
    if not user_confirmed:
        raise ConfirmationRequiredError(
            "drive erase refused: explicit user confirmation was not provided"
        )

    assert_safe(info, backend)

    if not info.is_disk_image and simulation_mode:
        raise SimulationModeMismatchError(
            "simulation mode only applies to disk image targets — turn it off "
            "explicitly to erase a real device, or select a disk image instead"
        )

    standard: WipeStandard = get_standard(standard_id)
    dev_fingerprint = fingerprint(info)

    effective_path = info.path
    if info.is_disk_image and simulation_mode:
        scratch_dir = simulation_scratch_dir or (Path(os.getcwd()) / "data" / "simulation")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        effective_path = str(scratch_dir / f"{dev_fingerprint}-{int(time.time())}.img")
        shutil.copyfile(info.path, effective_path)
        logger.info("simulation mode: wiping scratch copy %s (original untouched)", effective_path)

    pass_results: list[VerificationResult] = []
    error: str | None = None
    try:
        raw_context = open(effective_path, "r+b") if info.is_disk_image else backend.open_raw(info, "r+b")
        with raw_context as f:
            for wipe_pass in standard.passes:
                f.seek(0)
                write_pass(
                    f,
                    info.size_bytes,
                    wipe_pass.fill,
                    progress_cb=(
                        (lambda written, total, label=wipe_pass.label: progress_cb(label, written, total))
                        if progress_cb
                        else None
                    ),
                )
                f.seek(0)
                verification = verify_pass(f, info.size_bytes, wipe_pass.fill)
                pass_results.append(verification)
                if not verification.ok:
                    error = f"verification failed for pass {wipe_pass.label!r}"
                    break
    except OSError as exc:
        error = f"I/O error during erasure: {exc}"

    ok = error is None

    ledger.append_entry(
        action=ACTION_DRIVE_ERASE,
        target=f"{info.display_name} ({dev_fingerprint})",
        payload={
            "standard": standard.id,
            "standard_reference": standard.reference,
            "simulation_mode": simulation_mode,
            "effective_target_path": effective_path,
            "size_bytes": info.size_bytes,
            "passes": [
                {
                    "fill_mode": r.fill_mode,
                    "ok": r.ok,
                    "samples_checked": r.samples_checked,
                    "failures": len(r.failures),
                }
                for r in pass_results
            ],
            "result": "PASS" if ok else "FAIL",
            "error": error,
        },
    )

    return DriveEraseResult(
        ok=ok,
        device_fingerprint=dev_fingerprint,
        standard_id=standard.id,
        simulation_mode=simulation_mode,
        effective_target_path=effective_path,
        pass_results=pass_results,
        error=error,
    )
