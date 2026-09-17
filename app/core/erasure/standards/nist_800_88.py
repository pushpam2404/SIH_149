from __future__ import annotations

from app.config.constants import STANDARD_NIST_800_88_CLEAR
from app.core.erasure.standards.base import Pass, WipeStandard


class NIST80088Clear(WipeStandard):
    """NIST SP 800-88 Rev.1 "Clear" — single overwrite pass.

    NOTE: this implements "Clear" only. "Purge" requires media-native
    commands (ATA Secure Erase/Sanitize, NVMe Format/Sanitize) that act
    below the filesystem/OS write path and are out of scope for this
    MVP — see docs/compliance_mapping.md.
    """

    id = STANDARD_NIST_800_88_CLEAR
    display_name = "NIST SP 800-88 Rev.1 — Clear"
    reference = "NIST SP 800-88 Rev.1, Table A-1 (Clear)"

    @property
    def passes(self) -> list[Pass]:
        return [Pass("single overwrite pass (NIST 800-88 Clear)", "zero")]
