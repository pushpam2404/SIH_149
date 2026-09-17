"""Bulk_extractor wrapper for PII and feature extraction.

Runs bulk_extractor to find emails, credit cards, EXIF data, etc.,
and surfaces its feature files as RecoveredFileCandidates.
"""
from __future__ import annotations

from pathlib import Path

from app.core.recovery.engine_base import RecoveredFileCandidate, RecoveryEngine
from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import run, which

logger = get_logger(__name__)

_SCAN_TIMEOUT_SECONDS = 900.0


class BulkExtractorEngine(RecoveryEngine):
    name = "bulk_extractor"

    def is_available(self) -> bool:
        return which("bulk_extractor") is not None

    def scan(self, source_path: str, output_dir: str) -> list[RecoveredFileCandidate]:
        if not self.is_available():
            logger.warning("bulk_extractor not installed — skipping this engine")
            return []

        out_dir = Path(output_dir) / "bulk_extractor_out"
        out_dir.mkdir(parents=True, exist_ok=True)
        abs_source = str(Path(source_path).resolve())

        # run bulk_extractor
        result = run(
            ["bulk_extractor", "-o", str(out_dir), abs_source],
            timeout=_SCAN_TIMEOUT_SECONDS,
            cwd=str(out_dir.parent),
        )
        logger.info("bulk_extractor scan of %s exited (returncode=%s)", source_path, result.returncode)

        if result.returncode != 0:
            logger.warning("bulk_extractor had a non-zero exit code: %s", result.returncode)

        return self._parse_output(out_dir)

    def _parse_output(self, out_dir: Path) -> list[RecoveredFileCandidate]:
        candidates: list[RecoveredFileCandidate] = []
        
        # bulk_extractor generates .txt files for features (like email.txt, credit_card.txt)
        # we consider any non-empty txt file a "recovered candidate" of features.
        for txt_file in out_dir.glob("*.txt"):
            if not txt_file.is_file():
                continue
            
            size = txt_file.stat().st_size
            if size == 0:
                continue
                
            candidates.append(
                RecoveredFileCandidate(
                    source_engine=self.name,
                    recovered_path=str(txt_file),
                    suggested_name=txt_file.name,
                    size_bytes=size,
                    source_offset=None,
                    is_fragmented=False,
                )
            )
            
        # It also extracts some files in subdirectories (like zip, word, etc.) if configured.
        # But by default without -E we just get the feature text files, which is fine for PII.
            
        return candidates
