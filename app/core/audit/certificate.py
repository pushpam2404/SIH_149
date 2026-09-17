import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from app.core.audit.ledger import AuditLedger

_LIMITATIONS = [
    "Structure is modelled on the BSA 2023 Section 63 certificate (custodian + "
    "audit trail); it has not been reviewed by a legal professional and is not "
    "by itself admissible evidence.",
    "Erasure is software overwrite (NIST SP 800-88 Clear level at most). No "
    "Purge-level or firmware sanitize command (ATA/NVMe, IEEE 2883) was executed.",
    "On SSDs and copy-on-write filesystems, overwrite does not guarantee the "
    "original physical blocks were destroyed.",
    "integrity_digest is an unkeyed SHA-384 digest: it detects accidental or "
    "naive edits, but anyone can recompute it. It is not a digital signature.",
]


class CertificateGenerator:
    """Generates a JSON erasure/recovery certificate, structured after BSA Section 63."""

    def __init__(self, ledger: AuditLedger, operator_name: str, org_name: str):
        self.ledger = ledger
        self.operator_name = operator_name
        self.org_name = org_name

    def generate_json_certificate(self, target_device: str, wipe_status: str, out_path: Path) -> dict:
        entries = self.ledger.get_entries()
        device_entries = [e for e in entries if e.target == target_device]
        chain = self.ledger.verify_chain()

        cert_data = {
            "certificate_id": f"CERT-{hashlib.sha256(datetime.now().isoformat().encode()).hexdigest()[:12].upper()}",
            "issue_date": datetime.now(timezone.utc).isoformat(),
            "format": "Modelled on BSA 2023 Section 63 certificate structure (not legally reviewed)",
            "operator": {
                "name": self.operator_name,
                "organization": self.org_name
            },
            "device": {
                "target": target_device,
                "status_as_entered_by_operator": wipe_status
            },
            "audit_chain_verified_at_issue": chain.ok,
            "audit_trail": [
                {
                    "action": e.action,
                    "timestamp": e.timestamp,
                    "entry_hash": e.entry_hash,
                    "result": e.payload.get("result"),
                    "standard": e.payload.get("standard"),
                }
                for e in device_entries
            ],
            "limitations": _LIMITATIONS,
        }

        cert_json = json.dumps(cert_data, sort_keys=True)
        final_cert = {
            "certificate": cert_data,
            "integrity_digest": hashlib.sha384(cert_json.encode("utf-8")).hexdigest(),
            "integrity_digest_algorithm": "SHA-384 over sorted certificate JSON (unkeyed, not a signature)",
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_cert, f, indent=4)

        return final_cert
