"""Linux backend parsing and safety classification, using recorded-shape
`lsblk -J` output. Runs on every OS — lsblk is not invoked."""
from app.core.devices.backend_linux import LinuxDeviceBackend, as_flag, parse_lsblk
from app.core.devices.safety import classify_target

# Older util-linux: flags as strings "0"/"1", root filesystem on LVM inside a partition.
LSBLK_OLD = {
    "blockdevices": [
        {"name": "sda", "size": "500107862016", "rm": "0", "ro": "0", "type": "disk", "mountpoint": None,
         "model": "Samsung SSD 860 ", "serial": "S3Z", "fstype": None, "rota": "0", "tran": "sata",
         "children": [
             {"name": "sda1", "type": "part", "mountpoint": "/boot/efi", "fstype": "vfat"},
             {"name": "sda2", "type": "part", "mountpoint": None, "fstype": "LVM2_member",
              "children": [{"name": "vg-root", "type": "lvm", "mountpoint": "/", "fstype": "ext4"}]},
         ]},
        {"name": "sdb", "size": "31914983424", "rm": "1", "ro": "0", "type": "disk", "mountpoint": None,
         "model": "Ultra", "serial": "4C53", "fstype": None, "rota": "0", "tran": "usb",
         "children": [{"name": "sdb1", "type": "part", "mountpoint": "/media/user/USB", "fstype": "exfat"}]},
        {"name": "loop0", "size": "4096", "rm": "0", "type": "loop", "mountpoint": "/snap/core"},
    ]
}

# Newer util-linux: booleans and a `mountpoints` list.
LSBLK_NEW = {
    "blockdevices": [
        {"name": "nvme0n1", "size": 1024209543168, "rm": False, "ro": False, "type": "disk",
         "mountpoints": [None], "model": "WD SN770", "serial": "22", "fstype": None, "rota": False,
         "tran": "nvme",
         "children": [
             {"name": "nvme0n1p1", "type": "part", "mountpoints": ["/boot"], "fstype": "ext4"},
             {"name": "nvme0n1p2", "type": "part", "mountpoints": [None], "fstype": "crypto_LUKS",
              "children": [{"name": "luks-root", "type": "crypt", "mountpoints": ["/"], "fstype": "btrfs"}]},
         ]},
        {"name": "sdc", "size": 8000000000, "rm": False, "ro": False, "type": "disk", "mountpoints": [None],
         "model": "Hot-swap bay HDD", "serial": "Z1", "fstype": None, "rota": True, "tran": "sata"},
        {"name": "sdd", "size": 64000000000, "rm": True, "ro": False, "type": "disk", "mountpoints": [None],
         "model": "Live USB", "serial": "L1", "fstype": None, "rota": False, "tran": "usb",
         "children": [{"name": "sdd1", "type": "part", "mountpoints": ["/"], "fstype": "ext4"}]},
    ]
}


def _by_name(devices):
    return {d.path: d for d in devices}


def test_string_flag_zero_is_not_removable():
    assert as_flag("0") is False and as_flag("1") is True
    assert as_flag(False) is False and as_flag(True) is True
    assert as_flag(None) is False


def test_old_format_system_disk_on_lvm_is_detected_and_blocked():
    devices = _by_name(parse_lsblk(LSBLK_OLD))
    assert set(devices) == {"/dev/sda", "/dev/sdb"}, "loop devices must be skipped"
    sda = devices["/dev/sda"]
    assert sda.is_internal and not sda.is_removable
    assert sda.is_system_container
    assert sda.size_bytes == 500107862016
    assert not classify_target(sda, LinuxDeviceBackend()).allowed


def test_old_format_usb_stick_is_allowed():
    sdb = _by_name(parse_lsblk(LSBLK_OLD))["/dev/sdb"]
    assert sdb.is_removable and not sdb.is_system_container
    assert sdb.filesystem == "exfat"
    assert classify_target(sdb, LinuxDeviceBackend()).allowed


def test_new_format_luks_root_is_detected():
    nvme = _by_name(parse_lsblk(LSBLK_NEW))["/dev/nvme0n1"]
    assert nvme.is_system_container
    assert nvme.topology_type == "nvme"
    assert not classify_target(nvme, LinuxDeviceBackend()).allowed


def test_internal_non_removable_data_disk_is_blocked():
    sdc = _by_name(parse_lsblk(LSBLK_NEW))["/dev/sdc"]
    assert sdc.topology_type == "magnetic"
    assert not classify_target(sdc, LinuxDeviceBackend()).allowed


def test_live_usb_running_the_os_is_blocked_even_though_removable():
    sdd = _by_name(parse_lsblk(LSBLK_NEW))["/dev/sdd"]
    assert sdd.is_removable
    verdict = classify_target(sdd, LinuxDeviceBackend())
    assert not verdict.allowed and "system" in verdict.reason
