# Integrated Secure Data Erasure & Advanced File Recovery Tool

[![tests](https://github.com/pushpam2404/SIH_149/actions/workflows/tests.yml/badge.svg)](https://github.com/pushpam2404/SIH_149/actions/workflows/tests.yml)

SIH Problem Statement 26149 (NTRO) — one desktop app that combines secure
drive/file erasure with forensic file carving and recovery. Every action is
recorded in a tamper-evident, hash-chained audit log and exported as PDF/JSON
reports. Runs on **Windows, Linux and macOS**.

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
   warnings (APFS/ReFS/Btrfs copy-on-write, NTFS MFT and shadow copies, ext4
   journal, FAT file names).
3. **File Carving & Recovery** — pytsk3 (filesystem-aware), PhotoRec
   (signature carving) and bulk_extractor (PII/metadata artifacts), with file
   type classification (signature table, libmagic, Magika), a 0–100
   confidence score, SHA-256 and fuzzy hashes, and cross-engine agreement.
4. **Audit & Reporting** — SHA-256 hash chain with per-entry HMAC tags and
   append-only database triggers, a chain verification button, PDF/JSON
   reports, and JSON certificates.

## Platform support

| | Windows 10/11 | Linux | macOS |
|---|---|---|---|
| Test suite in CI | ✅ Windows Server runner | ✅ Ubuntu runner | ✅ macOS runner |
| Setup script | `scripts\setup_env.ps1` (run in CI) | `scripts/setup_env.sh` (apt/dnf) | `scripts/setup_env.sh` (Homebrew) |
| Disk listing + system disk blocked, on a real machine | ✅ CI runner | ✅ CI runner | ✅ CI runner + dev Mac |
| GUI starts (headless) | ✅ CI | ✅ CI | ✅ CI; used daily on the dev Mac |
| Same look: pages, dialogs, file pickers (rendered in CI, compared by eye) | ✅ | ✅ | ✅ |
| Simulation erase of a disk image | ✅ tests | ✅ tests | ✅ tests + manual |
| Deleted-file recovery from a FAT image | ✅ tests (pytsk3) | ✅ tests (pytsk3) | ✅ tests + manual walkthrough |
| Erase of a **physical** drive | ⚠️ implemented, never run | ⚠️ implemented, never run | ⚠️ implemented, never run |
| Physical drive access needs | Administrator | root (`sudo`) | root (`sudo`) |

**One UI everywhere:** the app draws everything inside its window itself —
one dark theme, bundled fonts and icons, and its own file picker instead of
Finder / File Explorer / GTK dialogs — so it looks the same on all three.
Only the window's title bar and the OS's font smoothing differ. CI renders
every page and dialog on each OS (`scripts/render_screenshots.py`) and
publishes them to the `ci-screenshots-windows`, `ci-screenshots-linux` and
`ci-screenshots-macos` branches.

"CI runner" means GitHub's hosted virtual machines, which have virtual
disks, not USB sticks. Removable-drive detection on Windows and Linux is
covered by unit tests with recorded `Get-Disk` / `lsblk` output, not by
real hardware.

## What we claim and don't

| ✅ Works (tested) | ⚠️ Works with caveats | ❌ Not done |
|---|---|---|
| Simulation-mode erase of disk images, verified — on Windows, Linux and macOS | Erase verification reads a **sample** of blocks (100% at 64 MB, 6% at 1 GB, 0.2% at 1 TB) | NIST 800-88 **Purge** / firmware Secure Erase (commands generated, never run) |
| System drive blocked from erasure (checked on real Windows, Linux and macOS machines) | Overwrite does **not** guarantee physical erasure on SSDs, flash, APFS or other copy-on-write filesystems | A recorded erase test on a physical drive, on any OS |
| File overwrite + rename + xattr clear + unlink | Audit HMAC key is a **hardcoded dev default** — no real protection in this build | Partition-table recovery (TestDisk not wired) |
| Deleted-file recovery, byte-exact, on FAT images (via pytsk3) | Tamper-*evident*, not tamper-*proof*: detects edits, can't prevent them | Trusted (RFC 3161) timestamping in the app flow |
| Hash-chain tamper detection | Certificate follows BSA Sec. 63 structure; **not legally reviewed, not signed** | Recovery-rate measurement on a real forensic corpus |
| 84 automated tests, run in CI on 3 OSes | Confidence scores are uncalibrated heuristics | Gap carving for fragments PhotoRec can't map |
| Headless GUI smoke tests (pages build, navigation, confirm-dialog gating, simulation default) | bulk_extractor untested (not installed on our dev machine or CI) | A test showing a deleted file carved *without* filesystem metadata |
| | Fuzzy hashes skipped for files > 4 MiB (pure-Python hashing is too slow) | Windows code signing / installer |

## Benchmarks (Apple M4, disk images on internal SSD)

Median of 3 runs, measured 2026-09-17 (macOS only):

| Operation | Result |
|---|---|
| NIST 800-88 Clear, 512 MB image (incl. verification) | 1.2 s (first run: 2.2 s — see docs) |
| DoD 5220.22-M, 512 MB image | 6.1 s (first run: 11.4 s) |
| File eraser, 100 × 64 KB files | 0.05 s (was 23.4 s before per-volume caching) |
| Recovery scan, 128 MB FAT image — pytsk3 | 0.02 s, deleted file recovered 3/3 |
| Recovery scan, 128 MB FAT image — PhotoRec | 0.28 s, deleted text file recovered **0/3** (no signature to carve) |

These measure software overhead on a fast internal SSD. A physical USB
drive will be limited by its own write speed. Full tables, methodology and
caveats: [docs/performance_evaluation.md](docs/performance_evaluation.md).

## Setup

You need Python 3.10–3.13 (3.12 recommended) and git.

### Windows

```powershell
git clone https://github.com/pushpam2404/SIH_149.git
cd SIH_149
powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1
```

The script creates `.venv` and installs the Python packages (pytsk3 comes
as a prebuilt package, no Sleuth Kit install needed). **Optional:** for
PhotoRec signature carving, download *TestDisk & PhotoRec* for Windows from
[cgsecurity.org](https://www.cgsecurity.org/wiki/TestDisk_Download), unzip
it, and add the folder containing `photorec_win.exe` to your PATH.

### Linux

```bash
git clone https://github.com/pushpam2404/SIH_149.git
cd SIH_149
./scripts/setup_env.sh            # testdisk (PhotoRec), libmagic, Qt runtime libs (apt or dnf)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### macOS

```bash
git clone https://github.com/pushpam2404/SIH_149.git
cd SIH_149
./scripts/setup_env.sh            # testdisk (PhotoRec), libmagic, sleuthkit via Homebrew
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

| | Command |
|---|---|
| Windows | `.venv\Scripts\python.exe -m app.main` |
| Linux / macOS | `.venv/bin/python -m app.main` |

The audit log and reports are stored in `data/` and `reports/` inside the
project folder (a packaged build stores them in the user's app-data folder
instead). To scan or erase a **physical** drive, start the app from an
Administrator terminal (Windows) or with `sudo` (Linux/macOS); disk image
files need no special rights.

**Try it without a USB stick:** build a practice image containing a deleted
copy of one of your photos, then scan it on the Recovery page:

```bash
.venv/bin/python -m scripts.make_practice_image path/to/photo.jpg      # Windows: .venv\Scripts\python.exe -m ...
```

## Test

| | Command |
|---|---|
| Windows | `.venv\Scripts\python.exe -m pytest` |
| Linux / macOS | `.venv/bin/python -m pytest` |

84 tests, about 6 seconds: unit tests, integration tests on real disk
images, and headless GUI tests. One recovery test builds its image with
macOS `hdiutil`/`diskutil` and is skipped on Windows and Linux; a second
recovery test uses a pure-Python FAT16 image and runs everywhere.

To check device detection on your own machine (nothing is written):

```bash
.venv/bin/python -m scripts.check_platform          # add --gui to also start the window headless
```

## Safety notes

- Drive erasure defaults to **simulation mode**, which wipes a scratch copy of
  a disk image. Simulation mode cannot target a real device.
- Only disk images and drives the OS reports as external/removable can be
  selected. The system drive never can. **Any external drive can be**, so
  check the name and size before confirming.
- On Windows, erasing a physical drive takes that disk **offline** for the
  duration of the erase (Windows blocks raw writes to mounted volumes) and
  brings it back online afterwards.
- Firmware-level (NVMe/ATA) sanitize commands are generated as reference
  strings only and never executed.

## Documentation

- [Beginner's guide](docs/beginners_guide.md) — plain-English walkthrough: erase a file, then try to recover it
- [User manual](docs/user_manual.md)
- [Technical documentation](docs/technical_documentation.md) — architecture, per-component status, platform matrix
- [Validation & testing](docs/validation_testing.md) — what is and isn't tested
- [Performance evaluation](docs/performance_evaluation.md) — measured benchmarks
- [Compliance mapping](docs/compliance_mapping.md) — claims register

Bundled third-party assets: Fira Sans / Fira Code fonts (SIL Open Font
License, `app/gui/assets/fonts/OFL.txt`) and Lucide icons (ISC License,
`app/gui/assets/icons/LUCIDE_LICENSE.txt`).
