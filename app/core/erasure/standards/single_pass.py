from __future__ import annotations

from app.config.constants import STANDARD_SINGLE_PASS_RANDOM, STANDARD_SINGLE_PASS_ZERO
from app.core.erasure.standards.base import Pass, WipeStandard


class SinglePassZero(WipeStandard):
    id = STANDARD_SINGLE_PASS_ZERO
    display_name = "Single Pass — Zero Fill"
    reference = "Generic single-pass overwrite"

    @property
    def passes(self) -> list[Pass]:
        return [Pass("zero-fill", "zero")]


class SinglePassRandom(WipeStandard):
    id = STANDARD_SINGLE_PASS_RANDOM
    display_name = "Single Pass — Random Fill"
    reference = "Generic single-pass overwrite"

    @property
    def passes(self) -> list[Pass]:
        return [Pass("random-fill", "random")]
