"""Wipe-standard interface. Each pass specifies how to fill each chunk.

Only overwrite-based ("Clear"-level) standards are implemented for this
MVP — true NIST 800-88 "Purge" (ATA Secure Erase/Sanitize firmware
commands) is out of scope; see docs/compliance_mapping.md for why.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

FillMode = Literal["zero", "ones", "random"]


@dataclass(frozen=True)
class Pass:
    label: str
    fill: FillMode


class WipeStandard(ABC):
    id: str
    display_name: str
    reference: str  # citation/standard name for reports

    @property
    @abstractmethod
    def passes(self) -> list[Pass]:
        ...
