"""0-100 confidence scoring for a recovered file candidate.

Weighted from: signature header match, footer/completeness, size sanity,
fragmentation state, and cross-engine agreement (when both pytsk3 and
PhotoRec independently recovered overlapping data). This is a heuristic
score for triage, not a certified probability.
"""
from __future__ import annotations

from app.config.constants import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM
from app.core.recovery.classifier import ClassificationResult
from app.core.recovery.engine_base import RecoveredFileCandidate


def score_candidate(
    classification: ClassificationResult,
    candidate: RecoveredFileCandidate,
    cross_engine_agreement: bool = False,
) -> tuple[int, list[str]]:
    total = 0
    reasons: list[str] = []

    if classification.header_matched:
        total += 40
        reasons.append("+40 header signature matched")
    else:
        reasons.append("+0 no header signature matched")

    if classification.signature is not None and classification.signature.footer is not None:
        if classification.footer_matched:
            total += 25
            reasons.append("+25 footer marker present (file likely complete)")
        else:
            total -= 10
            reasons.append("-10 footer marker missing (possible truncation)")
    elif classification.header_matched:
        total += 10
        reasons.append("+10 header matched, no footer expected for this type")

    if candidate.size_bytes > 0:
        total += 10
        reasons.append("+10 non-zero recovered size")
    else:
        reasons.append("+0 zero-byte candidate")

    if candidate.is_fragmented:
        total -= 15
        reasons.append("-15 fragmented/reconstructed from multiple runs")
    else:
        total += 10
        reasons.append("+10 recovered as a contiguous block")

    if cross_engine_agreement:
        total += 15
        reasons.append("+15 independently confirmed by a second recovery engine")

    return max(0, min(100, total)), reasons


def confidence_label(score: int) -> str:
    if score >= CONFIDENCE_HIGH:
        return "high"
    if score >= CONFIDENCE_MEDIUM:
        return "medium"
    return "low"
