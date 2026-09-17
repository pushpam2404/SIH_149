# User Manual

## Introduction & Scope

This tool combines secure drive erasure, secure file/folder erasure, and
forensic file recovery in one desktop application. Every action is
recorded in a tamper-evident audit log and can be exported as a PDF/JSON
report.

It is a **hackathon prototype**, not a certified sanitization or forensic
product. Read [compliance_mapping.md](compliance_mapping.md) before
relying on it for anything beyond evaluation. In short:
- Erasure is software overwrite (NIST 800-88 Clear level at most). It does
  not guarantee physical destruction on SSDs, USB flash drives or memory
  cards.
- Recovery results and confidence scores are triage aids, not certified
  findings.
- Certificates follow the structure of a BSA Section 63 certificate but
  are not legally reviewed or digitally signed.

## Installation & System Requirements

- **macOS** is the only platform this build has been tested on. Linux and
  Windows code paths exist but are untested (see
  `technical_documentation.md`, Platform Support Matrix).
- Python 3.11 or 3.12 (newer interpreters may lack `pytsk3` wheels).
- Run `./scripts/setup_env.sh` to install `sleuthkit`, `testdisk`,
  `libmagic`, and (optionally) `bulk_extractor`, then
  `pip install -r requirements.txt`.
- Optional components and what you lose without them:

| Component | If missing |
|---|---|
| `pytsk3` | No filesystem-aware recovery; only PhotoRec carving |
| `photorec` | No signature carving; only filesystem-aware recovery |
| `bulk_extractor` | The PII / Metadata Artifacts table stays empty |
| `python-magic`, `magika` | Classification uses only the built-in signature table |
| `ppdeep` | Fuzzy hash column shows N/A |

The app keeps running when these are missing and lists unavailable
engines at the end of a scan.

## Safety Model — What This Tool Will and Won't Wipe

The Drive Eraser only allows two kinds of target:
1. A disk image file you select (e.g. `.img`, `.dd`).
2. A drive the operating system reports as external/removable.

Your internal system/boot drive is **never** a valid target. The device
table shows it as `BLOCKED`, and the same check runs in
`app/core/devices/safety.py` before any write, even if the GUI were
bypassed.

**Be careful:** any external drive the OS reports as removable *is*
allowed, including one holding data you care about. The type-to-confirm
dialog is the only thing between you and a wipe. Double-check the device
name and size.

**Simulation mode** (on by default) makes a disk-image erase run on a
scratch copy, leaving your original file untouched. Simulation mode
cannot be used on a real device; turn it off explicitly for real hardware.

## Module 1: Drive Eraser

1. Open the **Drive Eraser** tab. Click **Refresh Devices** to list
   attached drives, or **Select Disk Image File...** to pick an image.
2. Select a row. Only rows marked `SAFE` can be erased.
3. Choose a wipe standard (single pass zero/random, NIST 800-88 Clear, or
   DoD 5220.22-M) and check the Simulation Mode box is set as you intend.
4. Click **Erase Selected Target**, type the confirmation code, tick the
   acknowledgment box, and confirm.
5. Progress and per-pass verification results appear in the log panel.
   A PDF and JSON report are written to `reports/`.

What "PASS" means: every pass completed and a random sample of blocks read
back with the expected pattern. It does **not** mean every block was
checked (see the coverage table in `technical_documentation.md`), and on
SSDs it does not mean the physical flash cells were erased.

Real drives are erased at the drive's own write speed. A 64 GB USB stick
at a typical 20–30 MB/s takes roughly 35–55 minutes per pass, so
DoD 5220.22-M takes about three times that.

## Module 2: File & Folder Eraser

1. Open the **File & Folder Eraser** tab.
2. **Add Files...** for individual files, or **Add Folder...** to queue an
   entire folder (its contents are erased and the folder removed).
3. Click **Securely Erase Queue**, confirm, and watch progress. Expect
   roughly a quarter of a second per file even for tiny files (filesystem
   checks run for each one).
4. If the filesystem can keep old copies of data, a **"Erase Complete with
   Filesystem Warnings"** dialog lists why (for example, APFS copy-on-write
   or local snapshots). These warnings are also stored in the audit log.
5. A report lists per-file PASS/FAIL, bytes overwritten, and whether
   extended attributes were cleared.

What this does **not** remove: APFS snapshots and Time Machine backups,
filesystem journal records, Spotlight/QuickLook caches, cloud-synced
copies, or copies elsewhere on disk. On macOS (APFS) the overwrite most
likely lands on new blocks, so treat file erasure there as "deleted and
renamed with metadata stripped", not "physically overwritten".

