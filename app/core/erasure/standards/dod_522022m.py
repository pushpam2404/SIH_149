from __future__ import annotations

from app.config.constants import STANDARD_DOD_5220_22_M
from app.core.erasure.standards.base import Pass, WipeStandard


class DoD522022M(WipeStandard):
    """DoD 5220.22-M three-pass overwrite: 0x00, 0xFF, random."""

    id = STANDARD_DOD_5220_22_M
    display_name = "DoD 5220.22-M (3-pass)"
    reference = "DoD 5220.22-M"

    @property
    def passes(self) -> list[Pass]:
        return [
            Pass("pass 1 of 3: 0x00 fill", "zero"),
            Pass("pass 2 of 3: 0xFF fill", "ones"),
            Pass("pass 3 of 3: random fill", "random"),
        ]
