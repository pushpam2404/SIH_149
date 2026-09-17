# Compliance Mapping & Claims Register

This document states plainly what this tool does and does not claim. It
exists so the gap between "a standard's procedure is implemented" and
"certified compliant" is never ambiguous to a user, judge, or auditor.

**Ground rules we hold ourselves to:**
- We say "implements the procedure of X", never "certified/compliant with X",
  unless an accredited body has certified it. None has.
- Every limitation below is also stated in the reports and certificates the
  tool generates, not only in this document.
- If a feature is simulated, unwired, or untested, we say so.

## Claims Register

| We claim | We do NOT claim |
|---|---|
| Overwrite procedures of NIST SP 800-88 Rev.1 **Clear** and DoD 5220.22-M (3-pass) are implemented and verified by sampled read-back | NIST 800-88 **Purge** or **Destroy**; IEEE 2883 sanitization; any certification |
| Overwrites every *logical* sector of the target | Physical destruction of data on SSDs, flash, or copy-on-write filesystems |
| File eraser overwrites content, renames to a random name, clears extended attributes, then unlinks | Removal of every trace: journal entries, snapshots, filesystem free-space remnants, backups, cloud copies |
| The audit log is hash-chained; `verify_chain()` detects modified, deleted, or reordered entries | That tampering is *impossible* — someone who can rewrite the whole database and knows the MAC key can rebuild a valid chain |
| Recovered files are SHA-256 hashed at recovery time | Formal forensic certification (ISO/IEC 27037, NIST CFTT), write-blocker enforcement |
| Certificates are *structured after* the BSA 2023 Section 63 certificate | Legal admissibility, legal review, or a digital signature |
| Confidence score ranks candidates within one scan | That the score is a calibrated probability |

## NIST SP 800-88 Rev.1

| Level | Status | Notes |
|---|---|---|
| **Clear** | Procedure implemented | `app/core/erasure/standards/nist_800_88.py` — one overwrite pass, verified by random sampled read-back (`app/core/erasure/verifier.py`). Verification samples 1% of blocks (min 16, max 512), **not** every block. |
| **Purge** | Not implemented | Needs drive-native commands (ATA Secure Erase/Sanitize, NVMe Format/Sanitize). `app/core/erasure/firmware_sanitize.py` only *generates* these command strings; it never runs them, and no GUI path calls it. A malformed or interrupted firmware command can brick a drive, which is not acceptable in a demo tool. |
| **Destroy** | Not implemented | Physical destruction is outside any software tool's scope. |

## DoD 5220.22-M

Implemented as the classic 3-pass overwrite (0x00, 0xFF, random) in
`app/core/erasure/standards/dod_522022m.py`, with verification after each
pass. DoD 5220.22-M predates flash storage, and the DoD itself no longer
references it as a sanitization method; we include it because many
procurement checklists still ask for it. It is a Clear-equivalent
software overwrite with the same SSD caveat below.

## The SSD / Wear-Leveling Caveat (applies to every overwrite standard)

On an SSD, the flash translation layer (FTL) remaps logical sectors to
physical NAND cells. An OS-level overwrite may land on a *different*
physical cell than the one holding the original data, leaving the original
physically intact and potentially recoverable via chip-off or direct NAND
access. Over-provisioned and retired blocks are never reachable by an
OS-level write at all. This is a property of all overwrite-based wiping on
flash, not a bug specific to this tool.

**This tool does not claim physical-media-level destruction on SSDs,
USB flash drives, or memory cards.** Reports should be read as "logical
erasure with verified overwrite."

TRIM: after a file erase the tool attempts a best-effort `fstrim` on
Linux. On macOS it does nothing (no safe per-volume TRIM trigger is
available from user space), and on Windows it is not attempted.

## Secure File & Folder Eraser

The SSD caveat applies, and more strongly: copy-on-write filesystems
(APFS, Btrfs, ZFS) write an "overwrite" to new blocks by design, and APFS
local snapshots or Time Machine may retain earlier versions. The tool
detects the filesystem and shows specific warnings (APFS copy-on-write,
NTFS small files resident in the MFT, ext3/ext4 journaling) in the GUI and
the audit entry. It **warns only** — it never deletes snapshots or edits
the MFT/journal. Every file-erasure report states that the overwrite is
**best-effort logical erasure**.

Not cleared: filesystem journal entries, directory-entry slack, the
original file name in journal records, macOS Spotlight/QuickLook caches,
backups, and copies in other locations.

## Tamper-Evident Audit Ledger

| Mechanism | What it actually provides | Limitation |
|---|---|---|
| SHA-256 hash chain (`prev_hash` → `entry_hash`) | Detects edited, deleted, or reordered entries | An attacker who rewrites *every* entry from the tampered point onward can produce a self-consistent chain |
| Forward-secure HMAC tag per entry (key ratchets after each entry) | Makes the full-rewrite attack above require the key | The initial key is currently a **hardcoded development default** in `ledger.py`. Anyone with the source code has it, so in this build the MAC adds no protection against a knowledgeable attacker. A production build must load the key from a secure store. |
| SQLite triggers blocking `UPDATE`/`DELETE` | Stops accidental edits and edits made through ordinary SQL | Anyone with file access can drop the triggers or edit the file directly. The chain check is the real defense, and it only *detects* tampering after the fact. |
| Trusted timestamping (`timestamping.py`) | **Not active.** Code exists to request an RFC 3161 token from a public TSA, but nothing in the app calls it | Timestamps in the log come from the local system clock and can be wrong or altered |

"Blockchain & Cybersecurity" theme: this is a single-machine hash chain,
the core data structure a blockchain uses. There is no distributed
ledger, consensus, or external anchoring.

## Certificates (BSA 2023 Section 63-style)

The Audit Log page generates a JSON certificate for a chosen target. It
contains operator/organization details, the target's audit entries with
their hashes, whether the audit chain verified at issue time, and an
embedded `limitations` list.

- It is **structured after** the Section 63 certificate. It has not been
  reviewed by a lawyer, and generating it does not make evidence admissible.
- The operator types the wipe status. The tool does not derive it
  automatically, but the underlying audit entries (with PASS/FAIL and the
  standard used) are included so a reviewer can check it.
- `integrity_digest` is an **unkeyed** SHA-384 digest. It catches careless
  edits, but anyone can recompute it after changing the file. It is not a
  digital signature, and there is no PKI.

## Advanced File Carving and Recovery — Evidentiary Integrity

- Recovery engines only **read** the source. They do not enforce read-only
  access at the OS level, though — use a hardware write-blocker or a
  read-only image for real evidence.
- Every candidate is SHA-256 hashed when recovered, and reports carry a
  "do not modify" notice.
- The tool has **not** been validated against ISO/IEC 27037 or NIST CFTT.
  Those require process controls (write-blockers, custody procedures,
  examiner qualification) beyond a software tool.

## Summary Against the Problem Statement

| Requirement | Status |
|---|---|
| Compliance with data destruction standards | **Partial** — Clear-level overwrite procedures implemented; Purge not implemented; nothing certified |
| Tamper-resistant reporting | **Implemented as tamper-evident** (detects, does not prevent); MAC key hardcoded in this build |
| Preserving evidential integrity | **Partial** — hashing and read-only access by convention; no enforced write-blocking, not certified |
| Compliance with forensic standards | **Not claimed** |
