"""Create a practice disk image with a deleted photo — works on Windows, Linux and macOS.

    python -m scripts.make_practice_image my_photo.jpg
    python -m scripts.make_practice_image my_photo.jpg --out practice.img

The image is a 16 MiB FAT16 volume containing a deleted copy of your photo
(recoverable) and one normal file. Nothing needs to be mounted, and no
admin rights are needed. Scan the result in the app's Recovery page.

The photo is deleted the way a FAT driver deletes a file (directory entry
marked deleted, cluster chain freed, data left in place). It is NOT erased
with the app's File & Folder Eraser — for that comparison, use the disk
image walkthrough in docs/beginners_guide.md (macOS) or a USB stick.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tests.fixtures.fat_image import CLUSTER, TOTAL_SECTORS, SECTOR, make_fat16_image_with_deleted_file

_MAX_BYTES = (TOTAL_SECTORS * SECTOR) - 1024 * 1024  # leave room for FAT structures and the kept file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photo", help="picture to put on the image and then delete (under 15 MB)")
    parser.add_argument("--out", default="practice.img", help="output image path (default: practice.img)")
    args = parser.parse_args()

    photo = Path(args.photo)
    if not photo.is_file():
        print(f"Not a file: {photo}", file=sys.stderr)
        return 1
    data = photo.read_bytes()
    if len(data) > _MAX_BYTES:
        print(f"{photo.name} is {len(data) / 1024**2:.1f} MB; please use a picture under 15 MB.", file=sys.stderr)
        return 1

    ext = (photo.suffix.lstrip(".").upper() or "BIN")[:3]
    result = make_fat16_image_with_deleted_file(
        args.out,
        deleted_content=data,
        deleted_name=f"PHOTO1.{ext}",
        kept_content=b"This file was not deleted.\n",
        kept_name="README.TXT",
    )
    clusters = (len(data) + CLUSTER - 1) // CLUSTER
    print(f"Created {Path(result.image_path).resolve()}")
    print(f"  deleted: {result.deleted_file_name} ({len(data)} bytes, {clusters} clusters) — should be recoverable")
    print(f"  kept:    {result.kept_file_name}")
    print("Next: open the app -> Recovery -> Browse Image... -> pick this file -> Start Recovery Scan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
