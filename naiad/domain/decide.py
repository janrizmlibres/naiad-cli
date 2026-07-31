"""The one function holding Naiad's rules (ADR 0004).

Signals in, Action out. Nothing here reads a file, runs a subprocess, or looks
at a clock: the tick loop gathers the signals, calls this, and carries out what
comes back, holding no rules of its own. Elapsed time is one of those signals,
so even the timeouts are decided over a number handed in.
"""

from __future__ import annotations

from dataclasses import dataclass

from naiad.domain.announcement import Announcement
from naiad.domain.answerer import Consultation, Escalated
from naiad.domain.question import Question
from naiad.domain.transitions import next_states as resolve_next_states
from naiad.domain.workflow import State, Workflow

# How many Nudges an Announcement is worth before Naiad stops and the human is
# told. The bound is the point: an agent that is genuinely stuck will not
# recover from being asked a third time, and unbounded nudging is Naiad
# fighting the agent rather than driving it (PRD, 'Recovery').
NUDGE_LIMIT = 2

# How long a typed /clear may go unconfirmed before Naiad reads it as dropped
# and types it again (ADR 0019). Longer than a Clear that lands takes to report
# itself — so a Clear merely in flight is not re-typed — and short enough that a
# genuinely dropped one is caught within a few ticks.
CLEAR_CONFIRM_SECONDS = 8.0

# How many times a State's /clear is typed before the human is told it would not
# land. The silence-then-Nudge bound applied to a Clear: re-typing a dropped one
# is cheap and safe, but an un-cleared context is the one thing delivery must
# never happen into, so past the bound Naiad stops rather than delivers.
CLEAR_RETRY_LIMIT = 3

# How long a session that has ended a turn may say nothing before Naiad reads
# it as a forgotten Protocol. Long enough that an agent pausing between tool
# calls is not interrupted mid-thought.
SILENCE_SECONDS = 120.0

# How long a session that has not even ended a turn may produce nothing at all
# before Naiad gives up on it. A hung session never fires Stop, so no signal
# will ever arrive and the wall clock is the only thing left to go on.
HANG_SECONDS = 1800.0

# What a Wait claims when the agent names no duration (ADR 0021). The order of
# a background review's runtime, so the common case ends by wake rather than by
# expiry.
WAIT_DEFAULT_SECONDS = 600.0

