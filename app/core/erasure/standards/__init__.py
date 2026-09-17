from __future__ import annotations

from app.core.erasure.standards.base import Pass, WipeStandard
from app.core.erasure.standards.dod_522022m import DoD522022M
from app.core.erasure.standards.nist_800_88 import NIST80088Clear
from app.core.erasure.standards.single_pass import SinglePassRandom, SinglePassZero

_REGISTRY: dict[str, WipeStandard] = {
    cls.id: cls()
    for cls in (SinglePassZero, SinglePassRandom, NIST80088Clear, DoD522022M)
}


def get_standard(standard_id: str) -> WipeStandard:
    try:
        return _REGISTRY[standard_id]
    except KeyError:
        raise ValueError(f"unknown wipe standard: {standard_id!r}") from None


def list_standards() -> list[WipeStandard]:
    return list(_REGISTRY.values())


__all__ = ["Pass", "WipeStandard", "get_standard", "list_standards"]
