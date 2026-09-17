"""Recovery engine interface.

Each engine (pytsk3 structure-aware, PhotoRec/TestDisk signature-based)
yields RecoveredFileCandidate objects from scan(); the classifier,
confidence scorer, and reassembly layer all operate on this common shape
regardless of which engine produced it.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RecoveredFileCandidate:
    source_engine: str  # "pytsk3", "photorec", "testdisk"
    recovered_path: str  # path to the extracted bytes on disk (in the output dir)
    suggested_name: str  # original filename if known (pytsk3), else engine-assigned name
    size_bytes: int
    source_offset: int | None = None  # byte offset within the source image/device, if known
    is_fragmented: bool = False
    is_deleted_entry: bool = True  # False if recovered from an intact, still-listed dir entry
    engine_metadata: dict = field(default_factory=dict)

    # populated by the classification/confidence layer after scan()
    file_type: str | None = None
    sha256: str | None = None
    fuzzy_hash: str | None = None
    confidence_score: int | None = None
    confidence_reasons: list[str] = field(default_factory=list)


class RecoveryEngine(ABC):
    name: str

    @abstractmethod
    def scan(self, source_path: str, output_dir: str) -> list[RecoveredFileCandidate]:
        """Scans `source_path` (a device path or disk image file) and extracts
        recovered files into `output_dir`, returning candidates found."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if this engine's external dependency is installed and usable."""
