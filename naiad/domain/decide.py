"""The one function holding Naiad's rules (ADR 0004).

Signals in, Action out. Nothing here reads a file, runs a subprocess, or looks
at a clock: the tick loop gathers the signals, calls this, and carries out what
comes back, holding no rules of its own. Elapsed time is one of those signals,
so even the timeouts are decided over a number handed in.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Literal

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

# How long a typed Prompt may go without the UserPromptSubmit hook reporting it
# before Naiad reads it as never having reached the Session (ADR 0053). The
# Clear's window, for the Clear's reason: a Prompt that reaches the Session is
# reported at once, so the window is only ever spent on one that did not.
DELIVERY_CONFIRM_SECONDS = CLEAR_CONFIRM_SECONDS

# How many times a State's Prompt is typed before the human is told it would
# not arrive whole. A Prompt the Session took cut short is turned away by the
# hook and typed again, and past the bound Naiad stops rather than lets the
# agent work from part of what its State asks.
DELIVERY_RETRY_LIMIT = 3

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
class Opening:
    """The Prompt a Run has been given a session for and has not been given
    (ADR 0028).

    An Adoption alone has one. A Run that spawned its session was handed its
    first Prompt as that session launched, so it is owed nothing before it
    announces; a Run that joined a session already running was handed nothing,
    and what it is owed is the Prompt of the State it was adopted at.

    The Subject rides along because there is no Announcement to carry it: it
    was named when the Entry was made, and the State adopted at may name it
    (ADR 0009).
    """

    state: str
    subject: str | None = None


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

    finished says the Run is already over — because it reached a Terminal
    State, or because the operator removed its Entry and cancelled it (ADR
    0036). Which of the two is not the core's business: both mean the same
    thing here, that nothing further is to be decided. It is a fact about the
    Run rather than about an Announcement, and the only one: nothing re-arms
    it, because nothing that arrives afterwards is Naiad's business.

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

    opening is the Prompt the Run is owed before it has announced anything, set
    for an Adoption between the moment it joins its session and that Prompt
    going out, and absent everywhere else. It is a fact about the Run rather
    than about an Announcement — there is no Announcement yet — and what
    re-arms it is the delivery itself.

    cleared and clear_attempts are the Clear handshake as signals (ADR 0019).
    cleared says this Announcement's /clear has been confirmed by the
    SessionStart hook; clear_attempts is how many times it has been typed. They
    are facts about the current Announcement, like nudges, and the next one
    re-arms them, so a State whose Clear was dropped is a fresh handshake from
    the State after it.

    switches is how many of this State's Switches have been typed, one per tick
    ahead of its Prompt (ADR 0038). A count rather than a flag each, because
    what the rule asks is how far along the sequence is; and per Announcement
    like the Clear, so the next Announcement counts from zero again.

    deliveries and submission are the Prompt's own handshake (ADR 0053).
    deliveries is how many times this Announcement's Prompt has been typed;
    submission is what the UserPromptSubmit hook made of the latest of them —
    landed whole, turned away cut short, or None while it has said nothing.
    Per Announcement like the Clear's pair, and re-armed by the next one.

    belief and handed_over are the two facts a Switch is decided over (ADR
    0039). belief is what Naiad last typed into the Session, by setting, and is
    what a State's own settings are compared against — so a State asking for
    what is already there spends no Tick on it. handed_over says a human has
    been given the keyboard since that was typed.

    A belief and not a reading: Claude Code fires no hook on a Switch, and
    reading the session back is what ADR 0002 forbids, so what Naiad put there
    is the only evidence there is. handed_over is when that evidence is worth
    nothing — past a Notify a human may have typed a `/model` of their own, and
    Naiad cannot know — which is why it is carried beside the belief rather
    than folded into it: emptying the belief where it is read would put the
    rule in the reader (ADR 0004).

    Both are facts about the Run rather than the current Announcement, and
    nothing re-arms them: what the Session holds does not change because the
    agent spoke again.
    """

    announcement: Announcement | None
    handled_seq: int | None
    stopped: bool
    opening: Opening | None = None
    stopped_since_action: bool = False
    notified: bool = False
    nudges: int = 0
    idle_for: float = 0.0
    consultation: Consultation = None
    finished: bool = False
    cleared: bool = False
    clear_attempts: int = 0
    switches: int = 0
    deliveries: int = 0
    submission: Submission = None
    belief: Mapping[str, str] = field(default_factory=dict)
    handed_over: bool = False
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


