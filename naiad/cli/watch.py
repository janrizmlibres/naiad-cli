"""Driving a Run: tick, say what happened, come round again — until it ends.

The one thing decided here is whether to come round again, and even that is
read off the Action rather than worked out: a Finish ends the Run and nothing
else does. Everything else is narration for the operator watching the terminal.

It lives apart from the entry point because a Run that has finished must stop
ticking and a Run waiting on a human must not, and those two are worth
asserting rather than assuming (PRD, 'The Answerer').
"""

from __future__ import annotations

import time
from collections.abc import Callable

from naiad.domain.decide import Action, Clear, Consult, Deliver, Finish, Notify, Nudge, Respond
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
    if RunLog(run.root).finished():
        report(f"{run.id} has already finished")
        return None

    while True:
        action = tick(
            run=run,
            workflow=workflow,
            session=session,
            notifier=notifier,
            answerer=answerer,
            naiad=naiad,
        )
        narration = _narrate(action)
        if narration is not None:
            report(narration)
        if isinstance(action, Finish):
            # The Run is over. Anything left ticking here would be ticking
            # forever: no further Announcement is coming, and the session is
            # deliberately left alive rather than killed.
            return action
        sleep(TICK_SECONDS)


def _narrate(action: Action) -> str | None:
    """What the operator watching the terminal is told. Nothing for the ticks
    where nothing happened, which is most of them."""
    if isinstance(action, Clear):
        again = "" if action.attempt == 1 else f" again (attempt {action.attempt})"
        return f"clearing {action.state}{again}"
    if isinstance(action, Deliver):
        return f"delivered {action.state}"
    if isinstance(action, Consult):
        return f"consulting the answerer: {action.question.text}"
    if isinstance(action, Respond):
        return f"answered: {action.answer}"
    if isinstance(action, Nudge):
        return f"nudged the agent ({action.attempt})"
    if isinstance(action, Notify):
        return f"notified: {action.reason}"
    if isinstance(action, Finish):
        return f"finished at {action.state}"
    return None


__all__ = ["TICK_SECONDS", "watch"]
