"""SQLite-backed, append-only persistence for the audit ledger.

WAL mode is used for durability/concurrency. Triggers reject UPDATE and
DELETE through ordinary SQL; someone with file access can still drop them,
which is why verify_chain() re-checks the hash chain.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.core.audit.models import AuditEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    mac_tag TEXT
);

CREATE TRIGGER IF NOT EXISTS prevent_audit_update
BEFORE UPDATE ON audit_entries
BEGIN
    SELECT RAISE(ABORT, 'audit_entries is append-only');
END;

CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
BEFORE DELETE ON audit_entries
BEGIN
    SELECT RAISE(ABORT, 'audit_entries is append-only');
END;
"""


class AuditStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(_SCHEMA)
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(audit_entries)")}
        if "mac_tag" not in columns:
            # Ledgers created before HMAC tags existed; old rows keep mac_tag NULL.
            self._conn.execute("ALTER TABLE audit_entries ADD COLUMN mac_tag TEXT")
        self._conn.commit()

    def append(self, entry: AuditEntry) -> AuditEntry:
        cur = self._conn.execute(
            "INSERT INTO audit_entries (timestamp, actor, action, target, payload, prev_hash, entry_hash, mac_tag) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.timestamp,
                entry.actor,
                entry.action,
                entry.target,
                json.dumps(entry.payload, sort_keys=True),
                entry.prev_hash,
                entry.entry_hash,
                entry.mac_tag,
            ),
        )
        self._conn.commit()
        return AuditEntry(
            entry_id=cur.lastrowid,
            timestamp=entry.timestamp,
            actor=entry.actor,
            action=entry.action,
            target=entry.target,
            payload=entry.payload,
            prev_hash=entry.prev_hash,
            entry_hash=entry.entry_hash,
            mac_tag=entry.mac_tag,
        )

    def all_entries(self) -> list[AuditEntry]:
        rows = self._conn.execute(
            "SELECT entry_id, timestamp, actor, action, target, payload, prev_hash, entry_hash, mac_tag "
            "FROM audit_entries ORDER BY entry_id ASC"
        ).fetchall()
        return [
            AuditEntry(
                entry_id=row[0],
                timestamp=row[1],
                actor=row[2],
                action=row[3],
                target=row[4],
                payload=json.loads(row[5]),
                prev_hash=row[6],
                entry_hash=row[7],
                mac_tag=row[8],
            )
            for row in rows
        ]

    def last_entry(self) -> AuditEntry | None:
        row = self._conn.execute(
            "SELECT entry_id, timestamp, actor, action, target, payload, prev_hash, entry_hash, mac_tag "
            "FROM audit_entries ORDER BY entry_id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return AuditEntry(
            entry_id=row[0],
            timestamp=row[1],
            actor=row[2],
            action=row[3],
            target=row[4],
            payload=json.loads(row[5]),
            prev_hash=row[6],
            entry_hash=row[7],
            mac_tag=row[8],
        )

    def close(self) -> None:
        self._conn.close()