# What the UserPromptSubmit hook made of the latest typed Prompt, or None while
# it has said nothing (ADR 0053).
Submission = Literal["landed", "rejected"] | None


# The settings a Switch can carry, by the name the session's command takes.
Setting = Literal["model", "effort"]


@dataclass(frozen=True)
class Switch:
    """Type one of this State's settings into the session, ahead of its Prompt
    and one to a tick (ADR 0038).

    setting is what the session calls it and value is the State's effective one.
    The pair is carried rather than two Actions, because the two settings differ
    in nothing a rule cares about: they are one judgment about the phase's work
    (ADR 0026), and the session merely takes them as two commands.

    The setting is spelled as a closed set while the value stays an opaque
    string, and the asymmetry is the point: what the session calls its commands
    is Naiad's own vocabulary, where what names a model is the session's to
    judge and any list Naiad kept would rot (ADR 0026).

    A first-class Action for the reason Clear is one: what has been typed and
    what is left is the decision's business, so the loop keeps no rule of its
    own (ADR 0004). Unlike a Clear it is never confirmed and never re-typed
    within one Announcement — it stays the best-effort switch ADR 0026 chose,
    with the Ticks between doing the work a confirmation would have done.
    """

    state: str
    setting: Setting
    value: str


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
    discarded the context that chose it (ADR 0009).

    The State's Model and Effort are not here. Each is typed on its own tick
    ahead of this one, as a Switch, because the session discards what arrives
    while it is handling a slash command (ADR 0038). Reaching this Action says
    both were typed, and no more than that: whether either took is what ADR 0026
    declines to find out.

    Typing it is not delivering it. The Session can take the typing with
    keystrokes missing, so the Prompt is confirmed by the UserPromptSubmit hook
    and a Confirm settles the Announcement once it has (ADR 0053). attempt is
    carried like a Clear's, so a retry reads apart from the first try."""

    state: str
    prompt: str
    next_states: tuple[str, ...]
    subject: str | None = None
    attempt: int = 1


@dataclass(frozen=True)
class Confirm:
    """The State's Prompt reached the Session whole, as the UserPromptSubmit
    hook reported: the Announcement is handled, and the agent is working on
    what it was given (ADR 0053).

    Sends nothing. It is an Action rather than a bookkeeping step inside the
    loop because it is the terminal one of the delivery — the one that marks
    the Announcement handled — and which Action is terminal is the decision's
    to say (ADR 0004). attempt is which typing it was that landed."""

    state: str
    attempt: int


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

    question is set when what needs a human is a Question — one the Answerer
    escalated, or one the Workflow gave the human (ADR 0046, 0050) — so that
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

