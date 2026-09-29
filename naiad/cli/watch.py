"""Driving a Run: tick, say what happened, come round again — until it ends.

The one thing decided here is whether to come round again, and even that is
read off the Action rather than worked out: a Finish ends the Run and nothing
else does. Everything else is narration for the operator watching the terminal.

It lives apart from the entry point because a Run that has finished must stop
ticking and a Run waiting on a human must not, and those two are worth
asserting rather than assuming.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from naiad.cli.terminal import cut, first_clause, terminal_width
from naiad.domain.decide import (
    Action,
    Clear,
    Confirm,
    Consult,
    Deliver,
    Finish,
    Notify,
    Nudge,
    Report,
    Respond,
)
from naiad.domain.protocol import DEFAULT_NAIAD
from naiad.domain.workflow import Workflow
from naiad.runtime.log import RunLog
from naiad.runtime.loop import Answerer, Notifier, Session, tick
from naiad.runtime.run import Run

# Fast enough that a finished turn is picked up promptly, slow enough that a
# Run waiting on a human is not spinning.
TICK_SECONDS = 2.0


def watch(
    *,
    run: Run,
    workflow: Workflow,
    session: Session,
    notifier: Notifier,
    answerer: Answerer,
    naiad: str = DEFAULT_NAIAD,
    entry_id: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    report: Callable[[str], None] = print,
) -> Finish | None:
    """Tick until the Run ends, and return the Finish that ended it — or
    nothing at all, if it had already ended before this watch began.

    A Run that has finished is asked about before the first tick rather than
    discovered by ticking, because a finished Run decides Nothing on every
    tick: without this, watching one again would spin forever over a Run that
    is over, which is the thing ending a Run is meant to prevent.

    sleep and report are handed in so that a test can drive the loop without
    waiting on a clock or printing to the operator's terminal; the loop is the
    same one either way.
    """
    if RunLog(run.root).ended():
        report(f"{run.id} has already ended")
        return None

    while True:
        action = tick_once(
            run=run,
            workflow=workflow,
            session=session,
            notifier=notifier,
            answerer=answerer,
            naiad=naiad,
            entry_id=entry_id,
            report=report,
        )
        if isinstance(action, Finish):
            # The Run is over. Anything left ticking here would be ticking
            # forever: no further Announcement is coming, and the session is
            # deliberately left alive rather than killed.
            return action
        sleep(TICK_SECONDS)


def tick_once(
    *,
    run: Run,
    workflow: Workflow,
    session: Session,
    notifier: Notifier,
    answerer: Answerer,
    naiad: str = DEFAULT_NAIAD,
    entry_id: str | None = None,
    report: Callable[[str], None] = print,
    lead: int = 0,
) -> Action:
    """One tick of a Run, narrated. The watch is this in a loop; the
    Supervisor calls it once per pass per lane instead, so the two
    drive a Run through the same tick with the same narration.

    lead is how many columns the caller prints before the narration, as the
    Supervisor prefixes the Run it belongs to: the lines cut to the terminal
    width are cut to what is left of it."""
    action = tick(
        run=run,
        workflow=workflow,
        session=session,
        notifier=notifier,
        answerer=answerer,
        naiad=naiad,
        entry_id=entry_id,
    )
    narration = _narrate(action, width=max(terminal_width() - lead, 1))
    if narration is not None:
        report(narration)
    return action


def _narrate(action: Action, *, width: int) -> str | None:
    """What the operator watching the terminal is told. Nothing for the ticks
    where nothing happened, which is most of them.

    The two lines that carry a Question's or an Answer's words are one line
    cut to width, options dropped and the answer's first clause kept: they run
    long and repeat for every Question, and the Run's Answer log holds the rest
    (`naiad queue answers`)."""
    if isinstance(action, Clear):
        again = "" if action.attempt == 1 else f" again (attempt {action.attempt})"
        return f"clearing {action.state}{again}"
    if isinstance(action, Deliver):
        again = "" if action.attempt == 1 else f" again (attempt {action.attempt})"
        return f"delivered {action.state}{again}"
    if isinstance(action, Confirm):
        return f"confirmed {action.state} landed"
    if isinstance(action, Consult):
        return cut(f"consulting the answerer: {_one_line(action.question.text)}", width)
    if isinstance(action, Respond):
        return cut(f"answered: {_one_line(first_clause(action.answer))}", width)
    if isinstance(action, Nudge):
        expired = "" if action.expired_wait is None else f" after its wait on '{action.expired_wait}' expired"
        return f"nudged the agent ({action.attempt}){expired}"
    if isinstance(action, Notify):
        return f"notified: {action.reason}"
    if isinstance(action, Report):
        return f"reported entering {action.state}"
    if isinstance(action, Finish):
        return f"finished at {action.state}"
    return None


def _one_line(text: str) -> str:
    """A Question or Answer with its line breaks made spaces: written as a
    paragraph, echoed as a line."""
    return " ".join(text.split())


__all__ = ["TICK_SECONDS", "tick_once", "watch"]
