"""The machine reading: what this machine has, asked the way an operator would.

It runs the programs an operator has and reads the files a system exposes,
rather than reaching for a library, so that what it reports is what `sysctl`
and the proc files say. Unknown is a value, never an exception: a machine that
cannot answer is one the Supervisor sizes as the smallest.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from naiad.domain.capacity import Disk

# How long a probe may take before its answer is taken as unknown.
PROBE_SECONDS = 5.0

# macOS's pressure levels: 1 is normal, 2 a warning and 4 critical.
NORMAL_PRESSURE_LEVEL = 1

# Above this share of the last ten seconds with some task stalled on memory,
# a Linux machine is strained.
STALLED_PERCENT = 10.0

# Below this share of its memory available, a Linux machine with no pressure
# file is strained.
AVAILABLE_SHARE = 0.10


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

    def strained(self) -> bool | None:
        """Whether memory is under pressure, as the operating system reports
        it: `kern.memorystatus_vm_pressure_level` above normal on macOS; on
        Linux the pressure file's `some avg10` above ten, or, where there is no
        such file, less than a tenth of memory available. None when nothing
        answers."""
        if self.platform == "darwin":
            level = _sysctl("kern.memorystatus_vm_pressure_level")
            return None if level is None else level > NORMAL_PRESSURE_LEVEL
        if self.platform.startswith("linux"):
            stalled = _some_avg10(self.proc / "pressure" / "memory")
            if stalled is not None:
                return stalled > STALLED_PERCENT
            meminfo = self.proc / "meminfo"
            total = _meminfo(meminfo, "MemTotal")
            available = _meminfo(meminfo, "MemAvailable")
            if total is None or available is None:
                return None
            return available < total * AVAILABLE_SHARE
        return None

    def free_disk(self, path: Path) -> Disk | None:
        """What the filesystem holding `path` reports. A path not made yet is
        asked of its nearest existing directory, the volume it will land on.
        None when the filesystem does not answer."""
        path = Path(path)
        while not path.exists() and path != path.parent:
            path = path.parent
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            return None
        return Disk(free=usage.free, total=usage.total)


def _some_avg10(path: Path) -> float | None:
    """The `avg10` figure on a pressure file's `some` line: the share of the
    last ten seconds in which some task was stalled."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        kind, *fields = line.split() or [""]
        if kind != "some":
            continue
        for item in fields:
            name, _, value = item.partition("=")
            if name == "avg10":
                try:
                    return float(value)
                except ValueError:
                    return None
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