## Module 3: Recovery

1. Open the **Recovery** tab. Browse to a disk image, or pick an attached
   device from the dropdown.
2. Click **Start Recovery Scan**. Installed engines run in turn: pytsk3
   (filesystem-aware), PhotoRec (signature carving), bulk_extractor
   (PII/metadata artifacts).
3. **Recovered Files** table: name, engine, file type, size, confidence
   score (0–100 with high/medium/low), fragmentation flag, SHA-256, and
   fuzzy hash ("skipped (>4 MiB)" for large files, to keep scans fast).
4. **PII / Metadata Artifacts** table (bulk_extractor only): click a row to
   preview the extracted feature file (for example, email addresses).
5. Select a recovered file and click **Export Selected File...**, or click
   **Generate Forensic Report** for a PDF/JSON report.

How to read the results:
- **Confidence** ranks candidates *within this scan*. A score of 80 is not
  "80% likely genuine", and scores from different scans are not comparable.
- **Fragmented = yes** means PhotoRec found the file in several pieces and
  the tool rebuilt it from PhotoRec's map. Fragmented files are more
  likely to be partly corrupt; open them before relying on them.
- PhotoRec carves by file signature. Files without one (plain text, many
  logs and configs) are only found by pytsk3, which needs the filesystem
  structure to still exist.
- The same file often appears twice (once per engine). Identical SHA-256
  values across engines raise the confidence score.
- Scans take time: PhotoRec reads the whole image, and a multi-gigabyte
  device can take many minutes. See `performance_evaluation.md`.

**Evidence handling:** the tool only reads the source, but it does not
enforce read-only access. For real evidence, scan a forensic image or use
a hardware write-blocker.

## Audit Log, Certificates & Reports

- The **Audit Log** tab lists every logged action with its hash.
- **Verify Chain Integrity** recomputes every entry's hash, chain link and
  MAC tag, and names the first entry that fails. It *detects* tampering
  after the fact; it cannot prevent someone with file access from
  changing the database.
- **Generate Certificate (Sec. 63-style)** asks for a target, operator
  name, organization, and the wipe status, then saves a JSON certificate
  with that target's audit entries and an embedded list of limitations.
  Enter a wipe status you have actually verified; the tool does not check
  what you type against the audit result.
- The **Reports** tab lists generated PDFs; select one and click
  **Open PDF**.

Timestamps come from this computer's clock. No trusted timestamping
authority is used.

## Simulation Mode Guide

Simulation mode lets you demo the Drive Eraser repeatedly without a fresh
USB stick. Pick or create a disk image (e.g. with `dd` or Disk Utility),
leave Simulation Mode checked, and each run wipes a fresh scratch copy
while the source image stays intact. Simulation runs are labelled
"SIMULATION MODE" in their reports.

## Troubleshooting

- **"unknown wipe standard"** — the standard ID isn't registered in
  `app/core/erasure/standards/__init__.py`. Shouldn't happen through the GUI.
- **Recovery finds 0 candidates** — check the scan result message or the
  audit entry for `engines_unavailable`. If both `pytsk3` and `photorec`
  are listed, no engine ran; re-run `setup_env.sh`. A genuinely wiped or
  empty image also returns 0.
- **Artifacts table is empty** — `bulk_extractor` is not installed, or the
  image contained no emails/URLs/other features.
- **Device table is empty** — device enumeration failed (see terminal
  output). On macOS this usually means `diskutil` isn't on PATH.
- **Real device erase fails with a permission error** — raw device writes
  need elevated permissions.

## FAQ

**Q: Can this permanently sanitize an SSD?**
A: No. It performs verified overwrite passes, which can leave data in
remapped or over-provisioned flash cells. That needs firmware-level
sanitize commands, which this tool does not run.

**Q: Is the certificate legally valid?**
A: Not on its own. It follows the structure of a BSA 2023 Section 63
certificate, but it has not been legally reviewed and is not digitally
signed.

**Q: Can the audit log be faked?**
A: Edits are detected by Verify Chain Integrity. However, in this build the
MAC key is a hardcoded development default, so someone with the source
code and the database file could rebuild a fully consistent fake log.

**Q: Does recovery modify the source device/image?**
A: The engines only read from the source and write recovered files to a
separate output directory. Read-only access is not enforced by the OS, so
use a write-blocker or a read-only image for real evidence.
