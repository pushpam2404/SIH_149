"""Windows backend parsing and safety classification, using recorded-shape
PowerShell JSON. Runs on every OS — no PowerShell is invoked."""
import io
import json

import pytest

from app.core.devices import backend_windows as bw
from app.core.devices.safety import classify_target

# Shape produced by the enumeration script on PowerShell 7 (enums as strings).
PS7_OUTPUT = json.dumps([
    {"Number": 0, "FriendlyName": "Samsung SSD 980", "SerialNumber": "S1 ", "Size": 1000204886016,
     "BusType": "NVMe", "MediaType": "SSD", "IsSystem": True, "IsBoot": True, "HostsSystemDrive": True,
     "IsOffline": False, "IsReadOnly": False, "FileSystems": ["FAT32", "NTFS", "NTFS"]},
    {"Number": 1, "FriendlyName": "WD Data", "SerialNumber": "", "Size": 2000398934016,
     "BusType": "SATA", "MediaType": "HDD", "IsSystem": False, "IsBoot": False, "HostsSystemDrive": False,
     "IsOffline": False, "IsReadOnly": False, "FileSystems": ["NTFS"]},
    {"Number": 2, "FriendlyName": "SanDisk Ultra USB 3.0", "SerialNumber": "4C53", "Size": 30784094208,
     "BusType": "USB", "MediaType": "Unspecified", "IsSystem": False, "IsBoot": False, "HostsSystemDrive": False,
     "IsOffline": False, "IsReadOnly": False, "FileSystems": ["exFAT"]},
])


def _info(disk: dict):
    return bw.disk_to_device_info(disk)


def test_parse_list_and_single_object():
    assert len(bw.parse_disks_json(PS7_OUTPUT)) == 3
    single = json.dumps(json.loads(PS7_OUTPUT)[2])
    assert [d["Number"] for d in bw.parse_disks_json(single)] == [2]
    assert bw.parse_disks_json("") == []
    assert bw.parse_disks_json("not json") == []


def test_bus_type_accepts_powershell_51_integers():
    assert bw.normalize_bus_type(7) == "USB"
    assert bw.normalize_bus_type("7") == "USB"
    assert bw.normalize_bus_type(17) == "NVMe"
    assert bw.normalize_bus_type("USB") == "USB"
    assert bw.normalize_bus_type(None) == "Unknown"


def test_system_nvme_disk_is_blocked():
    info = _info(json.loads(PS7_OUTPUT)[0])
    assert info.path == r"\\.\PhysicalDrive0"
    assert info.is_system_container and info.is_internal and not info.is_removable
    assert info.filesystem == "FAT32, NTFS"
    assert not classify_target(info, bw.WindowsDeviceBackend()).allowed


def test_internal_sata_data_disk_is_blocked():
    info = _info(json.loads(PS7_OUTPUT)[1])
    assert not info.is_system_container
    verdict = classify_target(info, bw.WindowsDeviceBackend())
    assert not verdict.allowed and "internal" in verdict.reason


def test_usb_stick_is_allowed_with_integer_bus_type():
    disk = dict(json.loads(PS7_OUTPUT)[2], BusType=7)  # PowerShell 5.1 shape
    info = _info(disk)
    assert info.is_removable and not info.is_internal
    assert info.serial == "4C53"
    assert classify_target(info, bw.WindowsDeviceBackend()).allowed


@pytest.mark.parametrize("flag", ["IsSystem", "IsBoot", "HostsSystemDrive"])
def test_any_system_signal_blocks_even_a_usb_disk(flag):
    disk = dict(json.loads(PS7_OUTPUT)[2], **{flag: True})
    info = _info(disk)
    verdict = classify_target(info, bw.WindowsDeviceBackend())
    assert not verdict.allowed and "system" in verdict.reason


def test_unknown_bus_fails_closed():
    disk = dict(json.loads(PS7_OUTPUT)[2], BusType="")
    assert not classify_target(_info(disk), bw.WindowsDeviceBackend()).allowed


def test_physical_drive_path_parsing():
    assert bw.parse_physical_drive_number(r"\\.\PhysicalDrive3") == 3
    assert bw.parse_physical_drive_number(r"\\.\physicaldrive12") == 12
    for bad in [r"C:\\", "/dev/sda", r"\\.\PhysicalDrive", r"\\.\PhysicalDrive1x"]:
        with pytest.raises(ValueError):
            bw.parse_physical_drive_number(bad)


def test_list_devices_is_empty_when_powershell_fails(monkeypatch):
    monkeypatch.setattr(bw, "_run_powershell", lambda *a, **k: None)
    assert bw.WindowsDeviceBackend().list_devices() == []


def test_raw_write_requires_admin(monkeypatch):
    monkeypatch.setattr(bw, "is_admin", lambda: False)
    info = _info(json.loads(PS7_OUTPUT)[2])
    with pytest.raises(PermissionError):
        with bw.WindowsDeviceBackend().open_raw(info, "r+b"):
            pass


class _FakeResult:
    def __init__(self, ok=True, stdout="", stderr=""):
        self.ok, self.stdout, self.stderr = ok, stdout, stderr


def test_raw_write_takes_disk_offline_and_restores_state(monkeypatch):
    scripts = []

    def fake_ps(script, timeout=30.0):
        scripts.append(script)
        if script is bw._ENUMERATE_SCRIPT:
            usb = dict(json.loads(PS7_OUTPUT)[2], IsReadOnly=True)
            return _FakeResult(stdout=json.dumps([usb]))
        return _FakeResult()

    opened = {}

    def fake_open(path, mode, buffering=-1):
        opened.update(path=path, mode=mode, buffering=buffering)
        return io.BytesIO(b"\0" * 16)

    monkeypatch.setattr(bw, "is_admin", lambda: True)
    monkeypatch.setattr(bw, "_run_powershell", fake_ps)
    monkeypatch.setattr("builtins.open", fake_open)

    info = _info(json.loads(PS7_OUTPUT)[2])
    with bw.WindowsDeviceBackend().open_raw(info, "r+b") as handle:
        handle.write(b"x")

    state_changes = [s for s in scripts if "Set-Disk" in s]
    assert state_changes == [
        "$ErrorActionPreference = 'Stop'; Set-Disk -Number 2 -IsOffline $true",
        "$ErrorActionPreference = 'Stop'; Set-Disk -Number 2 -IsReadOnly $false",
        "$ErrorActionPreference = 'Stop'; Set-Disk -Number 2 -IsReadOnly $true",
        "$ErrorActionPreference = 'Stop'; Set-Disk -Number 2 -IsOffline $false",
    ]
    assert opened == {"path": r"\\.\PhysicalDrive2", "mode": "r+b", "buffering": 0}


def test_raw_write_restores_online_state_even_if_writing_fails(monkeypatch):
    scripts = []

    def fake_ps(script, timeout=30.0):
        scripts.append(script)
        if script is bw._ENUMERATE_SCRIPT:
            return _FakeResult(stdout=json.dumps([json.loads(PS7_OUTPUT)[2]]))
        return _FakeResult()

    def failing_open(*args, **kwargs):
        raise OSError("access denied")

    monkeypatch.setattr(bw, "is_admin", lambda: True)
    monkeypatch.setattr(bw, "_run_powershell", fake_ps)
    monkeypatch.setattr("builtins.open", failing_open)

    info = _info(json.loads(PS7_OUTPUT)[2])
    with pytest.raises(OSError):
        with bw.WindowsDeviceBackend().open_raw(info, "r+b"):
            pass
    assert scripts[-1].endswith("Set-Disk -Number 2 -IsOffline $false")
