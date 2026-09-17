"""Pure-Python FAT16 disk image builder with a deleted file — no OS tools.

The macOS fixture (make_test_image.py) uses hdiutil/diskutil, so the
recovery tests could only run on macOS. This builder writes the FAT16
structures directly, so the same recovery test runs on Windows and Linux
(and in CI). It mimics what a FAT driver does on delete: the first byte of
the directory entry becomes 0xE5 and the file's cluster chain is freed in
the FAT, but the data clusters themselves are left untouched.

Layout (superfloppy, no partition table):
  sector 0          boot sector / BPB
  sectors 1..32     FAT #1
  sectors 33..64    FAT #2
  sectors 65..96    root directory (512 entries)
  sector 97..       data area, clusters of 4 sectors (2 KiB)
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

SECTOR = 512
SECTORS_PER_CLUSTER = 4
CLUSTER = SECTOR * SECTORS_PER_CLUSTER
RESERVED_SECTORS = 1
NUM_FATS = 2
ROOT_ENTRIES = 512
TOTAL_SECTORS = 32768  # 16 MiB
SECTORS_PER_FAT = 32
ROOT_DIR_SECTORS = (ROOT_ENTRIES * 32 + SECTOR - 1) // SECTOR
FIRST_DATA_SECTOR = RESERVED_SECTORS + NUM_FATS * SECTORS_PER_FAT + ROOT_DIR_SECTORS
DELETED_MARKER = 0xE5


@dataclass
class FatImageResult:
    image_path: str
    deleted_file_name: str
    deleted_file_original_content: bytes
    kept_file_name: str


def _boot_sector(label: str) -> bytes:
    bpb = struct.pack(
        "<3s8sHBHBHHBHHHII",
        b"\xEB\x3C\x90",
        b"MSWIN4.1",
        SECTOR,
        SECTORS_PER_CLUSTER,
        RESERVED_SECTORS,
        NUM_FATS,
        ROOT_ENTRIES,
        TOTAL_SECTORS,
        0xF8,
        SECTORS_PER_FAT,
        32,  # sectors per track
        2,  # heads
        0,  # hidden sectors
        0,  # total sectors (32-bit field; unused because the 16-bit field fits)
    )
    ebpb = struct.pack(
        "<BBBI11s8s",
        0x80,
        0,
        0x29,
        0x1234ABCD,
        label.upper().ljust(11)[:11].encode("ascii"),
        b"FAT16   ",
    )
    sector = bytearray(SECTOR)
    sector[: len(bpb)] = bpb
    sector[len(bpb) : len(bpb) + len(ebpb)] = ebpb
    sector[510:512] = b"\x55\xAA"
    return bytes(sector)


def _short_name(name: str) -> bytes:
    stem, _, ext = name.upper().partition(".")
    if not (1 <= len(stem) <= 8 and len(ext) <= 3):
        raise ValueError(f"fixture only supports 8.3 names, got {name!r}")
    return stem.ljust(8).encode("ascii") + ext.ljust(3).encode("ascii")


def _dir_entry(name: str, start_cluster: int, size: int) -> bytearray:
    entry = bytearray(32)
    entry[0:11] = _short_name(name)
    entry[11] = 0x20  # archive attribute
    # 12:00:00 on 2026-01-01 for created/modified; exact values don't matter for recovery.
    fat_time = (12 << 11)
    fat_date = ((2026 - 1980) << 9) | (1 << 5) | 1
    struct.pack_into("<HH", entry, 14, fat_time, fat_date)
    struct.pack_into("<H", entry, 18, fat_date)
    struct.pack_into("<HH", entry, 22, fat_time, fat_date)
    struct.pack_into("<H", entry, 26, start_cluster)
    struct.pack_into("<I", entry, 28, size)
    return entry


def make_fat16_image_with_deleted_file(
    image_path: str,
    deleted_content: bytes = b"hello forensic world, this text should be recoverable.\n" * 40,
    kept_content: bytes = b"this file is kept and should still be listed normally.\n",
    deleted_name: str = "DELETEME.TXT",
    kept_name: str = "KEEPME.TXT",
) -> FatImageResult:
    image = bytearray(TOTAL_SECTORS * SECTOR)
    image[0:SECTOR] = _boot_sector("TESTVOL")

    fat = bytearray(SECTORS_PER_FAT * SECTOR)
    struct.pack_into("<HH", fat, 0, 0xFFF8, 0xFFFF)

    root = bytearray(ROOT_DIR_SECTORS * SECTOR)
    next_cluster = 2

    def add_file(slot: int, name: str, data: bytes, deleted: bool) -> None:
        nonlocal next_cluster
        clusters = max(1, (len(data) + CLUSTER - 1) // CLUSTER)
        start = next_cluster
        for i in range(clusters):
            cluster = start + i
            offset = (FIRST_DATA_SECTOR + (cluster - 2) * SECTORS_PER_CLUSTER) * SECTOR
            chunk = data[i * CLUSTER : (i + 1) * CLUSTER]
            image[offset : offset + len(chunk)] = chunk
            if not deleted:
                value = 0xFFFF if i == clusters - 1 else cluster + 1
                struct.pack_into("<H", fat, cluster * 2, value)
        entry = _dir_entry(name, start, len(data))
        if deleted:
            entry[0] = DELETED_MARKER  # what a FAT driver does on delete; FAT chain stays free
        root[slot * 32 : slot * 32 + 32] = entry
        next_cluster += clusters

    add_file(0, deleted_name, deleted_content, deleted=True)
    add_file(1, kept_name, kept_content, deleted=False)

    fat_start = RESERVED_SECTORS * SECTOR
    for copy in range(NUM_FATS):
        offset = fat_start + copy * SECTORS_PER_FAT * SECTOR
        image[offset : offset + len(fat)] = fat
    root_offset = (RESERVED_SECTORS + NUM_FATS * SECTORS_PER_FAT) * SECTOR
    image[root_offset : root_offset + len(root)] = root

    path = Path(image_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(image))
    return FatImageResult(
        image_path=str(path),
        deleted_file_name=deleted_name,
        deleted_file_original_content=deleted_content,
        kept_file_name=kept_name,
    )
