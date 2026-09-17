"""Safe subprocess helpers for shelling out to diskutil/hdiutil/lsblk/photorec/testdisk.

Centralized here so every external-tool wrapper gets the same timeout and
argument-list (never shell=True) discipline.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


class ToolNotFoundError(RuntimeError):
    """Raised when a required external binary isn't on PATH."""


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def which(binary: str) -> str | None:
    return shutil.which(binary)


def require(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise ToolNotFoundError(
            f"Required tool '{binary}' not found on PATH. "
            f"See scripts/setup_env.sh for install instructions."
        )
    return path


def run(
    args: list[str],
    timeout: float = 60.0,
    check: bool = False,
    stdin_devnull: bool = False,
    cwd: str | None = None,
) -> CommandResult:
    """Run a command as an argument list (never a shell string) and capture output.

    stdin_devnull=True is required for tools (e.g. photorec's scriptable
    /cmd mode) that probe stdin and behave differently when it's a TTY vs.
    closed — without it such a tool can block waiting for keyboard input.

    cwd matters for tools (e.g. photorec's `/log` flag) that write
    incidental files relative to the current working directory rather
    than to any path you pass on the command line.
    """
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL if stdin_devnull else None,
        cwd=cwd,
    )
    result = CommandResult(proc.returncode, proc.stdout, proc.stderr)
    if check and not result.ok:
        raise subprocess.CalledProcessError(
            proc.returncode, args, output=proc.stdout, stderr=proc.stderr
        )
    return result
