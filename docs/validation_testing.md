# Validation & Testing

## Test Strategy Overview

Two layers:
- **Unit tests** (`tests/unit/`) — synthetic data, no external tools.
- **Integration tests** (`tests/integration/`) — real disk images and the
  real `pytsk3`/PhotoRec binaries. The recovery test needs macOS
  `hdiutil`/`diskutil` and is skipped elsewhere.

```bash
.venv/bin/python -m pytest tests/ -v
```

## Latest Recorded Run

2026-09-17, macOS (Apple M4), Python 3.11.16:
**29 passed, 0 failed, 0 skipped in 5.5 s** (16 warnings, all the Magika
deprecation notice below).

29 tests is a small suite for a tool like this. Read "What the Tests Do NOT
Cover" before drawing conclusions from the pass count.

## Unit Tests

| File | Tests | What it verifies |
|---|---|---|
| `test_audit_ledger.py` | 4 | Empty chain is valid; appended entries link by `prev_hash`; a payload edited via raw SQL (with the append-only trigger dropped, as an attacker with file access could) is detected at the right entry; a ledger database created before HMAC tags existed still opens and verifies. |
| `test_erasure_writer_verifier.py` | 4 | Zero/ones/random passes write the expected data; `verify_pass()` flags data that was never wiped. |
| `test_file_eraser.py` | 4 | A file is overwritten, renamed and unlinked, and logged; a missing file fails cleanly; batch and folder erasure process every item. |
| `test_safety.py` | 7 | Disk images allowed; system container denied; internal non-removable denied with its own reason; external/removable allowed; ambiguous devices denied. Uses constructed `DeviceInfo` objects, not real hardware. |
| `test_recovery_classification.py` | 7 | JPEG header/footer detection; truncated file flagged as footer-missing; score ordering complete > truncated, contiguous > fragmented, cross-engine > single engine. |

## Integration Tests

| File | Tests | Scenario |
|---|---|---|
| `test_drive_erase_simulation.py` | 2 | 2 MB image erased in simulation mode: original bytes unchanged, scratch copy all zeros and verified, PDF/JSON reports created. Erase refused without `user_confirmed=True`. |
| `test_recovery_pipeline.py` | 1 | 32 MB FAT image built with `hdiutil`/`diskutil`, a known text file written then deleted, full `run_recovery_scan()` run. Asserts the **exact original bytes** are recovered by at least one engine, the file is hashed and scored, the audit chain verifies, and reports are generated. |

Note on the recovery test: it passes because **pytsk3** recovers the file
from the surviving FAT directory entry. PhotoRec runs in the same test but
does not recover the plain-text file (see `performance_evaluation.md`).
Signature carving without filesystem metadata is not verified by any test.

## What the Tests Do NOT Cover

Be aware of these before trusting a component:

| Component | Coverage |
|---|---|
| GUI (all views, dialogs, buttons) | None automated. Manually smoke-tested only. After the 2026-09-17 redesign, pages were rendered and inspected, and a one-off script checked the confirm dialog, queue state, simulation default and navigation; that script is not part of `tests/`. |
| Certificate generation (`certificate.py`) | None automated. Checked by hand once. |
| HMAC tag verification failures (wrong key, missing tag) | Not tested; only the success path runs. |
| Filesystem warnings (`fs_aware.py`) | Code runs during file-eraser tests on APFS; warning content is not asserted. NTFS/ext4 branches never run. |
| bulk_extractor engine | Not tested; binary not installed on the dev machine. |
| Magika / python-magic classification | Runs during recovery tests; results not asserted. |
| Fragment reassembly (`reassembly.py`) | Not tested; the fixture file is not fragmented. |
| Real physical drives | No automated test; see manual checklist. |
| Linux and Windows backends | Never run. |
| Large targets (> 1 GB), damaged media, non-FAT filesystems (NTFS, ext4, exFAT, APFS) | Not tested. Recovery is only validated on small FAT images. |
| Recovery of formatted media | Not tested. The fixture deletes a file; it does not reformat the volume. |
| Signature carving (PhotoRec) recovering a known file | Not tested; PhotoRec returns 0 matching files on the current fixture. |

## Recovery Validation — Honest Scope

The only recovery ground truth we have is: **one deleted 55-byte text file
on a small FAT image, recovered byte-for-byte**. We have **not** measured
recovery rates on a benchmark corpus (e.g. the DFRWS carving challenges or
NIST CFReDS images), on fragmented files, or on overwritten or damaged
media. Any recovery-rate claim beyond "works on the FAT fixture" would be
unsupported.

## Manual Test Checklist (real hardware)

Not yet recorded as completed. Fill in date and result when run.

- [ ] Plug in a spare USB drive with no data you need.
- [ ] Drive Eraser: the USB drive shows `SAFE`, internal disks show `BLOCKED`.
- [ ] Real (non-simulation) single-pass erase on the USB drive; verification passes.
- [ ] Recovery on the wiped drive returns 0 or near-0 candidates without crashing.
- [ ] Reformat the drive, add and delete a known file, scan, confirm it comes back.
- [ ] Audit Log: all actions listed; **Verify Chain Integrity** reports intact.
- [ ] Generate a certificate for the USB drive and read it end to end.
- [ ] Open every generated PDF and check for formatting problems.

## Safety Guard-Rail Checks

- Erasing the system drive is blocked in `safety.py`
  (`tests/unit/test_safety.py`), independent of the GUI.
- `run_drive_erase()` raises `ConfirmationRequiredError` unless
  `user_confirmed=True` (tested).
- Simulation mode against a real device raises
  `SimulationModeMismatchError` (implemented; not covered by a test).

## Known Issues

- **Fixed 2026-09-17:** the app crashed on startup with an audit database
  created before the `mac_tag` column was added (`no such column: mac_tag`).
  Tests missed it because they always create a fresh database. The store
  now adds the column when missing, and a regression test covers it.

- Magika logs a deprecation warning (`.ct_label` → `.label`) during tests.
  Harmless today; will break on a future Magika release.
- Until 2026-09-17 the suite took about 3 minutes because pure-Python
  fuzzy hashing (`ppdeep`) stalled on a large carved blob. Fuzzy hashing
  is now skipped for files over 4 MiB; the suite takes about 6 seconds.
- An interrupted test run can leave an orphaned `photorec` process
  running; check with `ps aux | grep photorec`.
