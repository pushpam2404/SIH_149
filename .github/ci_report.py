"""CI helper: run a command, stream its output, and publish key lines as
GitHub Actions annotations (visible on the run page and via the public
check-runs API, unlike raw logs which need a login).

    python .github/ci_report.py tests    -> pytest, annotates summary + skip reasons
    python .github/ci_report.py platform -> scripts.check_platform --gui, annotates device verdicts
"""
import platform
import subprocess
import sys

COMMANDS = {
    "tests": [sys.executable, "-m", "pytest", "-v", "-rs"],
    "platform": [sys.executable, "-m", "scripts.check_platform", "--gui"],
}
KEEP = {
    "tests": lambda line: line.startswith("SKIPPED") or (line.startswith("=") and (" passed" in line or " failed" in line)),
    "platform": lambda line: "->" in line or line.startswith(("Backend:", "Filesystem", "GUI:", "FAIL", "All platform")),
}


def main() -> int:
    kind = sys.argv[1]
    proc = subprocess.run(COMMANDS[kind], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    print(proc.stdout)
    title = f"{kind} on {platform.system()} ({platform.release()})"
    lines = [line.strip("= ").strip() for line in proc.stdout.splitlines() if KEEP[kind](line.strip())]
    # GitHub keeps at most 10 annotations per step: put the verdict/summary lines first.
    summary_markers = (" passed", " failed", "All platform", "FAIL")
    lines.sort(key=lambda line: 0 if any(marker in line for marker in summary_markers) else 1)
    for line in lines[:9]:
        level = "error" if proc.returncode else "notice"
        # Newlines/colons would break the workflow command syntax.
        message = line.replace("%", "%25").replace("\r", "").replace("\n", " ")
        print(f"::{level} title={title}::{message}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
