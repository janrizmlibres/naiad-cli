"""The Supervisor's loop: gather the signals, ask the rules, carry out the answer.

There is deliberately no rule here. Which Entry is next, whether it is started
or resumed, what its work stands on, and whether an empty Queue is the end or
merely a pause were all decided in naiad.domain.supervise; what is left is
reading the Queue, one call, and a dispatch. If a condition ever needs adding
to this module, it belongs in the decision function instead.

Starting a Run and driving one are handed in rather than reached for, because
they are the two things that open a session and tick a clock, and the loop is
worth driving in a test without either.

The Supervisor holds no Run of its own. Which Run is live is derivable from the
Entries on every pass, so a concurrent Queue later is an addition rather than a
rewrite (ADR 0012).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import assert_never

from naiad.domain.entry import Entry
from naiad.domain.supervise import Drained, Idle, Resume, Signals, Start, supervise
from naiad.runtime.home import StorageError
from naiad.runtime.queue import DONE, Queue, status_of
from naiad.runtime.run import Run, RunStore

# How long a following Supervisor waits before looking at the Queue again.
# Fast enough that work queued from a session starts promptly, slow enough that
# a Supervisor with nothing to do is not spinning.
POLL_SECONDS = 5.0


def supervise_queue(
    *,
    queue: Queue,
    runs: RunStore,
    start: Callable[[Entry, str | None], Run],
    drive: Callable[[Run], None],
    following: bool,
    sleep: Callable[[float], None] = time.sleep,
    report: Callable[[str], None] = print,
) -> None:
    """Take the Queue in order until it is drained, or forever when following.

    sleep and report are handed in so that a test can drive the loop without
    waiting on a clock or printing to the operator's terminal; the loop is the
    same one either way.
    """
    while True:
        entries = queue.all()
        action = supervise(
            Signals(entries=entries, finished=_finished(entries, runs), following=following)
        )

        if isinstance(action, Start):
            entry = action.entry
            report(f"starting {entry.id}: {entry.task}")
            run = start(entry, action.predecessor)
            # Recorded before the Run is driven rather than after it, because
            # this is what a Supervisor restarted mid-Run reads to find the same
            # Entry again — and recorded afterwards it would be lost by exactly
            # the interruption it is for.
            #
            # A window remains between the two: a Supervisor killed here has
            # opened a session the Entry does not know about, and starting again
            # opens a second. It is left rather than closed because closing it
            # means minting the Run's id before the Run, which would put an id
            # on an Entry for a Run that may never exist — trading a narrow
            # window for a permanent lie.
            queue.attach_run(entry, run_id=run.id)
            drive(run)
        elif isinstance(action, Resume):
            entry = action.entry
            report(f"resuming {entry.id}: {entry.task}")
            drive(_run_of(entry, runs))
        elif isinstance(action, Idle):
            # Dispatched on the Action rather than on `following`, which the
            # rules have already read: a second look at it here would be this
            # module deciding something.
            sleep(POLL_SECONDS)
        elif isinstance(action, Drained):
            report("the queue is drained")
            return
        else:
            # Named rather than left to fall through, so that an Action added
            # to the rules is a type error here rather than a Queue that
            # quietly reports itself drained.
            assert_never(action)


def _finished(entries: Sequence[Entry], runs: RunStore) -> set[str]:
    """Which of the Entries' Runs have ended, asked of the Runs rather than of
    a status the Queue keeps (ADR 0013). Through the same reader the listing
    uses, so that one place decides what makes an Entry done."""
    return {
        entry.run_id
        for entry in entries
        if entry.run_id is not None and status_of(entry, runs) == DONE
    }


def _run_of(entry: Entry, runs: RunStore) -> Run:
    """The Run an Entry became, or a refusal naming it.

    A Run whose directory has gone records no ending, so `status_of` reads it as
    running — the honest answer, since nothing left on disk says otherwise — and
    the scan keeps choosing its Entry. There is nothing to drive, so the
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


__all__ = ["POLL_SECONDS", "supervise_queue"]
