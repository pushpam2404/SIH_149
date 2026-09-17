"""Secure file & folder erasure: overwrite -> strip metadata -> unlink -> verify.

Caveat documented for the report/GUI rather than hidden: in-place
overwrite is "logical erasure, best-effort" — on SSDs and copy-on-write
filesystems (e.g. APFS) it does not guarantee the original physical
blocks were overwritten, because wear-leveling/CoW may have relocated
data. See docs/compliance_mapping.md.
"""
from __future__ import annotations

import os
import secrets
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.config.constants import ACTION_FILE_ERASE
from app.core.audit.ledger import AuditLedger
from app.core.erasure.writer import write_pass
from app.core.erasure.fs_aware import get_file_warnings, invoke_trim
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[str, int, int], None]  # (path, index, total)


@dataclass
class FileEraseResult:
    path: str
    ok: bool
    bytes_overwritten: int = 0
    metadata_cleared: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    trim_invoked: bool = False


@dataclass
class BatchEraseResult:
    results: list[FileEraseResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def failed(self) -> list[FileEraseResult]:
        return [r for r in self.results if not r.ok]


def _random_filename(length: int = 16) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _clear_extended_attributes(path: Path) -> bool:
    """Best-effort removal of extended attributes (xattrs). Not fatal if unsupported."""
    try:
        for name in os.listxattr(path):
            try:
                os.removexattr(path, name)
            except OSError:
                pass
        return True
    except (OSError, AttributeError):
        return False


def erase_file(path: str, ledger: AuditLedger, passes: int = 1, actor: str = "user") -> FileEraseResult:
    target = Path(path)
    if not target.is_file():
        result = FileEraseResult(path=path, ok=False, error="not a regular file")
        ledger.append_entry(ACTION_FILE_ERASE, path, {"ok": False, "error": result.error}, actor=actor)
        return result

    warnings = get_file_warnings(path)
    trim_invoked = False

    try:
        size = target.stat().st_size
        with open(target, "r+b") as f:
            for _ in range(passes):
                f.seek(0)
                write_pass(f, size, "random")

        metadata_cleared = _clear_extended_attributes(target)

        # Rename to a random name before unlinking so the directory entry
        # (and thus the original filename) doesn't linger in filesystem
        # journals/undelete metadata under its original name.
        scrubbed_path = target.with_name(_random_filename())
        target.rename(scrubbed_path)
        scrubbed_path.unlink()

        still_present = target.exists() or scrubbed_path.exists()
        if still_present:
            raise OSError("target still present on filesystem after unlink")

        # Invoke TRIM if possible (best-effort)
        trim_invoked = invoke_trim(str(target.parent))

        result = FileEraseResult(
            path=path, 
            ok=True, 
            bytes_overwritten=size * passes, 
            metadata_cleared=metadata_cleared,
            warnings=warnings,
            trim_invoked=trim_invoked,
        )
    except OSError as exc:
        result = FileEraseResult(path=path, ok=False, error=str(exc), warnings=warnings)

    ledger.append_entry(
        ACTION_FILE_ERASE,
        path,
        {
            "ok": result.ok,
            "bytes_overwritten": result.bytes_overwritten,
            "metadata_cleared": result.metadata_cleared,
            "error": result.error,
            "warnings": result.warnings,
            "trim_invoked": result.trim_invoked,
        },
        actor=actor,
    )
    return result


def erase_batch(
    paths: list[str],
    ledger: AuditLedger,
    passes: int = 1,
    progress_cb: ProgressCallback | None = None,
) -> BatchEraseResult:
    results = []
    for i, path in enumerate(paths, start=1):
        if progress_cb:
            progress_cb(path, i, len(paths))
        results.append(erase_file(path, ledger, passes=passes))
    return BatchEraseResult(results=results)


def erase_folder(
    folder_path: str,
    ledger: AuditLedger,
    passes: int = 1,
    progress_cb: ProgressCallback | None = None,
) -> BatchEraseResult:
    root = Path(folder_path)
    files = [str(p) for p in root.rglob("*") if p.is_file()]
    batch = erase_batch(files, ledger, passes=passes, progress_cb=progress_cb)

    # Remove now-empty directories bottom-up.
    for dirpath in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            dirpath.rmdir()
        except OSError:
            pass
    try:
        root.rmdir()
    except OSError:
        pass

    return batch
