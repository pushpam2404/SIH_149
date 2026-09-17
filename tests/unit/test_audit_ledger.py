import json
import sqlite3

import pytest

from app.core.audit.ledger import AuditLedger


@pytest.fixture()
def ledger(tmp_path):
    led = AuditLedger(tmp_path / "audit.sqlite3")
    yield led
    led.close()


def test_empty_chain_is_valid(ledger):
    result = ledger.verify_chain()
    assert result.ok
    assert result.entries_checked == 0


def test_appended_entries_form_a_valid_chain(ledger):
    ledger.append_entry("file_erase", "/tmp/a.txt", {"standard": "single_pass_zero"})
    ledger.append_entry("file_erase", "/tmp/b.txt", {"standard": "single_pass_zero"})
    ledger.append_entry("recovery_scan", "image.img", {"candidates_found": 3})

    entries = ledger.get_entries()
    assert len(entries) == 3
    assert entries[0].prev_hash == "0" * 64
    assert entries[1].prev_hash == entries[0].entry_hash
    assert entries[2].prev_hash == entries[1].entry_hash

    result = ledger.verify_chain()
    assert result.ok
    assert result.entries_checked == 3


def test_tampering_with_a_past_entry_is_detected(ledger, tmp_path):
    ledger.append_entry("file_erase", "/tmp/a.txt", {"standard": "single_pass_zero"})
    ledger.append_entry("file_erase", "/tmp/b.txt", {"standard": "single_pass_zero"})
    ledger.close()

    db_path = tmp_path / "audit.sqlite3"
    conn = sqlite3.connect(str(db_path))
    # The append-only triggers block UPDATE through normal SQL (see
    # docs/BACKLOG_PLATFORM_QUALITY.md item P4) — drop them here to simulate
    # an attacker with direct file-level access bypassing that app-level
    # control, which is the documented limitation verify_chain() still has
    # to catch via the hash chain itself.
    conn.execute("DROP TRIGGER IF EXISTS prevent_audit_update")
    conn.execute(
        "UPDATE audit_entries SET payload = ? WHERE entry_id = 1",
        (json.dumps({"standard": "TAMPERED"}),),
    )
    conn.commit()
    conn.close()

    reopened = AuditLedger(db_path)
    result = reopened.verify_chain()
    reopened.close()

    assert not result.ok
    assert result.broken_at_entry_id == 1
    assert "modified" in result.reason


def test_ledger_created_before_mac_tags_still_opens_and_verifies(tmp_path):
    db_path = tmp_path / "old_audit.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE audit_entries (entry_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, "
        "actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, payload TEXT NOT NULL, "
        "prev_hash TEXT NOT NULL, entry_hash TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()

    ledger = AuditLedger(db_path)
    ledger.append_entry("file_erase", "/tmp/a.txt", {"standard": "single_pass_zero"})
    result = ledger.verify_chain()
    ledger.close()

    assert result.ok
    assert result.entries_checked == 1