# The most declared waiting one Announcement may buy, however the Waits chain.
# The same order as the hang bound: past it an agent still waiting is a Run
# stalled, and stalling with no human told is the failure a bound exists for.
WAIT_BUDGET_SECONDS = 1800.0


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

    finished says the Run has already reached a Terminal State. It is a fact
    about the Run rather than about an Announcement, and the only one: nothing
    re-arms it, because nothing that arrives afterwards is Naiad's business.

    consultation is what the Answerer has said about the Question currently
    announced, or None if it has not been asked yet. It is a signal rather than
    something fetched here for the reason resolving a Question takes two
    decisions at all: the Answerer returns either an answer or an Escalation,
    and choosing between those is a rule. Branching on it where the Answerer is
    called would put that rule in the adapter layer (ADR 0004).

    waiting says a declared Wait is in force — unexpired at the moment the
    signals were gathered — and wait_reason is what the latest Wait of this
    Announcement said it was for, expired or not. Two signals rather than one,
    because they answer different questions: waiting decides whether the
    silence rule runs at all, and wait_reason lets the Nudge that follows an
    expiry name what was waited on (ADR 0021). Both are facts about the
    current Announcement, re-armed by the next one like nudges.

    holding says a Hold is in force — the agent has declared, on the human's
    instruction, that the Run is in the human's hands — and hold_reason is what
    it said when it did. A Hold has no clock, so unlike waiting there is no
    expired counterpart to read: it stands until the agent signals again, and
    the next Announcement re-arms it like everything else kept per
    Announcement (ADR 0025).

    cleared and clear_attempts are the Clear handshake as signals (ADR 0019).
    cleared says this Announcement's /clear has been confirmed by the
    SessionStart hook; clear_attempts is how many times it has been typed. They
    are facts about the current Announcement, like nudges, and the next one
    re-arms them, so a State whose Clear was dropped is a fresh handshake from
    the State after it.
    """

    announcement: Announcement | None
    handled_seq: int | None
    stopped: bool
    stopped_since_action: bool = False
    notified: bool = False
    nudges: int = 0
    idle_for: float = 0.0
    consultation: Consultation = None
    finished: bool = False
    cleared: bool = False
    clear_attempts: int = 0
    waiting: bool = False
    wait_reason: str | None = None
    holding: bool = False
    hold_reason: str | None = None


@dataclass(frozen=True)
class Clear:
    """Discard this State's context, and wait for the discard to be confirmed
    before its Prompt is delivered (ADR 0019). The /clear can be dropped by the
    terminal, so it is typed again if the confirmation does not come; attempt is
    carried like a Nudge's, so a retry reads apart from the first try in the log.

    A first-class Action rather than a step hidden inside Deliver, so the
    waiting and the retrying are the decision's — elapsed time in, an Action out
    — and the loop keeps no rule of its own (ADR 0004)."""

    state: str
    attempt: int


@dataclass(frozen=True)
class Deliver:
    """Send this State's Prompt into the session.

    The context has already been discarded when the State asked for it: a Clear
    Action does that and is confirmed before this follows (ADR 0019), so a
    delivery never Clears — by the time one is returned there is nothing left to
    discard.

    Carries no Deviation. Delivery happens whether or not the Announcement left
    the expected path, so a Deviation changes nothing here; it classifies the
    Announcement rather than the Action, and is recorded against it
    (naiad.domain.transitions.deviation).

    next_states carries every State the agent may announce from here — one
    usually, both exits at a Branching State. Plural rather than singular so
    that no caller can render a fork as a single name and quietly decide the
    branch on the agent's behalf.

    subject is what the announcing agent said this Announcement was about,
    carried through unread so the Prompt can name it after the Clear has
    discarded the context that chose it (ADR 0009)."""

    state: str
    prompt: str
    next_states: tuple[str, ...]
    subject: str | None = None


@dataclass(frozen=True)
class Nudge:
    """Remind a silent agent of the Protocol. The attempt is carried so the
    second can be worded more firmly than the first; the words themselves are
    the Protocol's business, not a rule.

    expired_wait is what the agent's lapsed Wait said it was waiting on, when
    the silence being answered followed one (ADR 0021). Carried so the wording
    can send the agent to look at that thing first, rather than reading as an
    accusation of forgetting it did not commit."""

    attempt: int
    expired_wait: str | None = None


@dataclass(frozen=True)
class Consult:
    """Put this Question to the Answerer. Nothing is sent into the Run's
    session: what comes back is a signal for the next decision to act on."""

    question: Question


@dataclass(frozen=True)
class Respond:
    """Send the Answerer's answer into the session and append it to the Answer
    log. The Question rides along because the log records the alternatives the
    answer was chosen from, and Naiad is the only party holding both halves."""

    question: Question
    answer: str


@dataclass(frozen=True)
class Notify:
    """The human is needed. The Run stays alive and keeps ticking — they type,
    the agent announces, and delivery resumes. Only a Terminal State ends a
    Run, which is why this is not Finish.

    question is set when what needs a human is an Escalated Question, so that
    the Answer log records what became of it beside the ones that were
    answered. An Escalation is not a separate Action — a Gate reached, an
    Answerer escalating, an agent gone silent and an agent hung are one
    behaviour, and Naiad needs one behaviour here rather than v1's taxonomy."""

    reason: str
    question: Question | None = None


