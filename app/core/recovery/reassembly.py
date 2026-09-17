"""Fragmented-file reconstruction from a list of byte runs.

A "byte run" is (offset within source image, length) — both pytsk3 (via
attribute runs) and PhotoRec's DFXML report (<byte_run img_offset len>)
expose recovered files this way when they aren't stored contiguously.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ByteRun:
    source_offset: int
    length: int


def is_fragmented(byte_runs: list[ByteRun]) -> bool:
    return len(byte_runs) > 1


def find_gaps(byte_runs: list[ByteRun]) -> list[int]:
    """Indices (into byte_runs) where a run doesn't immediately follow the
    previous one in the source image — informational only, we don't attempt
    to guess/fill the missing data in between."""
    gaps = []
    for i in range(1, len(byte_runs)):
        prev = byte_runs[i - 1]
        if byte_runs[i].source_offset != prev.source_offset + prev.length:
            gaps.append(i)
    return gaps


def carve_bifragment_gap(source_path: str, gap_offset: int, gap_length: int, start_sig: bytes, end_sig: bytes | None = None) -> bytes | None:
    """Attempts to recover data from a gap by searching for known headers/footers.
    Returns the recovered chunk if found, otherwise None.
    """
    with open(source_path, "rb") as src:
        src.seek(gap_offset)
        # Read the gap data (plus a reasonable margin if we aren't exactly sure, 
        # but for now we stick to gap_length)
        # We cap it to avoid large memory spikes
        max_read = min(gap_length, 1024 * 1024 * 10)  # max 10MB search
        data = src.read(max_read)
        
    start_idx = data.find(start_sig)
    if start_idx == -1:
        return None
        
    if end_sig:
        end_idx = data.find(end_sig, start_idx)
        if end_idx != -1:
            return data[start_idx:end_idx + len(end_sig)]
            
    # If no end sig or not found, just return from start_idx to the end of the gap
    return data[start_idx:]


def reassemble(source_path: str, byte_runs: list[ByteRun], output_path: str, attempt_gap_carving: bool = False, file_sig: bytes | None = None) -> int:
    """Concatenates byte runs from source_path into output_path in order,
    returns total bytes written. If attempt_gap_carving is True and the file has gaps,
    it will attempt to extract data using carve_bifragment_gap."""
    total = 0
    with open(source_path, "rb") as src, open(output_path, "wb") as dst:
        for i, run in enumerate(byte_runs):
            # Check gap with previous run
            if attempt_gap_carving and file_sig and i > 0:
                prev = byte_runs[i - 1]
                expected_offset = prev.source_offset + prev.length
                if run.source_offset > expected_offset:
                    gap_offset = expected_offset
                    gap_length = run.source_offset - expected_offset
                    carved = carve_bifragment_gap(source_path, gap_offset, gap_length, file_sig)
                    if carved:
                        dst.write(carved)
                        total += len(carved)
                        
            src.seek(run.source_offset)
            data = src.read(run.length)
            dst.write(data)
            total += len(data)
    return total
