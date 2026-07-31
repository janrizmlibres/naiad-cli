"""The tick: gather the signals, ask the decision function, carry out the answer.

There is deliberately no rule here. Whether to deliver, whether to Clear first,
and which State comes next were all decided in naiad.domain.decide (ADR 0004);
what is left is reading three files, one call, and a dispatch. If a condition
ever needs adding to this module, it belongs in the decision function instead.
"""

from __future__ import annotations

from typing import Protocol

from naiad.domain.decide import Action, Deliver, Signals, decide
from naiad.domain.prompt import render_prompt
from naiad.domain.workflow import Workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.records import Handled, Turns
from naiad.runtime.run import Run


class UndrivableRun(Exception):
    """A Run with no session to deliver into."""


class Session(Protocol):
    def send(self, pane: str, text: str) -> None: ...
    def clear(self, pane: str) -> None: ...


def tick(*, run: Run, workflow: Workflow, session: Session) -> Action:
    announcement = Announcements(run.root).latest()
    turns = Turns(run.root)
    handled = Handled(run.root)

    action = decide(
        workflow,
        Signals(
            announcement=announcement,
            handled_seq=handled.seq(),
            stopped=turns.ended_since(announcement),
        ),
    )

    if isinstance(action, Deliver) and announcement is not None:
        pane = run.tmux_pane
        if not pane:
            # tmux reads an empty -t target as the attached pane, so coercing a
            # missing one would deliver into whatever session the operator is
            # looking at — and Clear it first.
            raise UndrivableRun(f"run {run.id} has no pane recorded to deliver into")
        if action.clear:
            session.clear(pane)
        session.send(
            pane,
            render_prompt(action.prompt, task=run.task, next_state=action.next_state),
        )
        handled.record(announcement.seq)

    return action


__all__ = ["Session", "tick"]
