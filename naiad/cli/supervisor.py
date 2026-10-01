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
from typing import assert_never

from naiad.domain.entry import Entry
from naiad.domain.supervise import Drained, Idle, Resume, Signals, Start, supervise
from naiad.runtime.home import StorageError
from naiad.runtime.queue import DONE, Queue, branch_of, status_of
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


def supervise_queue(
    *,
    queue: Queue,
    runs: RunStore,
    start: Callable[[Entry, str | None], Run],
    tick: Callable[[Run], None],
    following: bool,
    sleep: Callable[[float], None] = time.sleep,
    report: Callable[[str], None] = print,
) -> None:
    """Take the Queue lane by lane until it is drained, or forever when
    following.

    sleep and report are handed in so that a test can drive the loop without
    waiting on a clock or printing to the operator's terminal; the loop is the
    same one either way.
    """
    # Which Runs this Supervisor has already said it is driving. Narration
    # rather than state: a Resume comes round every pass by design, and the
    # operator is told about each Run once, not once per tick.
    announced: set[str] = set()

    while True:
        entries = queue.all()
        scanned = supervise(
            Signals(
                entries=entries,
                finished=_finished(entries, runs),
                following=following,
                declared=_declared(entries, runs),
            )
        )

        if isinstance(scanned, Idle):
            # Dispatched on the Action rather than on `following`, which the
            # rules have already read: a second look at it here would be this
            # module deciding something.
            sleep(POLL_SECONDS)
            continue
        if isinstance(scanned, Drained):
            report("the queue is drained")
            return

        for action in scanned:
            if isinstance(action, Start):
                entry = action.entry
                report(f"starting {entry.id}: {entry.task}")
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
                    report(f"resuming {entry.id}: {entry.task}")
                tick(run)
            else:
                # Named rather than left to fall through, so that an Action
                # added to the rules is a type error here rather than a lane
                # that is quietly never ticked.
                assert_never(action)

        sleep(TICK_SECONDS)


def _finished(entries: Sequence[Entry], runs: RunStore) -> set[str]:
    """Which of the Entries' Runs have ended, asked of the Runs rather than of
    a status the Queue keeps. Through the same reader the listing
    uses, so that one place decides what makes an Entry done."""
    return {
        entry.run_id
        for entry in entries
        if entry.run_id is not None and status_of(entry, runs) == DONE
    }


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
