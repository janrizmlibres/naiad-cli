"""The Supervisor's loop: gather the signals, ask the rules, carry out the answer.

There is deliberately no rule here. Which Entry is next in each lane, whether
it is started or resumed, and what its work stands on were all decided in
naiad.domain.supervise; what is left is reading the Queue, one call, and a
dispatch. If a condition ever needs adding to this module, it belongs in the
decision function instead.

One pass carries every lane: each Action the rules return is a
lane's live Run, started if it does not exist yet and then ticked once
before the pass sleeps and comes round again. Driving a Run was always
repeated calls to a pure tick, so the interleaving hoists that loop up a level
rather than adding threads or child processes; the Runs' sessions are what run
concurrently, and they are tmux's processes rather than Naiad's.

Starting a Run and ticking one are handed in rather than reached for, because
they are the two things that open a session and tick a clock, and the loop is
worth driving in a test without either.

The Supervisor holds no Run of its own. Which Runs are live is derivable from
the Entries on every pass.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, assert_never

from naiad.cli.style import Styled, say
from naiad.domain.capacity import DISK_FLOOR, DISK_SHARE, GB, Disk, low_on_disk
from naiad.domain.entry import Entry
from naiad.domain.supervise import (
    CEILING,
    DISK,
    MEMORY,
    AtCapacity,
    Drained,
    Idle,
    Reason,
    Resume,
    Signals,
    Start,
    supervise,
)
from naiad.runtime.home import StorageError
from naiad.runtime.queue import DONE, JOINING, Queue, Status, branch_of, status_of
from naiad.runtime.records import Children
from naiad.runtime.run import Run, RunStore

# How long a following Supervisor waits before looking at the Queue again.
# Fast enough that work queued from a session starts promptly, slow enough that
# a Supervisor with nothing to do is not spinning.
POLL_SECONDS = 5.0

# How long a pass with live Runs waits before ticking them again. Fast enough
# that a finished turn is picked up promptly, slow enough that Runs waiting on
# their agents are not spinning.
TICK_SECONDS = 2.0


class MachineReading(Protocol):
    """What the Supervisor asks of the machine each pass."""

    def strained(self) -> bool | None: ...

    def free_disk(self, path: Path) -> Disk | None: ...


def supervise_queue(
    *,
    queue: Queue,
    runs: RunStore,
    start: Callable[[Entry, str | None], Run],
    tick: Callable[[Run], None],
    following: bool,
    sleep: Callable[[float], None] = time.sleep,
    report: Callable[[str], None] = say,
    ceiling: int | None = None,
    machine: MachineReading | None = None,
) -> None:
    """Take the Queue lane by lane until it is drained, or forever when
    following.

    ceiling is how many Runs may be live at once, resolved by the caller when
    the Supervisor started; None sets none. machine is read each pass for
    memory pressure and free disk; None reads nothing, as a machine that
    answers neither.

    sleep and report are handed in so that a test can drive the loop without
    waiting on a clock or printing to the operator's terminal; the loop is the
    same one either way.
    """
    # Which Runs this Supervisor has already said it is driving. Narration
    # rather than state: a Resume comes round every pass by design, and the
    # operator is told about each Run once, not once per tick.
    announced: set[str] = set()
    # Why nothing started on the last pass, so that the operator is told once
    # each time it changes rather than every pass it stays the same.
    reported: Reason | None = None

    while True:
        entries = queue.all()
        statuses = _statuses(entries, runs, queue)
        scanned = supervise(
            Signals(
                entries=entries,
                finished={run_id for run_id, status in statuses.items() if status == DONE},
                following=following,
                declared=_declared(entries, runs),
                ceiling=ceiling,
                joining={run_id for run_id, status in statuses.items() if status == JOINING},
                strained=machine is not None and machine.strained() is True,
                low_disk=_low_disk(entries, machine),
            )
        )

        if isinstance(scanned, Idle):
            # Dispatched on the Action rather than on `following`, which the
            # rules have already read: a second look at it here would be this
            # module deciding something.
            sleep(POLL_SECONDS)
            continue
        if isinstance(scanned, Drained):
            report(Styled.assemble(("the queue is drained", "event.ended")))
            return

        reason = next(
            (action.reason for action in scanned if isinstance(action, AtCapacity)), None
        )
        if reason is not None and reason != reported:
            report(_held_back(reason, ceiling=ceiling))
        reported = reason

        for action in scanned:
            if isinstance(action, AtCapacity):
                continue
            if isinstance(action, Start):
                entry = action.entry
                report(_taking("starting", entry))
                run = start(entry, action.predecessor)
                # A Child needs no rule of its own to start, its working tree
                # being a Lane of its own; what is owed is the Run it became,
                # on its Parent's record. Written before the Entry learns it,
                # so that the narrow window below leaves the record naming the
                # Run a restarted Supervisor would start in its place rather
                # than none.
                # A Parent whose Run directory has gone is given no stub of one.
                if entry.parent is not None and runs.load(entry.parent) is not None:
                    Children(runs.root_for(entry.parent)).record_start(
                        entry.id, run_id=run.id
                    )
                # Recorded before the Run is ticked rather than after it,
                # because this is what a Supervisor restarted mid-Run reads to
                # find the same Entry again — and recorded afterwards it would
                # be lost by exactly the interruption it is for.
                #
                # A window remains between the two: a Supervisor killed here
                # has opened a session the Entry does not know about, and
                # starting again opens a second. It is left rather than closed
                # because closing it means minting the Run's id before the
                # Run, which would put an id on an Entry for a Run that may
                # never exist — trading a narrow window for a permanent lie.
                queue.attach_run(entry, run_id=run.id)
                announced.add(run.id)
                tick(run)
            elif isinstance(action, Resume):
                entry = action.entry
                run = _run_of(entry, runs)
                if run.id not in announced:
                    announced.add(run.id)
                    report(_taking("resuming", entry))
                tick(run)
            else:
                # Named rather than left to fall through, so that an Action
                # added to the rules is a type error here rather than a lane
                # that is quietly never ticked.
                assert_never(action)

        sleep(TICK_SECONDS)


def _statuses(entries: Sequence[Entry], runs: RunStore, queue: Queue) -> dict[str, Status]:
    """What became of each started Entry's Run, asked of the Runs rather than
    of a status the Queue keeps. Through the same reader the listing uses, so
    that one place decides what makes a Run done or joining."""
    return {
        entry.run_id: status_of(entry, runs, queue)
        for entry in entries
        if entry.run_id is not None
    }


def _low_disk(entries: Sequence[Entry], machine: MachineReading | None) -> set[Path]:
    """The working trees waiting to start whose volume is short of free disk.
    Only those not started are asked, because a live Run is never held back."""
    if machine is None:
        return set()
    return {
        entry.target_repo
        for entry in entries
        if entry.run_id is None and low_on_disk(machine.free_disk(entry.target_repo))
    }


def _taking(verb: str, entry: Entry) -> Styled:
    """The operator's line for an Entry the Supervisor is taking up: what it
    is doing, which Entry, and the work."""
    return Styled.assemble((verb, "event.progress"), " ", (entry.id, "id"), f": {entry.task}")


def _held_back(reason: Reason, *, ceiling: int | None) -> Styled:
    """The operator's line for why nothing is starting."""
    return Styled.assemble(
        ("not starting anything:", "event.attention"), " ", _why_held_back(reason, ceiling)
    )


