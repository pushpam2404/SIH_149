"""Cross-platform helpers: subprocess wrapper, filesystem warnings, tool
discovery, recovered-file naming, Magika result parsing, raw-handle writes."""
import io
import sys
from types import SimpleNamespace

import pytest

from app.core.erasure import fs_aware
from app.core.erasure.writer import write_pass
from app.core.recovery import bulk_extractor_engine, classifier, photorec_engine
from app.core.recovery.tsk_engine import safe_output_name
from app.utils import subprocess_utils
from app.utils.subprocess_utils import run, which_any


def test_run_missing_binary_returns_failed_result_instead_of_raising():
    result = run(["definitely-not-a-real-binary-sih149"])
    assert not result.ok
    assert result.returncode == 127


def test_run_decodes_non_utf8_output_without_crashing():
    code = "import sys; sys.stdout.buffer.write(b'caf\\xe9 ok')"
    result = run([sys.executable, "-c", code])
    assert result.ok
    assert result.stdout.startswith("caf") and result.stdout.endswith(" ok")


def test_which_any_returns_first_available(monkeypatch):
    available = {"photorec_win": "C:/tools/photorec_win.exe"}
    monkeypatch.setattr(subprocess_utils.shutil, "which", lambda name: available.get(name))
    assert which_any("photorec", "photorec_win") == "C:/tools/photorec_win.exe"
    assert which_any("nothing") is None


def test_windows_tool_names_are_recognised(monkeypatch):
    monkeypatch.setattr(photorec_engine, "which_any", lambda *names: "photorec_win.exe" if "photorec_win" in names else None)
    assert photorec_engine.PhotoRecEngine().is_available()
    monkeypatch.setattr(bulk_extractor_engine, "which_any", lambda *names: "x" if "bulk_extractor64" in names else None)
    assert bulk_extractor_engine.BulkExtractorEngine().is_available()


@pytest.mark.parametrize(
    "fs, size, expected",
    [
        ("apfs", 10_000, ["copy-on-write"]),
        ("refs", 10_000, ["copy-on-write"]),
        ("btrfs", 10_000, ["copy-on-write"]),
        ("ntfs", 100, ["MFT record", "Shadow Copies"]),
        ("ntfs", 10_000, ["Shadow Copies"]),
        ("ext4", 10_000, ["journaling"]),
        ("vfat", 10_000, ["ORIGINAL file name"]),
        ("exfat", 10_000, ["ORIGINAL file name"]),
        ("unknown", 10_000, []),
    ],
)
def test_filesystem_warning_wording(fs, size, expected):
    warnings = " ".join(fs_aware.warnings_for_filesystem(fs, size))
    for phrase in expected:
        assert phrase in warnings
    if not expected:
        assert warnings == ""
    if fs == "ntfs" and size >= 1024:
        assert "MFT record" not in warnings


def test_filesystem_is_detected_on_this_os(tmp_path):
    target = tmp_path / "probe.txt"
    target.write_text("x")
    detected = fs_aware.detect_filesystem(str(target))
    assert isinstance(detected, str) and detected
    if sys.platform in ("win32", "darwin", "linux"):
        assert detected != "unknown"


@pytest.mark.parametrize(
    "name, expected",
    [
        ("\ufffdHOTO1.PNG", "inode7_\ufffdHOTO1.PNG"),
        ("a:b*c?.txt", "inode7_a_b_c_.txt"),
        ("dir/evil\\name", "inode7_dir_evil_name"),
        ("  . ", "inode7_unnamed"),
    ],
)
def test_recovered_file_names_are_valid_everywhere(name, expected):
    assert safe_output_name(7, name) == expected


def test_magika_result_parsing_supports_old_and_new_api():
    new = SimpleNamespace(output=SimpleNamespace(label="pdf"), score=0.97)
    old = SimpleNamespace(output=SimpleNamespace(ct_label="png", score=0.88))
    assert classifier._magika_label_and_score(new) == ("pdf", 0.97)
    assert classifier._magika_label_and_score(old) == ("png", 0.88)


class _ShortWriter(io.RawIOBase):
    """Accepts at most 3 bytes per write call, like a raw device handle may."""

    def __init__(self):
        self.data = bytearray()

    def writable(self):
        return True

    def write(self, b):
        chunk = bytes(b[:3])
        self.data.extend(chunk)
        return len(chunk)

    def fileno(self):
        return 99


def test_write_pass_completes_despite_partial_writes(monkeypatch):
    synced = []
    monkeypatch.setattr("app.core.erasure.writer.os.fsync", synced.append)
    sink = _ShortWriter()
    write_pass(sink, 20, "ones", chunk_size=8)
    assert bytes(sink.data) == b"\xff" * 20
    assert synced == [99]
