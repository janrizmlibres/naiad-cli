"""The one function holding Naiad's rules (ADR 0004).

Signals in, Action out. Nothing here reads a file, runs a subprocess, or looks
at a clock: the tick loop gathers the signals, calls this, and carries out what
comes back, holding no rules of its own. Elapsed time is one of those signals,
so even the timeouts are decided over a number handed in.
"""

from __future__ import annotations

from dataclasses import dataclass

from naiad.domain.announcement import Announcement
from naiad.domain.transitions import next_state
from naiad.domain.workflow import Workflow

# How many Nudges an Announcement is worth before Naiad stops and the human is
# told. The bound is the point: an agent that is genuinely stuck will not
# recover from being asked a third time, and unbounded nudging is Naiad
# fighting the agent rather than driving it (PRD, 'Recovery').
NUDGE_LIMIT = 2

# How long a session that has ended a turn may say nothing before Naiad reads
# it as a forgotten Protocol. Long enough that an agent pausing between tool
# calls is not interrupted mid-thought.
SILENCE_SECONDS = 120.0

# How long a session that has not even ended a turn may produce nothing at all
# before Naiad gives up on it. A hung session never fires Stop, so no signal
# will ever arrive and the wall clock is the only thing left to go on.
HANG_SECONDS = 1800.0


@dataclass(frozen=True)
class Signals:
    """Everything the decision is made from.

    stopped is the safety signal: a turn has ended since the Announcement was
    made. It does not substitute for the Announcement and the Announcement does
    not substitute for it — turns end constantly without the agent being ready
    to advance, and an agent that has announced usually keeps working for a
    while. Delivering into a busy session types over work in progress, and
    Clearing it away is destructive.

    stopped_since_action is the same fact measured from the other end: a turn
    has ended since Naiad last acted, rather than since the Announcement. The
    two cannot be collapsed. The turn end that lets a Prompt be delivered is
    spent by that delivery, and reading it a second time makes every phase that
    outlives the silence bound look silent — so Naiad would nudge an agent
    working normally on what it was just given.

    notified and nudges are facts about the current Announcement rather than
    about the Run, and are re-armed by the next one, so that a Run which needed
    a human once can need one again.

    idle_for is elapsed seconds since the last signal of any kind. It is handed
    in rather than read, so every rule below is testable as data in, Action out.
    """

    announcement: Announcement | None
    handled_seq: int | None
    stopped: bool
    stopped_since_action: bool = False
    notified: bool = False
    nudges: int = 0
    idle_for: float = 0.0


@dataclass(frozen=True)
class Deliver:
    """Send this State's Prompt into the session, Clearing first if asked."""

    state: str
    prompt: str
    clear: bool
    next_state: str | None


@dataclass(frozen=True)
class Nudge:
    """Remind a silent agent of the Protocol. The attempt is carried so the
    second can be worded more firmly than the first; the words themselves are
    the Protocol's business, not a rule."""

    attempt: int


@dataclass(frozen=True)
class Notify:
    """The human is needed. The Run stays alive and keeps ticking — they type,
    the agent announces, and delivery resumes. Only a Terminal State ends a
    Run, which is why this is not Finish."""

    reason: str


@dataclass(frozen=True)
class Nothing:
    """The agent is working, or there is nothing left to act on."""


NOTHING = Nothing()

Action = Deliver | Nudge | Notify | Nothing


def decide(workflow: Workflow, signals: Signals, *, skip_gates: bool = False) -> Action:
    """skip_gates is an option of the Run rather than a signal of it — it does
    not change from tick to tick — so it is a parameter rather than a Signal.
    It only ever changes which State is interpolated into the Prompt; Naiad
    still never writes the State file (ADR 0001).
    """
    announcement = _unhandled(signals)

    if announcement is not None and signals.stopped:
        state = workflow.state(announcement.state)
        if state is None:
            # A State this Workflow does not declare. The announce command
            # rejects one, so this is the agent having found a way around it;
            # there is nothing to deliver and nobody but a human can say what
            # was meant. Recording it as a Deviation is another ticket.
            return _notify(
                signals,
                f"the agent announced '{announcement.state}', "
                f"which is not a State of this workflow",
            )
        if state.prompt is None:
            # A Gate State: there is nothing to deliver and the human types
            # into the session directly. That is why the session must stay
            # alive, and why there is no approve command.
            return _notify(signals, f"state '{state.name}' is a Gate State and is waiting for you")

        successor = next_state(workflow, state.name, skip_gates=skip_gates)
        return Deliver(
            state=state.name,
            prompt=state.prompt,
            clear=state.clear,
            next_state=successor.name if successor else None,
        )

    # Nothing to deliver. Either the agent is working — the common case, and
    # the loop's job is to stay out of its way — or it has gone quiet, and the
    # two ways of going quiet want different answers.
    if signals.stopped_since_action:
        # A turn ended after Naiad last acted and nothing was announced: the
        # session is alive and has most likely forgotten to announce, which a
        # reminder fixes.
        if signals.idle_for < SILENCE_SECONDS:
            return NOTHING
        if signals.nudges < NUDGE_LIMIT:
            return Nudge(attempt=signals.nudges + 1)
        return _notify(signals, f"the agent went silent and did not answer {NUDGE_LIMIT} Nudges")

    # No turn has ended since Naiad acted. Either the agent is working on what
    # it was given, which is the common case and wants leaving alone, or the
    # session has hung — and a hung session never fires Stop, so nothing will
    # nudge it back into life and no signal will ever arrive.
    if signals.idle_for < HANG_SECONDS:
        return NOTHING
    return _notify(signals, f"the session produced no signal for {int(signals.idle_for)}s")


def _unhandled(signals: Signals) -> Announcement | None:
    """The Announcement still owed an Action, if there is one. Naiad acts once
    per Announcement, so one already acted on is as good as none."""
    announcement = signals.announcement
    if announcement is None:
        return None
    if signals.handled_seq is not None and announcement.seq <= signals.handled_seq:
        return None
    return announcement


def _notify(signals: Signals, reason: str) -> Action:
    """Notification is once per Announcement, not once per tick. Every
    condition reaching here persists with identical signals until a human acts,
    so without this the operator is woken every couple of seconds until they do
    (PRD, 'The Answerer')."""
    return NOTHING if signals.notified else Notify(reason=reason)


__all__ = [
    "HANG_SECONDS",
    "NOTHING",
    "NUDGE_LIMIT",
    "SILENCE_SECONDS",
    "Action",
    "Deliver",
    "Nothing",
    "Notify",
    "Nudge",
    "Signals",
    "decide",
]
