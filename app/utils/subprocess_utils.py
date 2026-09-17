"""Safe subprocess helpers for shelling out to diskutil/hdiutil/lsblk/PowerShell/photorec/testdisk.

Centralized here so every external-tool wrapper gets the same timeout and
argument-list (never shell=True) discipline, and the same cross-platform
behaviour:

- Output is decoded as UTF-8 with `errors="replace"`, so a tool printing
  bytes in another code page (common on Windows consoles) can't crash the
  caller with UnicodeDecodeError.
- On Windows, child processes are started with CREATE_NO_WINDOW so the GUI
  (a windowed app with no console) doesn't flash a console window for
  every PowerShell/PhotoRec call.
- A missing binary returns a failed CommandResult instead of raising, so
  callers only need to check `.ok`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

IS_WINDOWS = sys.platform == "win32"
_NO_WINDOW_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0


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


def which_any(*binaries: str) -> str | None:
    """First binary found on PATH, e.g. which_any("photorec", "photorec_win")
    — several tools ship under a different executable name on Windows."""
    for name in binaries:
        path = shutil.which(name)
        if path is not None:
            return path
    return None


def require(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise ToolNotFoundError(
            f"Required tool '{binary}' not found on PATH. "
            f"See the Setup section of README.md for install instructions."
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

    subprocess.TimeoutExpired is still raised on timeout so long-running
    callers can tell "hung" apart from "failed".
    """
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL if stdin_devnull else None,
            cwd=cwd,
            creationflags=_NO_WINDOW_FLAGS,
        )
    except FileNotFoundError as exc:
        result = CommandResult(127, "", f"executable not found: {exc}")
        if check:
            raise ToolNotFoundError(result.stderr) from exc
        return result

    result = CommandResult(proc.returncode, proc.stdout or "", proc.stderr or "")
    if check and not result.ok:
        raise subprocess.CalledProcessError(
            proc.returncode, args, output=proc.stdout, stderr=proc.stderr
        )
    return result
