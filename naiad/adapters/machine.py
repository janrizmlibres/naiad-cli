"""The machine reading: what this machine has, asked the way an operator would.

It runs the programs an operator has and reads the files a system exposes,
rather than reaching for a library, so that what it reports is what `sysctl`
and the proc files say. Unknown is a value, never an exception: a machine that
cannot answer is one the Supervisor sizes as the smallest.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# How long a probe may take before its answer is taken as unknown.
PROBE_SECONDS = 5.0


class Machine:
    """One machine's readings. Constructed with its platform and proc
    directory rather than reading them itself, so that a test can stand a fake
    one in for either."""

    def __init__(self, *, platform: str = sys.platform, proc: Path = Path("/proc")) -> None:
        self.platform = platform
        self.proc = Path(proc)

    def total_memory(self) -> int | None:
        """The machine's memory in bytes: `sysctl -n hw.memsize` on macOS, and
        `MemTotal` in the proc meminfo file on Linux. None elsewhere, or when
        neither answers."""
        if self.platform == "darwin":
            return _sysctl("hw.memsize")
        if self.platform.startswith("linux"):
            return _meminfo(self.proc / "meminfo", "MemTotal")
        return None


def _sysctl(name: str) -> int | None:
    try:
        finished = subprocess.run(
            ["sysctl", "-n", name], capture_output=True, text=True, timeout=PROBE_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if finished.returncode != 0:
        return None
    answer = finished.stdout.strip()
    return int(answer) if answer.isdigit() else None


def _meminfo(path: Path, field: str) -> int | None:
    """One field of a meminfo file in bytes. The file gives kibibytes."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        name, _, value = line.partition(":")
        if name == field:
            number, *_unit = value.split()
            return int(number) * 1024 if number.isdigit() else None
    return None


__all__ = ["Machine"]
