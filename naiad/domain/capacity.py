"""The ceiling on live Runs, resolved once when the Supervisor starts.

The nearest instruction wins: the Supervisor commands' option, then the
environment variable, then what the machine's memory allows. A Run's Session
is a Claude Code process and its tools, so the derived ceiling keeps a reserve
for the operating system and everything else the operator has open, and gives
each Run a share of the rest.

Below the ceiling, the machine also has to be unstrained: no Run starts into a
working tree whose volume is short of free disk, so that worktrees and installs
never fill it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

CAPACITY_VARIABLE = "NAIAD_CAPACITY"

GIB = 1 << 30

# Kept back for the operating system and whatever else the operator runs.
RESERVED = 8 * GIB

# What one live Run is sized at.
PER_RUN = 3 * GIB // 2

GB = 10**9

# The least free disk a Run is started into: the larger of this share of the
# volume and this many bytes, so that a small disk keeps room in proportion and
# a large one keeps more than a rounding error.
DISK_SHARE = 0.10
DISK_FLOOR = 10 * GB


class CapacityError(Exception):
    """A ceiling given that is not one."""


@dataclass(frozen=True)
class Disk:
    """What the filesystem holding a path reports, in bytes."""

    free: int
    total: int


def low_on_disk(disk: Disk | None) -> bool:
    """Whether free disk is below the larger of a tenth of the volume and
    10 GB. A disk that could not be read is not low, so that a machine that
    cannot answer is held to the ceiling alone."""
    if disk is None:
        return False
    return disk.free < max(disk.total * DISK_SHARE, DISK_FLOOR)


def ceiling_for(total_memory: int | None) -> int:
    """max(1, ⌊(total memory − reserve) ÷ per Run⌋). A machine that cannot say
    what it has is sized as the smallest, so that it still runs one."""
    if total_memory is None:
        return 1
    return max(1, (total_memory - RESERVED) // PER_RUN)


def capacity_given(text: str) -> int | None:
    """A ceiling written by the operator, or None when it is not a positive
    whole number. Plain digits only, because `int` would also read `2_0` as
    twenty and ` 3` as three."""
    if not (text.isascii() and text.isdigit()):
        return None
    number = int(text)
    return number if number >= 1 else None


def resolve_ceiling(
    *, option: int | None, variable: str | None, total_memory: Callable[[], int | None]
) -> int:
    """The ceiling from the nearest instruction. The machine is read only when
    nothing nearer was given. A variable that is set but not a ceiling is
    refused rather than passed over, so that a typo does not quietly mean the
    derived ceiling."""
    if option is not None:
        return option
    if variable is not None:
        given = capacity_given(variable)
        if given is None:
            raise CapacityError(
                f"{CAPACITY_VARIABLE} is '{variable}', which is not a positive whole "
                f"number; set it to N, such as 4, or unset it to size by memory"
            )
        return given
    return ceiling_for(total_memory())


__all__ = [
    "CAPACITY_VARIABLE",
    "DISK_FLOOR",
    "DISK_SHARE",
    "GB",
    "CapacityError",
    "Disk",
    "capacity_given",
    "ceiling_for",
    "low_on_disk",
    "resolve_ceiling",
]
