import pytest

from app.core.devices.backend_base import DeviceBackend, DeviceInfo
from app.core.devices.safety import UnsafeTargetError, assert_safe, classify_target


class _FakeBackend(DeviceBackend):
    """Backend stub for testing safety.py without touching real hardware."""

    def __init__(self, system_drive_paths: set[str]):
        self._system_drive_paths = system_drive_paths

    def list_devices(self):
        return []

    def get_device_info(self, path):
        raise NotImplementedError

    def is_system_drive(self, info: DeviceInfo) -> bool:
        return info.path in self._system_drive_paths

    def open_raw(self, info, mode):
        raise NotImplementedError


def _device(**overrides) -> DeviceInfo:
    base = dict(
        path="/dev/disk9",
        display_name="Test Device",
        size_bytes=1024,
        is_disk_image=False,
        is_removable=True,
        is_internal=False,
        is_system_container=False,
    )
    base.update(overrides)
    return DeviceInfo(**base)


def test_disk_image_is_always_allowed():
    info = _device(is_disk_image=True, is_removable=True, is_internal=False)
    backend = _FakeBackend(system_drive_paths=set())
    verdict = classify_target(info, backend)
    assert verdict.allowed


def test_backend_flagged_system_drive_is_denied_even_if_removable():
    info = _device(path="/dev/disk0", is_removable=True)
    backend = _FakeBackend(system_drive_paths={"/dev/disk0"})
    verdict = classify_target(info, backend)
    assert not verdict.allowed


def test_precise_system_container_is_denied_with_specific_reason():
    info = _device(is_system_container=True, is_removable=True)
    backend = _FakeBackend(system_drive_paths=set())
    verdict = classify_target(info, backend)
    assert not verdict.allowed
    assert "system" in verdict.reason


def test_internal_fixed_drive_is_denied():
    info = _device(is_internal=True, is_removable=False)
    backend = _FakeBackend(system_drive_paths=set())
    verdict = classify_target(info, backend)
    assert not verdict.allowed


def test_external_removable_drive_is_allowed():
    info = _device(is_internal=False, is_removable=True)
    backend = _FakeBackend(system_drive_paths=set())
    verdict = classify_target(info, backend)
    assert verdict.allowed


def test_ambiguous_device_fails_closed():
    info = _device(is_internal=False, is_removable=False)
    backend = _FakeBackend(system_drive_paths=set())
    verdict = classify_target(info, backend)
    assert not verdict.allowed


def test_assert_safe_raises_for_unsafe_target():
    info = _device(path="/dev/disk0", is_removable=True)
    backend = _FakeBackend(system_drive_paths={"/dev/disk0"})
    with pytest.raises(UnsafeTargetError):
        assert_safe(info, backend)
