"""pytsk3 (Sleuth Kit) structure-aware recovery.

Walks the filesystem's directory metadata directly (not the live
directory listing) so it can find entries the filesystem still knows
about but marks unallocated/deleted — this works even after a file was
deleted, as long as the filesystem structure itself is intact and hasn't
been overwritten. It does NOT help once a filesystem has been
reformatted/destroyed entirely; that case is PhotoRecEngine's job
(signature-based carving with no filesystem metadata at all).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from app.core.recovery.engine_base import RecoveredFileCandidate, RecoveryEngine
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

try:
    import pytsk3

    _PYTSK3_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when pytsk3 isn't installed
    pytsk3 = None
    _PYTSK3_AVAILABLE = False

_READ_CHUNK = 1024 * 1024
# Characters that are invalid in file names on Windows (and "/" everywhere).
_UNSAFE_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_output_name(inode: int, name: str) -> str:
    """Output file name for a recovered entry that is valid on every OS.
    Deleted FAT entries start with 0xE5 and NTFS names can contain ':' etc."""
    cleaned = _UNSAFE_NAME_CHARS.sub("_", name).strip(" .") or "unnamed"
    return f"inode{inode}_{cleaned}"[:200]


def _open_filesystem(img):
    """Tries FS_Info at offset 0 (unpartitioned/superfloppy media); falls back
    to scanning a partition table for the first parseable volume."""
    try:
        return pytsk3.FS_Info(img)
    except OSError:
        pass

    try:
        volume = pytsk3.Volume_Info(img)
    except OSError as exc:
        raise RuntimeError(f"no filesystem and no partition table found: {exc}") from exc

    block_size = getattr(volume.info, "block_size", 512)
    for part in volume:
        try:
            return pytsk3.FS_Info(img, offset=part.start * block_size)
        except OSError:
            continue
    raise RuntimeError("no parseable filesystem found in any partition")


class TskEngine(RecoveryEngine):
    name = "pytsk3"

    def is_available(self) -> bool:
        return _PYTSK3_AVAILABLE

    def scan(self, source_path: str, output_dir: str) -> list[RecoveredFileCandidate]:
        if not self.is_available():
            logger.warning("pytsk3 not installed — skipping this engine")
            return []

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            img = pytsk3.Img_Info(source_path)
            fs = _open_filesystem(img)
        except (OSError, RuntimeError) as exc:
            logger.warning("pytsk3 could not open a filesystem on %s: %s", source_path, exc)
            return []

        candidates: list[RecoveredFileCandidate] = []
        self._walk(fs, fs.open_dir(path="/"), "/", out_dir, candidates, seen_inodes=set())
        return candidates

    def _walk(self, fs, directory, path_prefix, out_dir, candidates, seen_inodes, depth=0):
        if depth > 12:  # guard against directory-entry loops in corrupted metadata
            return
        for entry in directory:
            try:
                name = entry.info.name.name.decode("utf-8", errors="replace")
            except AttributeError:
                continue
            if name in (".", ".."):
                continue
            meta = entry.info.meta
            if meta is None:
                continue
            if meta.addr in seen_inodes:
                continue

            is_deleted = bool(meta.flags & pytsk3.TSK_FS_META_FLAG_UNALLOC)
            is_dir = meta.type == pytsk3.TSK_FS_META_TYPE_DIR

            if is_dir:
                if not is_deleted:
                    try:
                        subdir = fs.open_dir(inode=meta.addr)
                        seen_inodes.add(meta.addr)
                        self._walk(fs, subdir, f"{path_prefix}{name}/", out_dir, candidates, seen_inodes, depth + 1)
                    except OSError:
                        pass
                continue

            if not is_deleted:
                continue  # this engine surfaces deleted-but-still-indexed files

            seen_inodes.add(meta.addr)
            candidate = self._extract(fs, entry, meta, name, path_prefix, out_dir)
            if candidate is not None:
                candidates.append(candidate)

    def _extract(self, fs, entry, meta, name, path_prefix, out_dir):
        size = meta.size
        if size <= 0:
            return None

        output_path = out_dir / safe_output_name(meta.addr, name)

        try:
            f = fs.open_meta(inode=meta.addr)
            written = 0
            with open(output_path, "wb") as out:
                offset = 0
                while offset < size:
                    chunk = f.read_random(offset, min(_READ_CHUNK, size - offset))
                    if not chunk:
                        break
                    out.write(chunk)
                    written += len(chunk)
                    offset += len(chunk)
        except OSError as exc:
            logger.debug("failed to extract inode %s (%s): %s", meta.addr, name, exc)
            return None

        if written == 0:
            os.remove(output_path)
            return None

        return RecoveredFileCandidate(
            source_engine=self.name,
            recovered_path=str(output_path),
            suggested_name=name,
            size_bytes=written,
            source_offset=None,
            is_fragmented=False,  # pytsk3 read_random reassembles fragments transparently
            is_deleted_entry=True,
            engine_metadata={"original_path": f"{path_prefix}{name}", "inode": meta.addr},
        )
