"""TestDisk subprocess wrapper — partition-table analysis, not file carving.

TestDisk's non-interactive `/list <image>` mode (confirmed working
without hanging, unlike PhotoRec's full ncurses flow) prints the
detected partition table, which is useful supplementary forensic
context ("was there a filesystem here at all, and what did it look
like") alongside PhotoRec's raw file carving. Actual file recovery is
handled by PhotoRecEngine and TskEngine, not this class — scan() is a
no-op that satisfies the RecoveryEngine interface.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.recovery.engine_base import RecoveredFileCandidate, RecoveryEngine
from app.utils.logging_setup import get_logger
from app.utils.subprocess_utils import run, which_any

logger = get_logger(__name__)

_LIST_TIMEOUT_SECONDS = 60.0
_PARTITION_LINE_RE = re.compile(
    r"^\s*[P*D]?\s*(?P<type>\S+.*?)\s{2,}(?P<start>\S.*?)\s{2,}(?P<end>\S.*?)\s{2,}(?P<sectors>\d+)\s*$"
)


@dataclass
class PartitionInfo:
    partition_type: str
    start: str
    end: str
    size_sectors: int


class TestDiskEngine(RecoveryEngine):
    name = "testdisk"

    def is_available(self) -> bool:
        return which_any("testdisk", "testdisk_win") is not None

    def scan(self, source_path: str, output_dir: str) -> list[RecoveredFileCandidate]:
        # File extraction is handled by PhotoRecEngine/TskEngine; TestDisk is
        # used here for partition-table analysis only (see analyze_partitions()).
        return []

    def analyze_partitions(self, source_path: str) -> list[PartitionInfo]:
        if not self.is_available():
            logger.warning("testdisk not installed — skipping partition analysis")
            return []

        result = run([which_any("testdisk", "testdisk_win"), "/list", source_path], timeout=_LIST_TIMEOUT_SECONDS, stdin_devnull=True)
        partitions: list[PartitionInfo] = []
        for line in result.stdout.splitlines():
            match = _PARTITION_LINE_RE.match(line)
            if match:
                partitions.append(
                    PartitionInfo(
                        partition_type=match.group("type").strip(),
                        start=match.group("start").strip(),
                        end=match.group("end").strip(),
                        size_sectors=int(match.group("sectors")),
                    )
                )
        return partitions
