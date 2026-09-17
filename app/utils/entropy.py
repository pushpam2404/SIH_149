"""Byte-distribution statistics used by the post-wipe verifier.

Two questions matter after an overwrite pass:
  1. Is this block uniformly the fill byte we expect (zero-fill passes)?
  2. If it was a random-fill pass, does the block actually look random
     (high entropy, flat byte-frequency distribution) rather than, say,
     still containing structured leftover data?
"""
from __future__ import annotations

import math
from collections import Counter


def shannon_entropy(data: bytes) -> float:
    """Shannon entropy in bits/byte, 0.0 (uniform single value) to 8.0 (fully random)."""
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def chi_square_uniformity(data: bytes) -> float:
    """Chi-square statistic testing byte values against a uniform distribution.

    Lower values indicate a distribution closer to uniform (i.e. more
    consistent with genuine random fill). This is a descriptive statistic
    for the report, not a strict pass/fail threshold on its own.
    """
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    expected = length / 256.0
    chi_square = 0.0
    for byte_value in range(256):
        observed = counts.get(byte_value, 0)
        chi_square += (observed - expected) ** 2 / expected
    return chi_square


def is_constant_fill(data: bytes, fill_byte: int) -> bool:
    """True if every byte in data equals fill_byte (expected after a zero/0xFF pass)."""
    if not data:
        return True
    return data.count(fill_byte) == len(data)


def looks_random(data: bytes, min_entropy: float = 7.5) -> bool:
    """Heuristic: a block from a genuinely random-fill pass should be near-max entropy."""
    return shannon_entropy(data) >= min_entropy
