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

from rich.text import Text

from naiad.cli.style import Styled, say
from naiad.cli.terminal import first_clause, terminal_width
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
from naiad.runtime.queue import Queue
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
    queue: Queue | None = None,
    sleep: Callable[[float], None] = time.sleep,
    report: Callable[[str], None] = say,
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
        report(Styled.assemble((run.id, "id"), " ", ("has already ended", "event.ended")))
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
            queue=queue,
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
    queue: Queue | None = None,
    report: Callable[[str], None] = say,
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
        queue=queue,
    )
    narration = _narrate(action, width=max(terminal_width() - lead, 1))
    if narration is not None:
        report(narration)
    return action


def _narrate(action: Action, *, width: int) -> Styled | None:
    """What the operator watching the terminal is told. Nothing for the ticks
    where nothing happened, which is most of them.

    Each line is led by its verb, styled for what kind of thing happened, and
    names its State as a State; how each piece is styled is said here, where
    the line is worded, rather than read back out of the words where it is
    printed. The words are the same for a reader that sees no styles.

    The two lines that carry a Question's or an Answer's words are one line
    cut to width, options dropped and the answer's first clause kept: they run
    long and repeat for every Question, and the Run's Answer log holds the rest
    (`naiad queue answers`). They are cut as text, so the styles cost no
    width."""
    if isinstance(action, Clear):
        return Styled.assemble(
            ("clearing", "event.progress"), " ", (action.state, "state"), _again(action.attempt)
        )
    if isinstance(action, Deliver):
        return Styled.assemble(
            ("delivered", "event.progress"), " ", (action.state, "state"), _again(action.attempt)
        )
    if isinstance(action, Confirm):
        return Styled.assemble(
            ("confirmed", "event.progress"), " ", (action.state, "state"), " landed"
        )
    if isinstance(action, Consult):
        return _cut(
            Text.assemble(
                ("consulting the answerer:", "event.attention"),
                f" {_one_line(action.question.text)}",
            ),
            width,
        )
    if isinstance(action, Respond):
        return _cut(
            Text.assemble(
                ("answered:", "event.attention"), f" {_one_line(first_clause(action.answer))}"
            ),
            width,
        )
    if isinstance(action, Nudge):
        expired = (
            ""
            if action.expired_wait is None
            else f" after its wait on '{action.expired_wait}' expired"
        )
        return Styled.assemble(
            ("nudged the agent", "event.attention"), f" ({action.attempt}){expired}"
        )
    if isinstance(action, Notify):
        return Styled.assemble(("notified:", "event.attention"), f" {action.reason}")
    if isinstance(action, Report):
        return Styled.assemble(
            ("reported entering", "event.progress"), " ", (action.state, "state")
        )
    if isinstance(action, Finish):
        return Styled.assemble(("finished at", "event.ended"), " ", (action.state, "state"))
    return None


def _cut(text: Text, width: int) -> Styled:
    """The line as it fits in width columns: whole when it fits, otherwise
    truncated with an ellipsis in the last of them, measured in cells."""
    text.truncate(width, overflow="ellipsis")
    return Styled(text)


def _again(attempt: int) -> tuple[str, str] | str:
    """A retry said aside: the line is about the State, and the count is only
    which try this was."""
    return "" if attempt == 1 else (f" again (attempt {attempt})", "secondary")


def _one_line(text: str) -> str:
    """A Question or Answer with its line breaks made spaces: written as a
    paragraph, echoed as a line."""
    return " ".join(text.split())


__all__ = ["TICK_SECONDS", "tick_once", "watch"]