Action = Clear | Confirm | Consult | Deliver | Finish | Notify | Nudge | Respond | Switch | Nothing


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

    ended = terminal_state(workflow, signals.announcement)
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
        asked_from = workflow.state(announcement.state)
        if asked_from is not None and asked_from.questions == "human":
            # The Workflow gave this State's Questions to the human, so the
            # Answerer is never consulted: the Run parks exactly as it does on
            # an Escalation, and the human answers in the session (ADR 0046).
            # The Question rides along for the Answer log, which records what
            # became of it; the reason carries its text because no Answerer
            # has phrased one and the notification is all the human sees
            # before they sit down. It says who put the Question with them:
            # the State, or a file that declared no Answerer (ADR 0050).
            whose = (
                f"state '{asked_from.name}' reserves its Questions for you"
                if asked_from.questions_explicit
                else "no Answerer is declared"
            )
            return _notify(signals, f"{whose}: {question.text}", question=question)
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

    if signals.announcement is None and signals.opening is not None and signals.stopped:
        # An Adoption. The Run has joined a session and has said nothing in
        # it, so what it is owed is the Prompt of the State it was adopted at
        # rather than an answer to an Announcement.
        #
        # Waited for a turn to end for the reason every delivery is: the
        # adopted session is mid-conversation, and typing into one still
        # working types over the work. Falling through when none has ended is
        # deliberate, as it is for an answer in hand: it leaves the hang rule
        # below reachable, so a session that died before it could end a turn is
        # not waited on forever.
        return _owed(
            workflow,
            signals,
            state_name=signals.opening.state,
            subject=signals.opening.subject,
            # Said out loud rather than gone quiet on, because a Run owed a
            # Prompt that will never come waits for good. The checks were made
            # when the Entry was queued and again when the Run was attached, so
            # reaching this means the Workflow was edited after that.
            unknown=(
                f"this run was adopted at '{signals.opening.state}', "
                f"which is not a State of this workflow"
            ),
            skip_gates=skip_gates,
        )

    if announcement is not None and signals.stopped:
        return _owed(
            workflow,
            signals,
            state_name=announcement.state,
            subject=announcement.subject,
            # The announce command rejects a State this Workflow does not
            # declare, so reaching this is the agent having found a way around
            # it; nobody but a human can say what was meant. It is not a
            # Deviation — a Deviation is a legal target reached out of order —
            # but the Run log holds the Announcement and this notification's
            # reason beside it, which is what the operator reads to find out
            # what the agent thought it was doing.
            unknown=(
                f"the agent announced '{announcement.state}', "
                f"which is not a State of this workflow"
            ),
            skip_gates=skip_gates,
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


def _owed(
    workflow: Workflow,
    signals: Signals,
    *,
    state_name: str,
    subject: str | None,
    unknown: str,
    skip_gates: bool,
) -> Action:
    """What a Run standing at one State is owed: its Prompt, the Clear that has
    to come first, or why there is nothing to send at all.

    One copy of those rules, reached from both entrances to delivery — the
    State the agent announced, and the State an Adoption was adopted at
    (ADR 0028) — so that the two cannot come to disagree about what is
    deliverable, the discipline naiad.cli.refusals keeps for what is startable.

    A State the Workflow does not declare leaves nothing to deliver, and a Gate
    State is the human's to answer: both say so rather than going quiet, since
    a Run owed a Prompt it never gets waits for good. `unknown` is what the two
    entrances differ in and the only thing they do: how the Run came to stand
    at a State that is not there is what the human needs told.

    The Clear is honored at either entrance, and that is where an Adoption
    diverges from kickoff. Kickoff ignores its first State's flag because the
    session it is about to open holds nothing to discard; the session an
    Adoption joins holds everything, and a Workflow declaring a clean start is
    not Naiad's to overrule (ADR 0028). The discard is confirmed rather than
    assumed, retries and all (ADR 0019).
    """
    state = workflow.state(state_name)
    if state is None:
        return _notify(signals, unknown)
    if state.prompt is None:
        # A Gate State: there is nothing to deliver and the human types into
        # the session directly. That is why the session must stay alive, and
        # why there is no approve command.
        return _notify(signals, f"state '{state.name}' is a Gate State and is waiting for you")

    if state.clear and not signals.cleared:
        # The context must be discarded before the Prompt, and the discard
        # confirmed rather than assumed. Until then delivery waits, exactly as
        # it waits on a turn ending (ADR 0019).
        return _clear(signals, state.name)

    pending = _switches(state, signals.belief, handed_over=signals.handed_over)
    if signals.switches < len(pending):
        # One Switch a tick, the Prompt behind them. The session drops whatever
        # arrives while it is handling a slash command, so typing the two
        # settings and the Prompt in one go loses one of the three (ADR 0038).
        # The Ticks between are the whole of the fix: nothing is confirmed, and
        # nothing needs to be.
        return pending[signals.switches]

    return _deliver(
        signals,
        Deliver(
            state=state.name,
            prompt=state.prompt,
            next_states=resolve_next_states(workflow, state.name, skip_gates=skip_gates),
            subject=subject,
        ),
    )


def terminal_state(workflow: Workflow, announcement: Announcement | None) -> State | None:
    """The Terminal State this Announcement names, if it names one.

    Terminal is read from the Workflow, so Naiad recognises no State name of
    its own and stays ignorant of what any particular Workflow means.

    An Announcement carrying a Question is never an ending, however Terminal
    the State it was asked from: the agent is standing in that State rather
    than arriving at it, and it is waiting on an answer.

    Public because the resolution seam asks it too: a Run that has ended
    releases its Session (ADR 0035), and whether it has ended is this same
    question. A second copy would drift on exactly the Question clause above.
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


def _deliver(signals: Signals, delivery: Deliver) -> Action:
    """Get this State's Prompt into the Session whole, catching one the Session
    took cut short rather than letting the agent work from part of it
    (ADR 0053).

    The Clear's handshake with one difference, and the difference is the
    point. A Prompt the hook turned away is typed again at once, because the
    hook blocking it is proof the Session is idle and took none of it. A
    Prompt the hook said nothing about is not typed again: silence is also what
    a hook that is not installed produces, over a Prompt the agent is working
    on, and a retype would queue a second copy behind it. So that one tells the
    human, as a Clear past its bound does.
    """
    if signals.submission == "landed":
        return Confirm(state=delivery.state, attempt=signals.deliveries)
    if signals.deliveries == 0:
        return delivery
    if signals.submission == "rejected":
        if signals.deliveries < DELIVERY_RETRY_LIMIT:
            return replace(delivery, attempt=signals.deliveries + 1)
        return _notify(
            signals,
            f"the prompt for '{delivery.state}' arrived cut short "
            f"{DELIVERY_RETRY_LIMIT} times and was turned away each time",
        )
    if signals.idle_for < DELIVERY_CONFIRM_SECONDS:
        return NOTHING
    return _notify(
        signals,
        f"the prompt for '{delivery.state}' was typed but never reported as submitted; "
        "it may not have reached the session, or naiad's UserPromptSubmit hook "
        "is not installed (run `naiad install`)",
    )


def _switches(
    state: State, belief: Mapping[str, str], *, handed_over: bool
) -> tuple[Switch, ...]:
    """The Switches this State owes its session, in the order they are typed.

    Built from the settings the State actually has rather than from a fixed
    pair, so a Workflow naming one key does not spend a tick on the other, and
    one naming neither goes straight to its Prompt as it always did.

    Narrowed again to the ones the Session is not believed to hold already
    (ADR 0039). The settings are sticky, so a State asking for what is there
    buys nothing by asking twice and pays two Ticks for it. Compared per
    setting rather than over the pair, so a State moving one of the two spends
    one Tick and not both.

    A hand-off to a human discards the belief entirely, and every setting the
    State declares is typed again. That is what the narrowing gives up and this
    gives back: ADR 0026 bought the healing of a dropped Switch with an
    every-delivery retype, and past a Notify is the one moment Naiad knows its
    belief may be wrong — because a human has had the keyboard, and may have
    set the Model themselves.

    The order is the declaration's — Model, then Effort — and carries no
    meaning: neither setting depends on the other, and the sequence exists to
    put a tick between them rather than to sequence the settings themselves.
    """
    named: tuple[tuple[Setting, str | None], ...] = (
        ("model", state.model),
        ("effort", state.effort),
    )
    return tuple(
        Switch(state=state.name, setting=setting, value=value)
        for setting, value in named
        if value is not None
        if handed_over or belief.get(setting) != value
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
    "DELIVERY_CONFIRM_SECONDS",
    "DELIVERY_RETRY_LIMIT",
    "HANG_SECONDS",
    "NOTHING",
    "NUDGE_LIMIT",
    "SILENCE_SECONDS",
    "WAIT_BUDGET_SECONDS",
    "WAIT_DEFAULT_SECONDS",
    "Action",
    "Clear",
    "Confirm",
    "Consult",
    "Deliver",
    "Finish",
    "Nothing",
    "Notify",
    "Nudge",
    "Opening",
    "Respond",
    "Setting",
    "Signals",
    "Submission",
    "Switch",
    "decide",
    "terminal_state",
]
