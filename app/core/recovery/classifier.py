"""Classification layer: signature match (primary) + python-magic (optional
secondary cross-check) + filename-extension sanity check.

python-magic/libmagic is treated as optional — if it isn't installed, we
degrade gracefully to signature-only classification rather than failing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.recovery.signatures import Signature, has_matching_footer, match_header
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

try:
    import magic as _libmagic
    _MAGIC_AVAILABLE = True
except ImportError:
    _libmagic = None
    _MAGIC_AVAILABLE = False

try:
    from magika import Magika
    _MAGIKA_AVAILABLE = True
except ImportError:
    _MAGIKA_AVAILABLE = False

_magika_instance = None


def _magika():
    """Loading the Magika model takes ~100 ms; do it once, not per file."""
    global _magika_instance
    if _magika_instance is None:
        _magika_instance = Magika()
    return _magika_instance


def _magika_label_and_score(result) -> tuple[str, float]:
    """Magika >= 0.6 exposes `result.output.label` and `result.score`; older
    releases used `result.output.ct_label` and `result.output.score`."""
    output = result.output
    label = getattr(output, "label", None) or getattr(output, "ct_label", None)
    score = getattr(result, "score", None)
    if score is None:
        score = getattr(output, "score", 0.0)
    return str(label), float(score)


@dataclass
class ClassificationResult:
    file_type: str
    signature: Signature | None
    header_matched: bool
    footer_matched: bool
    libmagic_description: str | None
    reasons: list[str]


def classify(file_path: str, suggested_name: str = "") -> ClassificationResult:
    reasons: list[str] = []
    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except OSError as exc:
        return ClassificationResult(
            file_type="unreadable", signature=None, header_matched=False, footer_matched=False,
            libmagic_description=None, reasons=[f"could not read file: {exc}"],
        )

    sig = match_header(data)
    header_matched = sig is not None
    footer_matched = False
    file_type = "unknown"

    if sig is not None:
        file_type = sig.file_type
        reasons.append(f"header matches {sig.file_type} signature")
        footer_matched = has_matching_footer(data, sig)
        if sig.footer is not None:
            reasons.append("footer marker found" if footer_matched else "footer marker NOT found (possible truncation/fragmentation)")
    else:
        reasons.append("no known header signature matched")

    ext = os.path.splitext(suggested_name)[1].lstrip(".").lower()
    if sig is not None and ext and ext != sig.extension:
        reasons.append(f"filename extension {ext!r} does not match expected {sig.extension!r}")

    libmagic_description = None
    if _MAGIC_AVAILABLE:
        try:
            libmagic_description = _libmagic.from_buffer(data[:4096])
            reasons.append(f"libmagic cross-check: {libmagic_description}")
        except Exception as exc:  # pragma: no cover - depends on optional native lib
            logger.debug("libmagic classification failed: %s", exc)

    if _MAGIKA_AVAILABLE:
        try:
            res = _magika().identify_bytes(data)
            magika_label, magika_score = _magika_label_and_score(res)
            
            reasons.append(f"magika cross-check: {magika_label} (score: {magika_score:.2f})")
            
            # If our primary signature logic was unknown but Magika is highly confident, we can use it
            if file_type == "unknown" and magika_score > 0.8:
                file_type = magika_label
                reasons.append("adopted magika classification due to high confidence")
                
        except Exception as exc:
            logger.debug("magika classification failed: %s", exc)

    return ClassificationResult(
        file_type=file_type,
        signature=sig,
        header_matched=header_matched,
        footer_matched=footer_matched,
        libmagic_description=libmagic_description,
        reasons=reasons,
    )
