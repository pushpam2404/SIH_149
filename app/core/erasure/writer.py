"""Low-level chunked overwrite I/O, shared by the drive and file erasers."""
from __future__ import annotations

import os
from typing import BinaryIO, Callable

from app.config.constants import CHUNK_SIZE
from app.core.erasure.standards.base import FillMode

ProgressCallback = Callable[[int, int], None]  # (bytes_written, total_bytes)


def _fill_chunk(fill: FillMode, size: int) -> bytes:
    if fill == "zero":
        return b"\x00" * size
    if fill == "ones":
        return b"\xff" * size
    if fill == "random":
        return os.urandom(size)
    raise ValueError(f"unknown fill mode: {fill!r}")


def write_pass(
    file_obj: BinaryIO,
    total_size: int,
    fill: FillMode,
    chunk_size: int = CHUNK_SIZE,
    progress_cb: ProgressCallback | None = None,
) -> None:
    """Overwrites `total_size` bytes starting at the current position of file_obj
    (caller is responsible for seeking to the right offset first)."""
    written = 0
    while written < total_size:
        this_chunk = min(chunk_size, total_size - written)
        file_obj.write(_fill_chunk(fill, this_chunk))
        written += this_chunk
        if progress_cb is not None:
            progress_cb(written, total_size)
    file_obj.flush()
    os.fsync(file_obj.fileno())
