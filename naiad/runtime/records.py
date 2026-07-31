"""What Naiad records about a Run, as distinct from what the agent records.

Two facts, two files. The State file is the agent's and Naiad never writes it
(ADR 0001), so Naiad's own bookkeeping lives beside it rather than in it. The
two records are also written by different processes — a Stop hook fires while
the tick loop is running — so they stay separate files rather than racing over
one.
"""

from __future__ import annotations

import json
from pathlib import Path

from naiad.domain.announcement import Announcement
from naiad.runtime.atomic import write_atomically

TURNS_FILENAME = "turns.json"
HANDLED_FILENAME = "handled.json"


def _read(path: Path) -> dict[str, int | None]:
    try:
        document: dict[str, int | None] = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    return document


def _write(path: Path, document: dict[str, int | None]) -> None:
    write_atomically(path, json.dumps(document, indent=2) + "\n")


class Turns:
    """When a turn last ended, written by the Stop hook.

    The end of a turn is recorded against the Announcement that was current
    when it happened, rather than against a clock. A turn that ended while
    Announcement 2 was current says nothing about Announcement 3, which the
    agent made afterwards and is still working on.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / TURNS_FILENAME

    def record_end(self, *, latest_seq: int | None) -> None:
        _write(self.path, {"after_seq": latest_seq})

    def ended_since(self, announcement: Announcement | None) -> bool:
        if announcement is None:
            return False
        after = _read(self.path).get("after_seq")
        return after is not None and after >= announcement.seq


class Handled:
    """The last Announcement Naiad acted on, so that it acts once per
    Announcement rather than once per change of value."""

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / HANDLED_FILENAME

    def seq(self) -> int | None:
        return _read(self.path).get("seq")

    def record(self, seq: int) -> None:
        _write(self.path, {"seq": seq})


__all__ = ["Handled", "Turns"]
