"""Post-wipe verification: sample sector read-back + entropy/pattern check.

Never claims success without actually reading data back — see the plan's
verification requirement that a wipe must be able to FAIL visibly.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import BinaryIO

from app.config.constants import (
    CHUNK_SIZE,
    VERIFY_SAMPLE_MAX_BLOCKS,
    VERIFY_SAMPLE_MIN_BLOCKS,
    VERIFY_SAMPLE_FRACTION,
)
from app.core.erasure.standards.base import FillMode
from app.utils.entropy import is_constant_fill, looks_random, shannon_entropy


@dataclass
class SampleResult:
    offset: int
    passed: bool
    entropy: float


@dataclass
class VerificationResult:
    ok: bool
    fill_mode: FillMode
    samples_checked: int
    failures: list[SampleResult] = field(default_factory=list)


def _sample_offsets(total_size: int, block_size: int) -> list[int]:
    num_blocks = max(1, total_size // block_size)
    sample_count = min(
        VERIFY_SAMPLE_MAX_BLOCKS,
        max(VERIFY_SAMPLE_MIN_BLOCKS, int(num_blocks * VERIFY_SAMPLE_FRACTION)),
    )
    sample_count = min(sample_count, num_blocks)
    block_indices = random.sample(range(num_blocks), sample_count)
    return sorted(i * block_size for i in block_indices)


def verify_pass(
    file_obj: BinaryIO,
    total_size: int,
    fill: FillMode,
    block_size: int = CHUNK_SIZE,
) -> VerificationResult:
    offsets = _sample_offsets(total_size, block_size)
    failures: list[SampleResult] = []
    for offset in offsets:
        file_obj.seek(offset)
        length = min(block_size, total_size - offset)
        data = file_obj.read(length)
        entropy = shannon_entropy(data)
        if fill == "zero":
            passed = is_constant_fill(data, 0x00)
        elif fill == "ones":
            passed = is_constant_fill(data, 0xFF)
        else:  # random
            passed = looks_random(data)
        if not passed:
            failures.append(SampleResult(offset=offset, passed=False, entropy=entropy))
    return VerificationResult(
        ok=not failures,
        fill_mode=fill,
        samples_checked=len(offsets),
        failures=failures,
    )