@dataclass(frozen=True)
class Finish:
    """The Run is over: the agent announced a State the Workflow marks
    Terminal. The operator is told the work is done and the tick loop stops,
    which is the whole of what separates this from Notify.

    The State is the outcome — which of a Workflow's ends this Run reached.

    The session is deliberately not touched. It is left alive so that the
    evidence of what the Run did is still there to read, which is exactly what
    the operator wants when the result looks wrong.
    """

    state: str


@dataclass(frozen=True)
class Nothing:
    """The agent is working, or there is nothing left to act on."""


NOTHING = Nothing()

Action = Clear | Consult | Deliver | Finish | Notify | Nudge | Respond | Nothing


def decide(workflow: Workflow, signals: Signals, *, skip_gates: bool = False) -> Action:
    """skip_gates is an option of the Run rather than a signal of it — it does
    not change from tick to tick — so it is a parameter rather than a Signal.
    It only ever changes which State is interpolated into the Prompt; Naiad
    still never writes the State file (ADR 0001).
    """
    if signals.finished:
        # The Run ended. Nothing that arrives now is Naiad's business: the
        # session is left alive for the operator to read and to type into, and
        # an agent that says something more into it is talking to them. Without
        # this a watch started again over a finished Run would drive it on.
        return NOTHING

    announcement = _unhandled(signals)

    ended = _terminal(workflow, signals.announcement)
    if ended is not None and announcement is not None:
        # No turn end is waited for. Finishing sends nothing into the session,
        # so it cannot type over an agent still writing its last paragraph, and
        # a Run whose agent has declared itself done should not be left ticking
        # on a turn end that a session about to be abandoned may never fire.
        return Finish(state=ended.name)

    if announcement is not None and announcement.question is not None:
        # A Question outranks the State it was asked from. The agent is
        # standing in a State it has already been given the Prompt for, so
        # without this the answer to 'which of these two?' would be the Prompt
        # it is in the middle of working on.
        question = announcement.question
        consultation = signals.consultation

        # Consulting and escalating both send nothing into the session, so
        # neither can type over work in progress and neither waits on a turn
        # ending. That exemption is theirs alone.
        if consultation is None:
            return Consult(question=question)
        if isinstance(consultation, Escalated):
            return _notify(
                signals, f"the Answerer escalated: {consultation.reason}", question=question
            )
        if signals.stopped:
            return Respond(question=question, answer=consultation.text)

        # An answer in hand, but no turn has ended. Sending it now would type
        # over an agent still working, exactly as delivering a Prompt would.
        # Falling through rather than returning is deliberate: it leaves the
        # hang rule below reachable, so an answer waiting on a session that has
        # died is not waited on forever.

    if announcement is not None and signals.stopped:
        state = workflow.state(announcement.state)
        if state is None:
            # A State this Workflow does not declare. The announce command
            # rejects one, so this is the agent having found a way around it;
            # there is nothing to deliver and nobody but a human can say what
            # was meant. It is not a Deviation — a Deviation is a legal target
            # reached out of order — but the Run log holds the Announcement and
            # this notification's reason beside it, which is what the operator
            # reads to find out what the agent thought it was doing.
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

        if state.clear and not signals.cleared:
            # The context must be discarded before the Prompt, and the discard
            # confirmed rather than assumed. Until then delivery waits, exactly
            # as it waits on a turn ending above (ADR 0019).
            return _clear(signals, state.name)

        return Deliver(
            state=state.name,
            prompt=state.prompt,
            next_states=resolve_next_states(workflow, state.name, skip_gates=skip_gates),
            subject=announcement.subject,
        )

    # Nothing to deliver. Either the agent is working — the common case, and
    # the loop's job is to stay out of its way — or it has gone quiet, and the
    # two ways of going quiet want different answers.
    if signals.stopped_since_action:
        # A turn ended after Naiad last acted and nothing was announced. A
        # declared Wait says that silence is deliberate — the agent is waiting
        # on something that will come back — so nothing is owed until it
        # expires; expiry re-arms this same rule rather than a new one, with
        # the Nudge naming what was waited on (ADR 0021). Undeclared, the
        # session has most likely forgotten to announce, which a reminder
        # fixes.
        # A Hold is a park the human asked for: the Run parks deliberately,
        # notified once and calmly, and nothing here runs again until the
        # agent signals — no expiry, no budget, no Nudges (ADR 0025). Checked
        # before waiting because the wait command releases any Hold, so both
        # standing means the Hold is the newer declaration.
        if signals.holding:
            return _notify(signals, f"held at your request: {signals.hold_reason}")
        if signals.waiting:
            return NOTHING
        if signals.idle_for < SILENCE_SECONDS:
            return NOTHING
        if signals.nudges < NUDGE_LIMIT:
            return Nudge(attempt=signals.nudges + 1, expired_wait=signals.wait_reason)
        return _notify(signals, f"the agent went silent and did not answer {NUDGE_LIMIT} Nudges")

    # No turn has ended since Naiad acted. Either the agent is working on what
    # it was given, which is the common case and wants leaving alone, or the
    # session has hung — and a hung session never fires Stop, so nothing will
    # nudge it back into life and no signal will ever arrive.
    if signals.idle_for < HANG_SECONDS:
        return NOTHING
    return _notify(signals, f"the session produced no signal for {int(signals.idle_for)}s")


