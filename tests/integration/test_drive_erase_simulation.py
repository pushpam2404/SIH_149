"""End-to-end: create a disk image -> erase it in simulation mode -> verify.

Uses a plain disk-image DeviceInfo (is_disk_image=True), which never
touches the real device backend, so this test runs anywhere without
needing hdiutil/diskutil device attachment.
"""
from app.core.audit.ledger import AuditLedger
from app.core.devices.enumerator import disk_image_info
from app.core.devices.backend_macos import MacOSDeviceBackend
from app.core.erasure.drive_eraser import run_drive_erase
from app.core.reporting.json_report import save_json
from app.core.reporting.pdf_report import render_pdf
from app.core.reporting.report_builder import build_drive_erase_report


def test_simulation_mode_wipes_a_copy_and_leaves_original_untouched(tmp_path):
    original = tmp_path / "source.img"
    original.write_bytes(b"\xAA" * (2 * 1024 * 1024))
    original_bytes_before = original.read_bytes()

    ledger = AuditLedger(tmp_path / "audit.sqlite3")
    info = disk_image_info(str(original))
    backend = MacOSDeviceBackend()  # unused for image targets, but required by the signature

    result = run_drive_erase(
        info,
        backend,
        standard_id="single_pass_zero",
        ledger=ledger,
        simulation_mode=True,
        user_confirmed=True,
        simulation_scratch_dir=tmp_path / "scratch",
    )

    assert result.ok
    assert result.effective_target_path != str(original)
    assert original.read_bytes() == original_bytes_before, "original image must be untouched in simulation mode"

    scratch_bytes = open(result.effective_target_path, "rb").read()
    assert scratch_bytes == b"\x00" * len(scratch_bytes)

    entries = ledger.get_entries()
    assert len(entries) == 1
    assert entries[0].payload["result"] == "PASS"

    report = build_drive_erase_report(result, info)
    assert "SIMULATION MODE" in (report.notice or "")

    json_path = save_json(report, str(tmp_path / "reports" / "drive_report.json"))
    pdf_path = render_pdf(report, str(tmp_path / "reports" / "drive_report.pdf"))
    assert json_path.exists()
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0

    ledger.close()


def test_drive_erase_refuses_without_confirmation(tmp_path):
    original = tmp_path / "source.img"
    original.write_bytes(b"\xAA" * 1024)
    ledger = AuditLedger(tmp_path / "audit.sqlite3")
    info = disk_image_info(str(original))
    backend = MacOSDeviceBackend()

    import pytest
    from app.core.erasure.drive_eraser import ConfirmationRequiredError

    with pytest.raises(ConfirmationRequiredError):
        run_drive_erase(
            info, backend, standard_id="single_pass_zero", ledger=ledger,
            simulation_mode=True, user_confirmed=False,
        )
    ledger.close()
