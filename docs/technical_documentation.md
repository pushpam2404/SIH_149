# Technical Documentation

Status labels used throughout: **Verified** (exercised by automated tests
or manual runs on real hardware), **Implemented, untested** (code exists
but has not been run on the target platform/tool), **Not wired** (code
exists but nothing in the app calls it), **Not implemented**.

## Architecture Overview

```
app/gui/     PySide6 views — no business logic; long jobs run on a QThread
             (app/gui/workers.py) so the UI thread never blocks on I/O.
app/core/    Pure Python, no Qt imports — independently testable.
  devices/   Cross-platform device enumeration + safe-target enforcement.
  erasure/   Wipe standards, chunked overwrite I/O, verification,
             filesystem-aware warnings, firmware command reference strings.
  recovery/  pytsk3, PhotoRec and bulk_extractor engines, classification
             (signatures + libmagic + Magika), confidence scoring, hashing.
  audit/     Hash-chained audit ledger (SQLite), HMAC tags, certificates.
  reporting/ Generic Report object -> PDF (reportlab) and JSON.
app/config/  Constants and runtime settings (paths, simulation-mode default).
app/utils/   Logging, entropy math, subprocess helpers.
scripts/     setup_env.sh (native deps), benchmark.py (performance numbers).
```

Every destructive action and every recovery scan calls
`AuditLedger.append_entry()`. This is enforced by code structure (the
orchestrators `drive_eraser.py`, `file_eraser.py` and `scan_service.py`
each log directly), not by any mechanism that makes bypassing it
impossible.

## Device Safety & System-Drive Detection — Verified (macOS)

`app/core/devices/backend_base.py` defines one normalized `DeviceInfo`
dataclass that every platform backend returns, so `safety.py` never has
to special-case platforms.

`safety.classify_target()` is **deny-list-first**. A target is allowed
only if it is:
1. a disk image file (`is_disk_image=True`), or
2. a device the backend positively identifies as removable/external AND
   not internal AND not the system container.

Anything else, including anything the backend can't classify, is denied.
On macOS, `MacOSDeviceBackend._is_system_container()` compares the disk
against `diskutil info -plist /`'s `ParentWholeDisk`, and treats the
device as the system drive if that lookup fails.

**Limitation:** "removable/external" comes from what the OS reports. An
external drive that happens to hold important data is still an allowed
target; the only protection there is the type-to-confirm dialog.

**A real bug caught during development:** `diskutil info -plist <id>`
requires `-plist` directly after `info`. The original code appended it
last, which silently broke `get_device_info()` for every real device.
Mocked unit tests did not catch it; running against real hardware did.

## Wipe Standards — Verified on disk images

`app/core/erasure/standards/`: single-pass zero, single-pass random,
NIST 800-88 Clear (one overwrite), DoD 5220.22-M (0x00, 0xFF, random).
See `compliance_mapping.md` for what these do and don't guarantee.

Verification (`app/core/erasure/verifier.py`) runs after **every** pass
and reads back a **random sample** of 4 MiB blocks — 1% of blocks, minimum
16, maximum 512 — checking for the expected constant fill (zero/ones
passes) or Shannon-entropy randomness (random passes). A failure is
reported and logged as FAIL.

**Limitation — sampling coverage:**

| Target size | 4 MiB blocks | Blocks read back | Coverage |
|---|---|---|---|
| 64 MiB | 16 | 16 | 100% |
| 256 MiB | 64 | 16 | 25% |
| 1 GiB | 256 | 16 | 6.25% |
| 64 GiB | 16,384 | 163 | 1% |
| 1 TiB | 262,144 | 512 (cap) | 0.2% |

A small region that was never written can go undetected on large
targets, and the random-fill check tests for high entropy, so a region
that still holds encrypted or compressed original data would also pass.
Full read-back verification is not implemented.

Real (non-image) device erasure goes through the same code path but raw
writes use a plain `open()`, which needs elevated permissions. No run
against a physical drive is recorded in `validation_testing.md`; all
automated tests use disk images.

## Filesystem-Aware File Erasure — Runs on APFS, warning text not tested

`app/core/erasure/fs_aware.py` detects the filesystem of a file before
erasing it and returns warnings shown in the GUI and stored in the audit
entry:
- APFS: copy-on-write warning, plus a count of local snapshots if any.
- NTFS: files under 1 KB may be resident in the MFT.
- ext3/ext4: journaling may keep fragments.

It only warns. It never deletes snapshots or edits filesystem metadata.
The checks spawn `df`/`stat`/`tmutil` for every file (~0.22 s per file
measured), which makes large batches of small files slow.
NTFS and ext4 detection is **implemented, untested** (development was
on macOS). `invoke_trim()` runs `fstrim` on Linux, does nothing on macOS,
and is not attempted on Windows.

## Firmware Sanitize — Not wired (on purpose)

`app/core/erasure/firmware_sanitize.py` builds NVMe Format and ATA
Secure Erase command strings for reference. It never executes them,
nothing in the app calls it, and its result is labelled "no Purge
performed".

## Hash-Chained Audit Ledger — Verified

Each `AuditEntry` (`app/core/audit/models.py`) stores `prev_hash` and
`entry_hash = SHA256(canonical_json({timestamp, actor, action, target,
payload, prev_hash}))`. `verify_chain()` checks, for every entry in order:
1. `prev_hash` equals the previous entry's `entry_hash` (catches deletion
   and reordering);
2. recomputing the hash matches the stored hash (catches edits);
3. the HMAC tag matches, using a key that is ratcheted forward (one-way
   hashed) after every entry.

`app/core/audit/store.py` adds SQLite triggers that reject `UPDATE` and
`DELETE` on the table.