def _why_held_back(reason: Reason, ceiling: int | None) -> str:
    if reason == CEILING:
        return f"the ceiling of {ceiling} live runs is reached"
    if reason == MEMORY:
        return "the machine reports memory under pressure"
    if reason == DISK:
        return (
            "free disk where the waiting runs would work is "
            f"below the larger of {DISK_SHARE:.0%} and {DISK_FLOOR // GB} GB"
        )
    assert_never(reason)


def _declared(entries: Sequence[Entry], runs: RunStore) -> dict[str, str]:
    """The branches Runs declared for Entries whose own record carries none,
    read through the same resolver the claim check uses, so that one
    place decides what branch an Entry works on. A Run that never declared —
    or whose directory has gone — resolves to nothing and is simply absent."""
    return {
        entry.id: branch
        for entry in entries
        if entry.working_branch is None and (branch := branch_of(entry, runs)) is not None
    }


def _run_of(entry: Entry, runs: RunStore) -> Run:
    """The Run an Entry became, or a refusal naming it.

    A Run whose directory has gone records no ending, so `status_of` reads it as
    running — the honest answer, since nothing left on disk says otherwise — and
    the scan keeps choosing its Entry. There is nothing to tick, so the
    Supervisor would resume nothing forever.

    Not a rule, and so not the decision function's: it is the refusal an adapter
    makes when what it was told to drive is not there, in the shape
    naiad.runtime.loop refuses a Run with no pane to deliver into. Said out loud
    because only the operator can decide whether to remove the Entry or put the
    Run back.
    """
    run = None if entry.run_id is None else runs.load(entry.run_id)
    if run is None:
        raise StorageError(
            f"entry '{entry.id}' became run '{entry.run_id}', which is not under "
            f"{runs.root}; remove the entry or restore the run"
        )
    return run


__all__ = ["POLL_SECONDS", "TICK_SECONDS", "supervise_queue"]
