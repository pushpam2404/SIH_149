"""Machine-readable JSON export of a Report."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from app.core.reporting.report_builder import Report


def to_dict(report: Report) -> dict:
    return dataclasses.asdict(report)


def to_json(report: Report) -> str:
    return json.dumps(to_dict(report), indent=2, sort_keys=False, default=str)


def save_json(report: Report, path: str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(report), encoding="utf-8")
    return out
