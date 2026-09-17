"""PhotoRec subprocess wrapper.

PhotoRec's normal interface is an interactive ncurses TUI with no
documented scriptable flags — but the installed build (PhotoRec 7.2 via
the `testdisk` package) supports an undocumented `/cmd <image> search`
mode that runs non-interactively and writes a parseable DFXML
(report.xml) describing every recovered file. This was verified against
a real test image before being relied on here (see docs/technical_documentation.md,
"Recovery Engine Design").

Requires stdin to be explicitly closed (DEVNULL) — with an inherited TTY
stdin, PhotoRec's TUI can block waiting for a keypress.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import os
from pathlib import Path

from app.core.recovery.engine_base import RecoveredFileCandidate, RecoveryEngine
from app.core.recovery.reassembly import ByteRun, reassemble
from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import run, which_any

logger = get_logger(__name__)

_SCAN_TIMEOUT_SECONDS = 600.0
# The official Windows TestDisk/PhotoRec zip ships photorec_win.exe.
_BINARY_NAMES = ("photorec", "photorec_win")


def photorec_binary() -> str | None:
    return which_any(*_BINARY_NAMES)


def _is_device_path(path: str) -> bool:
    return path.startswith("\\\\.\\") or path.startswith("/dev/")


class PhotoRecEngine(RecoveryEngine):
    name = "photorec"

    def is_available(self) -> bool:
        return photorec_binary() is not None

    def scan(self, source_path: str, output_dir: str) -> list[RecoveredFileCandidate]:
        if not self.is_available():
            logger.warning("photorec not installed — skipping this engine")
            return []

        binary = photorec_binary()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        # Raw device paths (\\.\PhysicalDriveN, /dev/sdX) must be passed as-is;
        # Path.resolve() would mangle the Windows form.
        abs_source = source_path if _is_device_path(source_path) else str(Path(source_path).resolve())

        result = run(
            # /d takes a directory PREFIX: PhotoRec appends recup_dir.N itself, so the
            # trailing separator is what puts recup_dir.N inside out_dir.
            [binary, "/log", "/d", f"{out_dir}{os.sep}", "/cmd", abs_source, "search"],
            timeout=_SCAN_TIMEOUT_SECONDS,
            stdin_devnull=True,
            cwd=str(out_dir),  # /log writes photorec.log relative to CWD, not to /d's path
        )
        logger.info("photorec scan of %s exited (returncode=%s)", source_path, result.returncode)

        report_path = self._latest_report(out_dir)
        if report_path is None:
            logger.warning("photorec produced no report.xml for %s", source_path)
            return []
        return self._parse_report(report_path, abs_source)

    def _latest_report(self, out_dir: Path) -> Path | None:
        reports = sorted(out_dir.glob("recup_dir.*/report.xml"))
        return reports[-1] if reports else None

    def _parse_report(self, report_path: Path, source_path: str) -> list[RecoveredFileCandidate]:
        candidates: list[RecoveredFileCandidate] = []
        recup_dir = report_path.parent
        try:
            root = ET.parse(report_path).getroot()
        except ET.ParseError as exc:
            logger.error("failed to parse photorec report %s: %s", report_path, exc)
            return []

        for fileobj in root.findall("fileobject"):
            filename = fileobj.findtext("filename", default="")
            filesize = int(fileobj.findtext("filesize", default="0") or 0)
            byte_runs_el = fileobj.find("byte_runs")
            offset = None
            fragmented = False
            parsed_runs = []
            if byte_runs_el is not None:
                runs = byte_runs_el.findall("byte_run")
                if runs:
                    offset = int(runs[0].get("img_offset", "0"))
                    for r in runs:
                        img_offset = int(r.get("img_offset", "0"))
                        r_len = int(r.get("len", "0"))
                        parsed_runs.append(ByteRun(img_offset, r_len))
                fragmented = len(runs) > 1

            recovered_path = recup_dir / filename
            if not recovered_path.is_file():
                continue
                
            if fragmented and parsed_runs:
                try:
                    # Overwrite PhotoRec's extraction with our own verified reassembly pipeline
                    reassemble(source_path, parsed_runs, str(recovered_path), attempt_gap_carving=False)
                except Exception as exc:
                    logger.debug("Reassembly override failed for %s: %s", filename, exc)

            candidates.append(
                RecoveredFileCandidate(
                    source_engine=self.name,
                    recovered_path=str(recovered_path),
                    suggested_name=filename,
                    size_bytes=filesize,
                    source_offset=offset,
                    is_fragmented=fragmented,
                )
            )
        return candidates