Limitations:
- **The HMAC starting key is a hardcoded development default** (see
  `AuditLedger.__init__`). With the source code, anyone can recompute
  valid tags, so the MAC gives no real protection in this build.
- Triggers only stop ordinary SQL. Anyone with file access can drop them.
  The chain check *detects* tampering; nothing *prevents* it.
- Entries with no MAC tag (older databases) are skipped by the MAC check
  instead of being flagged.
- Timestamps come from the local clock. `timestamping.py` contains an
  RFC 3161 client (via `openssl ts` to freetsa.org, falling back to a
  local placeholder) but it is **not wired** — nothing calls
  `AuditLedger.timestamp_entry()`.
- This is a single-machine hash chain, not a distributed blockchain.

## Certificates — Verified (generation), not legally reviewed

`app/core/audit/certificate.py`, triggered from the Audit Log tab,
writes a JSON certificate *structured after* the BSA 2023 Section 63
certificate: operator, organization, target, the target's audit entries
(hash, result, standard), whether the chain verified at issue, and an
embedded `limitations` list. The wipe status is typed by the operator.
The `integrity_digest` is unkeyed SHA-384 — not a digital signature.
No automated test covers certificate generation yet.

## Recovery Engine Design

| Engine | Status | What it does |
|---|---|---|
| `TskEngine` (pytsk3 / Sleuth Kit) | Verified on FAT images | Walks filesystem metadata, finds unallocated (deleted) entries, reads them through the filesystem's own block map. Needs intact filesystem structures. |
| `PhotoRecEngine` | Runs on FAT images; **did not recover the deleted plain-text test file** (no signature), so carving is unverified | Signature carving with no filesystem needed. Driven through PhotoRec's **undocumented** `/cmd <image> search` mode (found by inspecting the binary), with `stdin=DEVNULL` so it can't block on a keypress. Parses the DFXML `report.xml`. Other `/cmd` argument combinations tried (partition selection, file-type filters) either errored or stalled, so only whole-image search is used. |
| `BulkExtractorEngine` | Implemented, **untested on the dev machine** (`bulk_extractor` is not installed there) | Runs `bulk_extractor` and lists each non-empty feature file (emails, URLs, etc.) as an artifact, shown in a separate GUI table. If the binary is missing the engine is skipped and the table stays empty. |
| `TestDiskEngine` | **Not wired** | `analyze_partitions()` exists but nothing calls it. There is no partition-table recovery in the app. |

**Fragmented files:** when PhotoRec's report lists more than one byte run
for a file, `reassembly.reassemble()` re-extracts it by concatenating
those runs in order. This relies entirely on PhotoRec's own fragment
detection. The bifragment gap-carving code in `reassembly.py` is disabled
(`attempt_gap_carving=False`) and untested. pytsk3 handles fragmentation
through the filesystem's block map.

**Classification** (`classifier.py`):
1. Our own magic-byte signature table (`signatures.py`) — primary, checks
   header and footer.
2. `python-magic` / libmagic cross-check — optional.
3. Magika (Google's ML file-type model) — optional. It is used **only when
   the signature table returns "unknown" and Magika's score is above 0.8**.
   Otherwise its label is recorded in the reasons but does not change the
   type.

**Confidence score** (`confidence.py`), 0–100: +40 header match, +25
footer match (−10 if expected but missing), +10 non-zero size, +10
contiguous (−15 fragmented), +15 cross-engine agreement (pytsk3 and
PhotoRec produced byte-identical files, compared by SHA-256). The weights
are hand-chosen to give a sensible ordering, **not calibrated** on a
labelled dataset.

**Hashing:** SHA-256 for integrity and `ppdeep` fuzzy hashes (CTPH) for
similarity. Fuzzy hashes are only computed for files up to 4 MiB, because
`ppdeep` is pure Python and took 10+ minutes on a 32 MB carved file.
Fuzzy hashes are displayed and stored, but the app has no "compare against
a known file" feature.

## Report Generation Pipeline

`report_builder.py` turns a `DriveEraseResult`, `BatchEraseResult`, or
`ScanSummary` into a generic `Report`. `json_report.py` and
`pdf_report.py` render it. PDF tables are capped at the first 200 rows per
section; the JSON export contains everything. Each report type carries a
notice (simulation mode, best-effort erasure, or evidentiary data).

## Platform Support Matrix

| Capability | macOS | Linux | Windows |
|---|---|---|---|
| Device enumeration | Verified (`diskutil -plist`) | Implemented, untested (`lsblk -J`) | Implemented, untested (PowerShell `Get-Disk`) |
| Raw device erase | Implemented; no recorded physical-drive run; needs elevated permissions | Implemented, untested | Implemented, untested; plain `open()` on `\\.\PhysicalDriveN` is unlikely to work for writes without volume locking |
| Disk image erase (simulation) | Verified | Should work (pure Python), untested | Should work (pure Python), untested |
| Test fixture image builder | Verified (`hdiutil`) | Not implemented | Not implemented |
| pytsk3 / PhotoRec recovery | Verified | Implemented, untested | Untested |
| bulk_extractor | Untested (not installed) | Untested | Untested |
| Filesystem warnings | APFS path runs during tests (output not asserted) | ext4 implemented, untested | NTFS implemented, untested |

## Known Gaps (not implemented)

- NIST 800-88 Purge (firmware sanitize execution) — deliberately excluded.
- Full read-back verification (only sampling).
- Partition-table recovery (TestDisk not wired).
- Gap carving for fragments PhotoRec can't map.
- Secure key storage for the audit HMAC key.
- Trusted timestamping in the app flow.
- Exporting the full audit ledger as a PDF/JSON document.
- Automated GUI tests.
