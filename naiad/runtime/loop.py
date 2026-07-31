"""The tick: gather the signals, ask the decision function, carry out the answer.

There is deliberately no rule here. Whether to deliver, whether to Clear first,
which State comes next, whether the agent has been quiet long enough to be
nudged and whether the operator has already been told were all decided in
naiad.domain.decide (ADR 0004); what is left is reading a few files, one call,
and a dispatch. If a condition ever needs adding to this module, it belongs in
the decision function instead.
"""

from __future__ import annotations

import time
from typing import Protocol

from naiad.domain.decide import Action, Deliver, Notify, Nudge, Signals, decide
from naiad.domain.prompt import render_prompt
from naiad.domain.protocol import DEFAULT_NAIAD, render_nudge
from naiad.domain.workflow import Workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.records import Handled, Notices, Turns, idle_seconds
from naiad.runtime.run import Run


class UndrivableRun(Exception):
    """A Run with no session to deliver into."""


class Session(Protocol):
    def send(self, pane: str, text: str) -> None: ...
    def clear(self, pane: str) -> None: ...


class Notifier(Protocol):
    def notify(self, title: str, message: str) -> None: ...


def tick(
    *,
    run: Run,
    workflow: Workflow,
    session: Session,
    notifier: Notifier,
    now: float | None = None,
    naiad: str = DEFAULT_NAIAD,
) -> Action:
    """now is a parameter so the rules that depend on elapsed time can be
    driven from data rather than from a test that waits. Every other caller
    means the current moment, so that is what it defaults to."""
    announcement = Announcements(run.root).latest()
    turns = Turns(run.root)
    handled = Handled(run.root)
    notices = Notices(run.root)
    notified, nudges = notices.of(announcement)

    action = decide(
        workflow,
        Signals(
            announcement=announcement,
            handled_seq=handled.seq(),
            stopped=turns.ended_since(announcement),
            stopped_since_action=turns.ended_since_action(handled),
            notified=notified,
            nudges=nudges,
            idle_for=idle_seconds(run.root, now=now if now is not None else time.time()),
        ),
        skip_gates=run.skip_gates,
    )

    if isinstance(action, Deliver) and announcement is not None:
        pane = _pane(run)
        if action.clear:
            session.clear(pane)
        session.send(
            pane,
            render_prompt(action.prompt, task=run.task, next_state=action.next_state),
        )
        handled.record(announcement.seq, turns=turns.count())
    elif isinstance(action, Nudge):
        session.send(_pane(run), render_nudge(attempt=action.attempt, naiad=naiad))
        notices.record_nudge(announcement)
    elif isinstance(action, Notify):
        notifier.notify(title=f"naiad: {run.id}", message=action.reason)
        notices.record_notified(announcement)

    return action


def _pane(run: Run) -> str:
    pane = run.tmux_pane
    if not pane:
        # tmux reads an empty -t target as the attached pane, so coercing a
        # missing one would deliver into whatever session the operator is
        # looking at — and Clear it first.
        raise UndrivableRun(f"run {run.id} has no pane recorded to deliver into")
    return pane


__all__ = ["Notifier", "Session", "tick"]
