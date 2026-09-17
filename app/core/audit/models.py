"""Audit ledger data model.

Each AuditEntry links to the previous entry's hash, forming a hash chain:
tampering with (or deleting/reordering) any past entry changes its hash,
which breaks every subsequent link. verify_chain() in ledger.py walks the
chain and reports exactly where it breaks.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64


def _canonical_json(obj: dict) -> str:
    """Deterministic JSON encoding so the same logical entry always hashes the same."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class AuditEntry:
    entry_id: int | None  # None until persisted (sqlite assigns the id)
    timestamp: str  # ISO-8601 UTC
    actor: str  # e.g. "user", "system"
    action: str  # one of app.config.constants ACTION_* values
    target: str  # human-readable target description (device id, file path, report id)
    payload: dict  # action-specific structured details (standard used, result, etc.)
    prev_hash: str
    entry_hash: str = field(default="")
    mac_tag: str | None = field(default=None)

    @staticmethod
    def create(action: str, target: str, payload: dict, actor: str, prev_hash: str) -> "AuditEntry":
        timestamp = datetime.now(timezone.utc).isoformat()
        base = {
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "target": target,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        entry_hash = hashlib.sha256(_canonical_json(base).encode("utf-8")).hexdigest()
        return AuditEntry(
            entry_id=None,
            timestamp=timestamp,
            actor=actor,
            action=action,
            target=target,
            payload=payload,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            mac_tag=None,
        )

    def recompute_hash(self) -> str:
        """Recomputes the hash from this entry's own fields — used by verify_chain()."""
        base = {
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
        }
        return hashlib.sha256(_canonical_json(base).encode("utf-8")).hexdigest()
