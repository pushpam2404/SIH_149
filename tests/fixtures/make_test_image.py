"""Builds a small FAT disk image with a known deleted file, for reproducible
recovery-module tests and demos.

macOS-only for now (uses hdiutil/diskutil) — see docs/technical_documentation.md,
"Known Limitations". A Linux equivalent would use losetup + mkfs.vfat + mount.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from app.utils.subprocess_utils import require, run


class FixtureBuildError(RuntimeError):
    pass


@dataclass
class TestImageResult:
    image_path: str
    deleted_file_original_content: bytes
    deleted_file_name: str
    kept_file_name: str


def make_fat_image_with_deleted_file(
    image_path: str,
    size_mb: int = 32,
    volume_name: str = "TESTVOL",
    deleted_content: bytes = b"hello forensic world, this text should be recoverable.\n",
) -> TestImageResult:
    require("hdiutil")
    require("diskutil")

    image = Path(image_path)
    image.parent.mkdir(parents=True, exist_ok=True)
    if image.exists():
        image.unlink()

    dd_result = run(["dd", "if=/dev/zero", f"of={image}", "bs=1m", f"count={size_mb}"], timeout=60.0)
    if not dd_result.ok:
        raise FixtureBuildError(f"dd failed: {dd_result.stderr}")

    attach = run(
        ["hdiutil", "attach", "-imagekey", "diskimage-class=CRawDiskImage", "-nomount", str(image)],
        timeout=30.0,
    )
    if not attach.ok:
        raise FixtureBuildError(f"hdiutil attach failed: {attach.stderr}")
    device_path = attach.stdout.strip().splitlines()[0].strip()
    device_id = device_path.rsplit("/", 1)[-1]

    try:
        erase = run(["diskutil", "eraseVolume", "MS-DOS", volume_name, device_path], timeout=30.0)
        if not erase.ok:
            raise FixtureBuildError(f"diskutil eraseVolume failed: {erase.stderr}")

        mount_point = Path(f"/Volumes/{volume_name}")
        deleted_name = "deleteme.txt"
        kept_name = "keepme.txt"
        (mount_point / deleted_name).write_bytes(deleted_content)
        (mount_point / kept_name).write_bytes(b"this file is kept and should still be listed normally.\n")
        run(["sync"], timeout=10.0)
        (mount_point / deleted_name).unlink()
        run(["sync"], timeout=10.0)
        time.sleep(0.5)
    finally:
        run(["diskutil", "eject", device_path], timeout=30.0)

    return TestImageResult(
        image_path=str(image),
        deleted_file_original_content=deleted_content,
        deleted_file_name=deleted_name,
        kept_file_name=kept_name,
    )
