"""The one function holding Naiad's rules (ADR 0004).

Signals in, Action out. Nothing here reads a file, runs a subprocess, or looks
at a clock: the tick loop gathers the signals, calls this, and carries out what
comes back, holding no rules of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from naiad.domain.announcement import Announcement
from naiad.domain.workflow import Workflow


@dataclass(frozen=True)
class Signals:
    """Everything the decision is made from.

    stopped is the safety signal: a turn has ended since the Announcement was
    made. It does not substitute for the Announcement and the Announcement does
    not substitute for it — turns end constantly without the agent being ready
    to advance, and an agent that has announced usually keeps working for a
    while. Delivering into a busy session types over work in progress, and
    Clearing it away is destructive.
    """

    announcement: Announcement | None
    handled_seq: int | None
    stopped: bool


@dataclass(frozen=True)
class Deliver:
    """Send this State's Prompt into the session, Clearing first if asked."""

    state: str
    prompt: str
    clear: bool
    next_state: str | None


@dataclass(frozen=True)
class Nothing:
    """The agent is working, or there is nothing left to act on."""


NOTHING = Nothing()

Action = Deliver | Nothing


def decide(workflow: Workflow, signals: Signals) -> Action:
    announcement = signals.announcement
    if announcement is None:
        return NOTHING

    if signals.handled_seq is not None and announcement.seq <= signals.handled_seq:
        return NOTHING

    if not signals.stopped:
        return NOTHING

    # A State with no Prompt is a Gate State: there is nothing to deliver and
    # the human types into the session directly. Notifying them that they are
    # needed, and recording a Deviation for a State that is not the expected
    # next one, are both still to come.
    state = workflow.state(announcement.state)
    if state is None or state.prompt is None:
        return NOTHING

    successor = workflow.successor(state.name)
    return Deliver(
        state=state.name,
        prompt=state.prompt,
        clear=state.clear,
        next_state=successor.name if successor else None,
    )


__all__ = ["NOTHING", "Action", "Deliver", "Nothing", "Signals", "decide"]
