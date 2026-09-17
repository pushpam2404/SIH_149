"""Platform self-check: run on a real machine (or CI runner) to confirm the
parts that unit tests can only simulate.

    python -m scripts.check_platform            # enumeration + safety + fs detection
    python -m scripts.check_platform --gui      # also build the main window headless

Checks, and exits non-zero if any fails:
  1. The OS device backend enumerates at least one disk.
  2. The disk holding the running OS is detected and BLOCKED.
  3. Every disk the safety check ALLOWS is reported removable and not a
     system disk (i.e. nothing internal slipped through).
  4. A disk image file is allowed (the simulation-mode path).
  5. The filesystem under the current directory is detected.
  6. (--gui) MainWindow builds with the real device list, offscreen.

Nothing is written to any device. The audit DB for --gui goes to a temp dir.
"""
from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path


def main() -> int:
    if "--gui" in sys.argv:
        # Must happen before any app module is imported: settings read these at import time.
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        tmp = tempfile.mkdtemp(prefix="sih149_gui_")
        os.environ["APP_DATA_DIR"] = tmp
        os.environ["APP_REPORTS_DIR"] = os.path.join(tmp, "reports")
        os.environ["APP_AUDIT_DB"] = os.path.join(tmp, "audit.sqlite3")

    from app.core.devices.enumerator import disk_image_info, get_backend
    from app.core.devices.safety import classify_target
    from app.core.erasure.fs_aware import detect_filesystem

    failures: list[str] = []
    print(f"Platform: {platform.platform()} / Python {platform.python_version()}")

    backend = get_backend()
    devices = backend.list_devices()
    print(f"\nBackend: {type(backend).__name__} — {len(devices)} device(s)")
    for info in devices:
        verdict = classify_target(info, backend)
        print(
            f"  {info.path:<22} {info.size_bytes / 1024**3:8.1f} GB  "
            f"removable={info.is_removable!s:<5} system={info.is_system_container!s:<5} "
            f"-> {'SAFE' if verdict.allowed else 'BLOCKED'} ({verdict.reason}) [{info.display_name}]"
        )
        if verdict.allowed and (info.is_system_container or not info.is_removable):
            failures.append(f"{info.path} was allowed but is internal or a system disk")

    if not devices:
        failures.append("no devices enumerated")
    elif not any(d.is_system_container for d in devices):
        failures.append("no device was identified as the system disk")
    elif any(classify_target(d, backend).allowed for d in devices if d.is_system_container):
        failures.append("a system disk was allowed")

    with tempfile.TemporaryDirectory() as tmp:
        image = Path(tmp) / "probe.img"
        image.write_bytes(b"\0" * 4096)
        if not classify_target(disk_image_info(str(image)), backend).allowed:
            failures.append("disk image file was not allowed")

    fs = detect_filesystem(os.getcwd())
    print(f"\nFilesystem under {os.getcwd()}: {fs}")
    if fs == "unknown":
        failures.append("filesystem detection returned 'unknown'")

    if "--gui" in sys.argv:
        failures.extend(_check_gui())

    print()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("All platform checks passed.")
    return 0


def _check_gui() -> list[str]:
    from PySide6.QtWidgets import QApplication

    from app.config.settings import AUDIT_DB_PATH
    from app.gui.main_window import MainWindow
    from app.gui.theme import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    app.processEvents()
    rows = window._drive_eraser._table.rowCount()
    print(f"GUI: main window built offscreen (audit DB {AUDIT_DB_PATH}); Drive Eraser lists {rows} device(s)")
    for index in range(window._stack.count()):
        window._nav_group.button(index).click()
        app.processEvents()
    window.close()
    return [] if window._stack.count() == 6 else ["main window did not build all 6 pages"]


if __name__ == "__main__":
    sys.exit(main())
