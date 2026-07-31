"""The one function holding the Queue's rules — the sibling of the engine's
(ADR 0004).

Signals in, Action out. Nothing here reads a file, runs a subprocess or looks
at a clock: the Supervisor's loop gathers the signals, calls this, and carries
out what comes back, holding no rules of its own.

The rule is one scan. Take the Entries in order, find the first that is not
done; if it has a Run, Resume it, and otherwise Start it. If every Entry is
done, Drained or Idle by mode.

That single scan produces three behaviours with no special case for any of
them. Sequential ordering, because the scan stops at the first unfinished
Entry. A parked Run blocking the Queue (ADR 0012), because a parked Run is not
finished, so the scan keeps returning Resume — and watching a Run already never
returns while it is parked. And crash recovery, because a restarted Supervisor
is handed the same signals and finds the same Entry, which the existing watch
handles in both directions: it reports that a finished Run has finished and
returns, and picks an unfinished one up mid-flight (ADR 0013).
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from naiad.domain.entry import Entry


@dataclass(frozen=True)
class Signals:
    """Everything the Supervisor's decision is made from.

    entries are the Queue in order. The order is settled by whoever gathered
    them — it is id order, and an id is a sortable timestamp — so the rule reads
    the sequence it was handed and sorts nothing itself.

    finished holds the ids of the Runs that have reached a Terminal State. It
    is handed in rather than asked of each Run here, so that every rule below is
    testable as data in, Action out. There is no matching signal for parked or
    running, and deliberately: the scan needs to know only whether an Entry is
    done, and asking for more would have the Queue keeping a status of its own
    (ADR 0013).

    following says Entries added later are to be picked up. It is the whole of
    the difference between the two modes, and it changes nothing but the answer
    to an empty Queue.
    """

    entries: Sequence[Entry]
    finished: Collection[str] = ()
    following: bool = False


@dataclass(frozen=True)
class Start:
    """Start this Entry's Run, then watch it.

    predecessor is what the work stands on, resolved here rather than by the
    loop afterwards, so that picking an Entry and deciding what it stands on are
    one decision exercised by one table of cases. An opaque string: whether to
    actually stand on it is the agent's to decide in the Prompt (ADR 0015).
    """

    entry: Entry
    predecessor: str | None = None


@dataclass(frozen=True)
class Resume:
    """Watch the Run this Entry already has. It has not finished, so it is
    running, or parked and waiting for a human — and the two are the same
    Action, because watching a parked Run is what keeps it tickable until their
    typing revives it."""

    entry: Entry


@dataclass(frozen=True)
class Drained:
    """Nothing waiting, nothing running, and not following. The Supervisor
    returns and the operator gets their prompt back."""


@dataclass(frozen=True)
class Idle:
    """Nothing to do; come round again. The Queue may yet be added to."""


DRAINED = Drained()
IDLE = Idle()

Action = Start | Resume | Drained | Idle


def supervise(signals: Signals) -> Action:
    """One scan, and no second rule beside it.

    An Entry with no Run has not been started, so it is Started. An Entry with
    a Run the finished ids do not name has not ended, so it is Resumed — and
    whether that Run is working or parked is not asked, because both want
    watching and the difference is the Run's to keep rather than the Queue's
    (ADR 0013). Falling off the end means every Entry is done, which is the
    empty Queue again and answers the same way.
    """
    for entry in signals.entries:
        if entry.run_id is None:
            return Start(entry=entry, predecessor=_predecessor(entry))
        if entry.run_id not in signals.finished:
            return Resume(entry=entry)

    return IDLE if signals.following else DRAINED


def _predecessor(entry: Entry) -> str | None:
    """What an Entry's work stands on. The pinned base only, for now; resolving
    it from the Entries before it is the next thing this learns, and Start's
    shape does not change when it does."""
    return entry.pinned_base


__all__ = [
    "DRAINED",
    "IDLE",
    "Action",
    "Drained",
    "Idle",
    "Resume",
    "Signals",
    "Start",
    "supervise",
]
