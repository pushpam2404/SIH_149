# Integrated Secure Data Erasure & Advanced File Recovery Tool

SIH Problem Statement 26149 (NTRO) — one desktop app that combines secure
drive/file erasure with forensic file carving and recovery. Every action is
recorded in a tamper-evident, hash-chained audit log and exported as PDF/JSON
reports.

**This is a hackathon prototype, not a certified product.** We've tried to
state exactly what works, what doesn't, and what we haven't tested. See
[What we claim and don't](#what-we-claim-and-dont) and
[docs/compliance_mapping.md](docs/compliance_mapping.md).

## Why this matters

Investigators currently use one tool to destroy data and a different one to
recover it, with no shared, verifiable record connecting the two. This tool
puts both workflows behind one hash-chained audit log, so every erase and
every recovery scan can be checked afterwards. It can also produce a
certificate structured after India's BSA 2023 Section 63 electronic-evidence
certificate.

## Modules

1. **Secure Drive Eraser** — wipes disk images and external/removable drives
   (the system drive is always blocked) using single-pass, NIST 800-88 Clear,
   or DoD 5220.22-M overwrite, with sampled read-back verification after each
   pass. Simulation mode is on by default.
2. **Secure File & Folder Eraser** — overwrite, rename to a random name, clear
   extended attributes, unlink; batch and folder support; filesystem-specific
   warnings (APFS copy-on-write and snapshots, NTFS MFT, ext4 journal).
3. **File Carving & Recovery** — pytsk3 (filesystem-aware), PhotoRec
   (signature carving) and bulk_extractor (PII/metadata artifacts), with file
   type classification (signature table, libmagic, Magika), a 0–100
   confidence score, SHA-256 and fuzzy hashes, and cross-engine agreement.
4. **Audit & Reporting** — SHA-256 hash chain with per-entry HMAC tags and
   append-only database triggers, a chain verification button, PDF/JSON
   reports, and JSON certificates.

## What we claim and don't

| ✅ Works (tested) | ⚠️ Works with caveats | ❌ Not done |
|---|---|---|
| Simulation-mode erase of disk images, verified | Erase verification reads a **sample** of blocks (100% at 64 MB, 6% at 1 GB, 0.2% at 1 TB) | NIST 800-88 **Purge** / firmware Secure Erase (commands generated, never run) |
| System drive blocked from erasure | Overwrite does **not** guarantee physical erasure on SSDs, flash or APFS | A recorded erase test on a physical drive |
| File overwrite + rename + xattr clear + unlink | Audit HMAC key is a **hardcoded dev default** — no real protection in this build | Linux / Windows testing (code exists, never run) |
| Deleted-file recovery, byte-exact, on a FAT image (via pytsk3) | Tamper-*evident*, not tamper-*proof*: detects edits, can't prevent them | Partition-table recovery (TestDisk not wired) |
| Hash-chain tamper detection | Certificate follows BSA Sec. 63 structure; **not legally reviewed, not signed** | Trusted (RFC 3161) timestamping in the app flow |
| 29 automated tests passing | Confidence scores are uncalibrated heuristics | Recovery-rate measurement on a real forensic corpus |
| | bulk_extractor untested (not installed on our dev machine) | Gap carving for fragments PhotoRec can't map |
| | Fuzzy hashes skipped for files > 4 MiB (pure-Python hashing is too slow) | A test showing a deleted file carved *without* filesystem metadata |
| | File eraser costs ~0.23 s per file in filesystem checks | |

## Benchmarks (Apple M4, disk images on internal SSD)

Median of 3 runs, measured 2026-09-17:

| Operation | Result |
|---|---|
| NIST 800-88 Clear, 512 MB image (incl. verification) | 2.2 s |
| DoD 5220.22-M, 512 MB image | 11.4 s |
| File eraser, 100 × 64 KB files | 23.4 s (~0.23 s/file — slow, see docs) |
| Recovery scan, 128 MB FAT image — pytsk3 | 0.06 s, deleted file recovered 3/3 |
| Recovery scan, 128 MB FAT image — PhotoRec | 0.68 s, deleted text file recovered **0/3** (no signature to carve) |

These measure software overhead on a fast internal SSD. A physical USB
drive will be limited by its own write speed. Full tables, methodology and
caveats: [docs/performance_evaluation.md](docs/performance_evaluation.md).
Reproduce with `.venv/bin/python -m scripts.benchmark`.

## Setup

Tested on macOS only.

```bash
./scripts/setup_env.sh            # sleuthkit, testdisk, libmagic, optional bulk_extractor
python3.11 -m venv .venv          # 3.11/3.12; newer Pythons may lack pytsk3 wheels
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python -m app.main
```

## Test

```bash
.venv/bin/python -m pytest tests/
```

29 tests, about 6 seconds. The recovery integration test needs macOS
`hdiutil`/`diskutil` and is skipped elsewhere.

## Safety notes

- Drive erasure defaults to **simulation mode**, which wipes a scratch copy of
  a disk image. Simulation mode cannot target a real device.
- Only disk images and drives the OS reports as external/removable can be
  selected. The system drive never can. **Any external drive can be**, so
  check the name and size before confirming.
- Firmware-level (NVMe/ATA) sanitize commands are generated as reference
  strings only and never executed.

## Documentation

- [Beginner's guide](docs/beginners_guide.md) — plain-English walkthrough: erase a file, then try to recover it
- [User manual](docs/user_manual.md)
- [Technical documentation](docs/technical_documentation.md) — architecture, per-component status, platform matrix
- [Validation & testing](docs/validation_testing.md) — what is and isn't tested
- [Performance evaluation](docs/performance_evaluation.md) — measured benchmarks
- [Compliance mapping](docs/compliance_mapping.md) — claims register
