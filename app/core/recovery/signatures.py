"""Custom magic-byte signature table.

This is the primary classification signal because it has zero native
library dependency (unlike python-magic/libmagic, which is used only as
an optional secondary cross-check in classifier.py). It also gives us
header/footer completeness data that feeds directly into confidence.py.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signature:
    file_type: str
    header: bytes
    header_offset: int = 0
    footer: bytes | None = None
    extension: str = ""


SIGNATURES: list[Signature] = [
    Signature("JPEG", b"\xff\xd8\xff", footer=b"\xff\xd9", extension="jpg"),
    Signature("PNG", b"\x89PNG\r\n\x1a\n", footer=b"IEND\xaeB`\x82", extension="png"),
    Signature("GIF", b"GIF87a", extension="gif"),
    Signature("GIF", b"GIF89a", footer=b"\x00\x3b", extension="gif"),
    Signature("PDF", b"%PDF-", footer=b"%%EOF", extension="pdf"),
    Signature("ZIP/Office (docx/xlsx/pptx/zip)", b"PK\x03\x04", extension="zip"),
    Signature("GZIP", b"\x1f\x8b\x08", extension="gz"),
    Signature("MP4/MOV", b"ftyp", header_offset=4, extension="mp4"),
    Signature("BMP", b"BM", extension="bmp"),
    Signature("RIFF (WAV/AVI)", b"RIFF", extension="riff"),
    Signature("7-ZIP", b"7z\xbc\xaf\x27\x1c", extension="7z"),
    Signature("RAR", b"Rar!\x1a\x07", extension="rar"),
    Signature("SQLite DB", b"SQLite format 3\x00", extension="sqlite"),
]


def match_header(data: bytes) -> Signature | None:
    for sig in SIGNATURES:
        end = sig.header_offset + len(sig.header)
        if len(data) >= end and data[sig.header_offset:end] == sig.header:
            return sig
    return None


def has_matching_footer(data: bytes, sig: Signature, search_window: int = 4096) -> bool:
    if sig.footer is None:
        return False
    tail = data[-search_window:] if len(data) > search_window else data
    return sig.footer in tail
