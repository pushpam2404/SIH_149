"""Reference command strings for firmware-level sanitize (the kind IEEE 2883 Purge relies on).

WARNING: Executing these commands destructively can brick drives if the OS
suspends the machine or if passwords are lost.
For safety during the hackathon/demo, these functions operate in 
DOCUMENTATION-ONLY mode. They return the exact command that would have been
executed but DO NOT run it.
"""
from __future__ import annotations

from app.core.devices.backend_base import DeviceInfo
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


def generate_nvme_format_command(info: DeviceInfo) -> list[str]:
    """Generates the NVMe Format NVM command (IEEE 2883-2022 Purge/Sanitize).
    
    This command instructs the NVMe controller to securely erase all namespaces.
    """
    if "nvme" not in info.path:
        raise ValueError(f"Drive {info.path} is not an NVMe device.")
    
    # User Data Erase (SES=1) or Cryptographic Erase (SES=2)
    # nvme format /dev/nvme0n1 --ses=1
    return ["nvme", "format", info.path, "--ses=1"]


def generate_hdparm_security_erase_command(info: DeviceInfo, password: str = "NULL") -> list[str]:
    """Generates the ATA Secure Erase command via hdparm.
    
    1. Sets a user password.
    2. Issues the SECURITY ERASE UNIT command.
    """
    # The actual execution would look like:
    # hdparm --user-master u --security-set-pass {password} {info.path}
    # hdparm --user-master u --security-erase {password} {info.path}
    
    # We return the combined erase command for logging
    return ["hdparm", "--user-master", "u", "--security-erase", password, info.path]


def simulate_firmware_sanitize(info: DeviceInfo, method: str) -> dict:
    """Simulates a firmware sanitize and returns the audit trail data."""
    if method == "nvme_format":
        cmd = generate_nvme_format_command(info)
    elif method == "ata_secure_erase":
        cmd = generate_hdparm_security_erase_command(info)
    else:
        raise ValueError(f"Unknown firmware sanitize method: {method}")
        
    logger.info("SIMULATED FIRMWARE SANITIZE: %s", " ".join(cmd))
    
    return {
        "command": " ".join(cmd),
        "status": "simulated",
        "compliance": "none - command was generated but NOT executed; no Purge performed",
        "message": "For safety, firmware commands are logged but not executed."
    }
