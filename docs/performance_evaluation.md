# Performance Evaluation

All numbers here were measured on 2026-09-17 with `scripts/benchmark.py`.
Nothing is estimated or copied from elsewhere. Reproduce them with:

```bash
.venv/bin/python -m scripts.benchmark
```

## Test Environment

- Apple M4 MacBook Air, 16 GB RAM, internal SSD, macOS (Darwin 27.0)
- Python 3.11.16
- sleuthkit (pytsk3), PhotoRec 7.2, libmagic, Magika 1.0.3, ppdeep
- bulk_extractor **not installed** — not benchmarked
- Each measurement is the **median of 3 runs**, with the min–max range shown

## Read This First — What These Numbers Do and Don't Mean

1. **Targets are disk-image files on a fast internal SSD, not physical
   drives.** The numbers measure the software's own overhead. A real USB
   stick or HDD will be limited by its own write speed (often 10–100 MB/s),
   which will dominate the total time.
2. **The erase source images are sparse files** (created with `truncate`),
   so making the scratch copy in simulation mode is cheaper than it would
   be for a full image.
3. **Recovery was measured on tiny, almost-empty FAT images holding one
   deleted text file.** This says nothing about recovery *rate* on real
   media, and scan time on a full multi-GB device will be far higher.
4. Three runs on one machine is a small sample. Treat these numbers as
   rough indicators, not a statistical characterization.

## Drive Erasure (simulation mode)

Time includes creating the scratch copy, all overwrite passes, and sampled
read-back verification after each pass.

| Standard | Size | Median time | Min–max | Throughput | Verified |
|---|---|---|---|---|---|
| Single pass (zero) | 64 MB | 1.95 s | 1.92–1.99 s | 33 MB/s | 3/3 PASS |
| Single pass (random) | 64 MB | 4.49 s | 4.46–4.50 s | 14 MB/s | 3/3 PASS |
| NIST 800-88 Clear | 64 MB | 1.92 s | 1.92–1.93 s | 33 MB/s | 3/3 PASS |
| DoD 5220.22-M (3-pass) | 64 MB | 8.29 s | 8.27–8.31 s | 8 MB/s | 3/3 PASS |
| Single pass (zero) | 512 MB | 2.17 s | 2.12–2.18 s | 236 MB/s | 3/3 PASS |
| Single pass (random) | 512 MB | 7.40 s | 7.39–7.44 s | 69 MB/s | 3/3 PASS |
| NIST 800-88 Clear | 512 MB | 2.16 s | 2.16–2.18 s | 237 MB/s | 3/3 PASS |
| DoD 5220.22-M (3-pass) | 512 MB | 11.44 s | 11.41–11.52 s | 45 MB/s | 3/3 PASS |

Observations:
- **There is a fixed overhead of roughly 1.8 s per run**, regardless of
  size. A zero-fill of 64 MB and of 512 MB take almost the same time. That
  is why "throughput" looks 7× better at 512 MB: it isn't faster I/O, the
  fixed cost is simply spread over more data. We have not profiled where
  the fixed cost goes.
- **Random-fill passes are 2.5–5 s slower** than zero-fill because of
  generating random data (plus the entropy check during verification).
- DoD 5220.22-M does one random pass and three verifications, so it is the
  slowest.
- **Real-device estimate** (not measured): throughput is capped by the
  device. For a 64 GB USB stick writing at 25 MB/s, one pass takes about
  43 minutes, and DoD 5220.22-M about 2 hours 10 minutes.

## File & Folder Eraser (1 overwrite pass)

| Scenario | Median time | Min–max | Per file | All PASS |
|---|---|---|---|---|
| 100 files × 64 KB | 23.37 s | 23.10–23.56 s | ~0.23 s | yes |
| 10 files × 10 MB | 3.05 s | 2.96–3.06 s | ~0.31 s | yes |

**Known performance issue:** small files are slow — about 0.23 s each —
and almost none of that is writing data. Before each erase the tool runs
filesystem-detection subprocesses (`df`, `stat`, `tmutil listlocalsnapshots`),
and we measured that at about 0.22 s per file. Caching these results per
directory would remove most of the cost; that is not done yet. Expect
roughly 4 minutes for a folder of 1,000 small files.

## Recovery Scan

FAT images built with `tests/fixtures/make_test_image.py`, each holding
one kept file and one deleted 55-byte text file. Each engine is timed on
its own, including hashing, classification and scoring.

| Image | Engine | Median time | Min–max | Candidates | Deleted file recovered byte-exact |
|---|---|---|---|---|---|
| 32 MB | pytsk3 | 0.05 s | 0.05–0.13 s | 2 | **3/3** |
| 32 MB | PhotoRec | 0.21 s | 0.21–0.21 s | 3 | **0/3** |
| 128 MB | pytsk3 | 0.06 s | 0.06–0.08 s | 2 | **3/3** |
| 128 MB | PhotoRec | 0.68 s | 0.65–0.70 s | 3 | **0/3** |

Honest reading of this table:
- **Only pytsk3 recovered the deleted file.** It works because the FAT
  directory entry still exists. PhotoRec did not recover it, because plain
  text has no file signature to carve from, so PhotoRec only returned
  other structures (a large blob and two small gzip-signature fragments).
  **Carving without filesystem metadata is therefore not demonstrated by
  this fixture.** A fixture with signature-bearing files (JPEG, PDF, ZIP)
  on a reformatted volume would be needed to demonstrate it; we don't have
  one yet.
- PhotoRec time grows with image size (0.21 s → 0.68 s for 4× the data),
  as expected for a full sector scan. pytsk3 time barely changes because
  it reads filesystem metadata, not every sector.
- Nothing here measures recovery rate on real, used, fragmented, or
  damaged media.

## Bug Found by Benchmarking (fixed)

The first benchmark run never finished. PhotoRec carves a ~32 MB blob from
the test image, and **`ppdeep` fuzzy hashing is pure Python: it spent 10 to
over 60 minutes on that one file.** In the app, that would have looked like
a frozen recovery scan. It also explains why the test suite used to take
about 3 minutes.

Fix: fuzzy hashes are now computed only for files up to 4 MiB; larger
files show "skipped (>4 MiB)". After the fix, the scans above take under a
second and the full test suite dropped from about 180 s to about 6 s.

**Trade-off:** large recovered files no longer get a similarity hash. Their
SHA-256 hash is still computed.

## Classification & Confidence Scoring

- **Accuracy has not been measured on any real corpus.** The only checks
  are 7 unit tests on synthetic JPEG data (header/footer detection,
  truncated-file flagging, and score ordering). There are no precision or
  recall numbers.
- Confidence weights (`app/core/recovery/confidence.py`): +40 header,
  +25 footer (−10 if expected but missing), +10 non-zero size, +10
  contiguous (−15 fragmented), +15 cross-engine agreement. They were
  chosen by reasoning, not tuned on labelled data. Use scores to rank
  candidates within one scan only.
- Magika's own published accuracy figures apply to Magika, not to this
  tool. In our pipeline it only overrides the type when our signature
  table returns "unknown".

## Resource Usage

Not profiled. Erasure writes in 4 MiB chunks and pytsk3 reads in 1 MiB
chunks, so memory should not grow with target size, but we have not
measured it. Magika loads an ML model on first use, which adds startup
time and memory that we also haven't measured.

## Not Benchmarked

- Physical HDD, SSD, USB, or SD card targets
- Images larger than 512 MB (erase) or 128 MB (recovery)
- bulk_extractor
- Linux and Windows
- GUI responsiveness under load