def _terminal(workflow: Workflow, announcement: Announcement | None) -> State | None:
    """The Terminal State this Announcement names, if it names one.

    Terminal is read from the Workflow, so Naiad recognises no State name of
    its own and stays ignorant of what any particular Workflow means.

    An Announcement carrying a Question is never an ending, however Terminal
    the State it was asked from: the agent is standing in that State rather
    than arriving at it, and it is waiting on an answer.
    """
    if announcement is None or announcement.question is not None:
        return None
    state = workflow.state(announcement.state)
    return state if state is not None and state.terminal else None


def _unhandled(signals: Signals) -> Announcement | None:
    """The Announcement still owed an Action, if there is one. Naiad acts once
    per Announcement, so one already acted on is as good as none."""
    announcement = signals.announcement
    if announcement is None:
        return None
    if signals.handled_seq is not None and announcement.seq <= signals.handled_seq:
        return None
    return announcement


def _clear(signals: Signals, state_name: str) -> Action:
    """Get this State's context discarded before its Prompt, catching a dropped
    /clear rather than hoping (ADR 0019).

    The silence-then-Nudge shape applied to a Clear that may be dropped: the
    first /clear goes at once, a confirm window is waited before one is judged
    dropped, a dropped one is re-typed, and past the retry bound the human is
    told rather than the session left un-cleared under a delivery.
    """
    if signals.clear_attempts == 0:
        return Clear(state=state_name, attempt=1)
    if signals.idle_for < CLEAR_CONFIRM_SECONDS:
        return NOTHING
    if signals.clear_attempts < CLEAR_RETRY_LIMIT:
        return Clear(state=state_name, attempt=signals.clear_attempts + 1)
    return _notify(
        signals, f"the clear was not confirmed after {CLEAR_RETRY_LIMIT} tries and looks dropped"
    )


def _notify(signals: Signals, reason: str, *, question: Question | None = None) -> Action:
    """Notification is once per Announcement, not once per tick. Every
    condition reaching here persists with identical signals until a human acts,
    so without this the operator is woken every couple of seconds until they do
    (PRD, 'The Answerer')."""
    return NOTHING if signals.notified else Notify(reason=reason, question=question)


__all__ = [
    "CLEAR_CONFIRM_SECONDS",
    "CLEAR_RETRY_LIMIT",
    "HANG_SECONDS",
    "NOTHING",
    "NUDGE_LIMIT",
    "SILENCE_SECONDS",
    "WAIT_BUDGET_SECONDS",
    "WAIT_DEFAULT_SECONDS",
    "Action",
    "Clear",
    "Consult",
    "Deliver",
    "Finish",
    "Nothing",
    "Notify",
    "Nudge",
    "Respond",
    "Signals",
    "decide",
]
