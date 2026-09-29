"""The tick: gather the signals, ask the decision function, carry out the answer.

There is deliberately no rule here. Whether to deliver, whether to Clear first,
which State comes next, whether the agent has been quiet long enough to be
nudged and whether the operator has already been told were all decided in
naiad.domain.decide; what is left is reading a few files, one call,
and a dispatch. If a condition ever needs adding to this module, it belongs in
the decision function instead.
"""

from __future__ import annotations

import time
import uuid
from typing import Protocol

from naiad.domain.answerer import Answered, ConsultationSpec, Escalated, render_consultation
from naiad.domain.decide import (
    Action,
    Clear,
    Confirm,
    Consult,
    Deliver,
    Finish,
    Notify,
    Nudge,
    Opening,
    Report,
    Respond,
    Signals,
    Switch,
    decide,
)
from naiad.domain.announcement import Announcement
from naiad.domain.notification import Notification, render_answered
from naiad.domain.prompt import render_prompt
from naiad.domain.protocol import DEFAULT_NAIAD, render_answer, render_nudge
from naiad.domain.question import Question
from naiad.domain.transitions import UnknownState, deviation, start_state
from naiad.domain.workflow import Workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.answers import AnswerLog
from naiad.runtime.log import RunLog
from naiad.runtime.records import (
    ClearAttempts,
    Clears,
    Consultations,
    Deliveries,
    Handled,
    Holds,
    Notices,
    Reports,
    Submissions,
    Switches,
    Turns,
    Waits,
    idle_seconds,
)
from naiad.runtime.run import Run


class UndrivableRun(Exception):
    """A Run with no session to deliver into."""


class Session(Protocol):
    def send(self, pane: str, text: str) -> None: ...
    def clear(self, pane: str) -> None: ...


class Notifier(Protocol):
    """Where a telling goes, and what kind of telling it is.

    The kind is service-neutral (naiad.domain.notification): the loop says
    whether a human is needed, the work is done or a State was entered, and an
    adapter maps that onto whatever scale of urgency its service understands.
    Deciding here which push priority a Gate State deserves would put a
    service's vocabulary in the tick.
    """

    def notify(self, title: str, message: str, kind: Notification) -> None: ...


class Answerer(Protocol):
    def consult(self, spec: ConsultationSpec) -> Answered | Escalated: ...


def tick(
    *,
    run: Run,
    workflow: Workflow,
    session: Session,
    notifier: Notifier,
    answerer: Answerer,
    now: float | None = None,
    naiad: str = DEFAULT_NAIAD,
    entry_id: str | None = None,
) -> Action:
    """now is a parameter so the rules that depend on elapsed time can be
    driven from data rather than from a test that waits. Every other caller
    means the current moment, so that is what it defaults to.

    entry_id is the Entry this Run became, which is what `naiad queue answers`
    is best pointed at. The Run knows no Entry, so whoever drives it says; a
    Run with none is pointed at by its own id."""
    announcement = Announcements(run.root).latest()
    log = RunLog(run.root)
    turns = Turns(run.root)
    handled = Handled(run.root)
    notices = Notices(run.root)
    reports = Reports(run.root)
    consultations = Consultations(run.root)
    clears = Clears(run.root)
    clearing = ClearAttempts(run.root)
    switching = Switches(run.root)
    deliveries = Deliveries(run.root)
    submissions = Submissions(run.root)
    answers = AnswerLog(run.root)
    waits = Waits(run.root)
    holds = Holds(run.root)
    moment = now if now is not None else time.time()
    reference = entry_id or run.id
    # Read out of the log rather than out of a record of its own, for the reason
    # `finished` is: every Switch and every Notify is already written there, and
    # one fact deserves one home. Both come back from one pass, and
    # what they mean for a State's Switches is the decision's to say.
    belief, handed_over = log.belief(announcement)
    # The Wait and Hold counts key the Notices record: a fresh Wait re-arms
    # the nudge allowance the way a fresh Announcement does, and a
    # fresh Hold re-arms the notification an earlier alarm would otherwise
    # swallow.
    wait_count = waits.count(announcement)
    hold_count = holds.count(announcement)
    notified, nudges = notices.of(announcement, wait_count=wait_count, hold_count=hold_count)
    typed = deliveries.attempts(announcement)

    # Written before the decision rather than after it, because where the agent
    # stood before this Announcement is read back out of the log — and because
    # an Announcement Naiad received is worth recording whether or not anything
    # was done about it this tick.
    log.record_announcement(
        announcement, deviated_from=_deviation(run, workflow, log, announcement)
    )

    action = decide(
        workflow,
        Signals(
            announcement=announcement,
            opening=_opening(run, workflow, log),
            handled_seq=handled.seq(),
            stopped=turns.ended_since(announcement),
            stopped_since_action=turns.ended_since_action(handled),
            notified=notified,
            reported=reports.of(announcement),
            nudges=nudges,
            idle_for=idle_seconds(run.root, now=moment),
            consultation=consultations.of(announcement),
            finished=log.ended(),
            cleared=clearing.confirmed(announcement, clears),
            clear_attempts=clearing.attempts(announcement),
            switches=switching.typed(announcement),
            deliveries=typed,
            submission=submissions.of(announcement, attempt=typed),
            belief=belief,
            handed_over=handed_over,
            waiting=waits.waiting(announcement, now=moment),
            wait_reason=waits.reason(announcement),
            holding=holds.holding(announcement),
            hold_reason=holds.reason(announcement),
            answered=answers.answered(),
        ),
        skip_gates=run.skip_gates,
    )

    if isinstance(action, Clear):
        # Type /clear and record the attempt against the current Clear count,
        # so a landing after this can be told from one before it. The Prompt
        # does not follow yet: a later tick delivers it, once the SessionStart
        # hook has confirmed the discard.
        #
        # An adopted Run's Clear answers no Announcement, as its first delivery
        # answers none: the attempt is kept against no seq, which is the key the
        # next tick reads it back under while nothing has been announced.
        session.clear(_pane(run))
        clearing.record_attempt(announcement, landed=clears.count())
    elif isinstance(action, Switch):
        # One of the State's settings, and only one: the Prompt and the other
        # Switch follow on later ticks, because the session discards whatever
        # arrives while it is handling a slash command. Nothing is
        # waited for here — the tick interval is the pause, which is what keeps
        # this loop free of a sleep that would stall every other Lane.
        #
        # Recorded so the next tick knows how far the sequence got. Kept against
        # no seq for an adopted Run's first delivery, exactly as its Clear is.
        session.send(_pane(run), f"/{action.setting} {action.value}")
        switching.record_typed(announcement)
    elif isinstance(action, Deliver):
        prompt = render_prompt(
            action.prompt,
            task=run.task,
            next_states=action.next_states,
            subject=action.subject,
            # Read off the Run rather than off the Action: the branch and what
            # it stands on are facts of the Run like the task, so they reach
            # every delivery rather than being decided per Announcement as the
            # Subject is.
            branch=run.working_branch,
            predecessor=run.predecessor,
        )
        # Recorded before it is typed, because the UserPromptSubmit hook fires
        # while it is being typed and judges the submission against this. The
        # Announcement is not handled yet: a Confirm does that once the hook has
        # seen the Prompt land whole.
        deliveries.record_attempt(announcement, prompt=prompt, turns=turns.count(), at=moment)
        session.send(_pane(run), prompt)
    elif isinstance(action, Confirm):
        # An adopted Run's first delivery answers no Announcement, so there is
        # no seq to record against it — only the turn baseline, which is what
        # keeps the agent working on what it was just given from reading as a
        # silent one. The baseline is the one taken when the Prompt
        # that landed was typed, so a Turn the agent ended since then counts.
        handled.record(
            announcement.seq if announcement is not None else None,
            turns=deliveries.turns(announcement),
        )
    elif isinstance(action, Consult):
        consultations.record(
            announcement, answerer.consult(_consultation(run, workflow, action.question))
        )
    elif isinstance(action, Respond) and announcement is not None:
        session.send(_pane(run), render_answer(action.answer))
        answers.record(
            question=action.question, answer=action.answer, state=announcement.state
        )
        handled.record(announcement.seq, turns=turns.count())
    elif isinstance(action, Nudge):
        session.send(
            _pane(run),
            render_nudge(attempt=action.attempt, naiad=naiad, expired_wait=action.expired_wait),
        )
        notices.record_nudge(announcement, wait_count=wait_count, hold_count=hold_count)
    elif isinstance(action, Finish):
        # The session is deliberately not touched: nothing is sent into it and
        # it is not killed, because it holds the evidence of what the Run did.
        # Nothing is recorded here either — the log entry written below is what
        # makes the ending final, so the fact has one home rather than two.
        notifier.notify(
            title=f"naiad: {run.id}",
            message=_with_answered(f"finished at {action.state}", action.answered, reference),
            kind=Notification.FINISH,
        )
    elif isinstance(action, Report):
        # Nothing is sent into the session and nothing is parked: the Report
        # goes to the operator and is recorded apart from the Notices, so no
        # reader of a hand-off can see it. The Task is left out
        # because the run id already names the Run and a Task can swamp a
        # banner.
        message = f"entered {action.state}"
        if action.subject is not None:
            message += f": {action.subject}"
        notifier.notify(title=f"naiad: {run.id}", message=message, kind=Notification.REPORT)
        reports.record(announcement)
    elif isinstance(action, Notify):
        notifier.notify(
            title=f"naiad: {run.id}",
            message=_with_answered(action.reason, action.answered, reference),
            kind=Notification.NOTIFY,
        )
        notices.record_notified(announcement, wait_count=wait_count, hold_count=hold_count)
        if action.question is not None and announcement is not None:
            # A Question the human is answering: one the Answerer escalated,
            # or one the Workflow gave the human. Recorded here rather
            # than at the consultation so that the log holds what became of
            # it, not merely what was said about it — and once, because a
            # second notification for the same Announcement never arrives.
            answers.record(
                question=action.question,
                answer=action.reason,
                state=announcement.state,
                escalated=True,
            )

    log.record(action, seq=announcement.seq if announcement is not None else None)
    return action


def _with_answered(message: str, answered: int, reference: str) -> str:
    """The message with the Answerer's count as a line of its own, and only
    when it answered something: a Run it never answered has nothing to review."""
    if answered == 0:
        return message
    return f"{message}\n{render_answered(answered, reference=reference)}"


def _opening(run: Run, workflow: Workflow, log: RunLog) -> Opening | None:
    """The Prompt this Run is owed and has not been given.

    Only an adopted Run is ever owed one — a spawned Run was handed its first
    Prompt as its session launched — and only until it goes out, which the log
    is what says. Both facts are read rather than kept: which of the two ways a
    Run met its session is written on the Run, and what has been delivered into
    it is written in its log.
    """
    if not run.adopted or log.opened():
        return None
    try:
        name = start_state(workflow, run.start_state).name
    except UnknownState:
        # The Workflow no longer declares the State this Run was adopted at.
        # Carried through under the name it was queued with rather than
        # swallowed here, so that the decision is the one that says so — a Run
        # owed a Prompt that will never come has to be said out loud.
        name = str(run.start_state)
    return Opening(state=name, subject=run.start_subject)


def _deviation(
    run: Run, workflow: Workflow, log: RunLog, announcement: Announcement | None
) -> tuple[str, ...]:
    """Whether this Announcement left the expected path, asked of the domain.
    Where the agent stood before it is read back from the log, which is the only
    place the Announcements before the latest are kept."""
    if announcement is None:
        return ()
    return deviation(
        workflow,
        announced=announcement.state,
        previous_state=log.previous_state(announcement),
        started_at=run.start_state,
        skip_gates=run.skip_gates,
    )


def _consultation(run: Run, workflow: Workflow, question: Question) -> ConsultationSpec:
    """One Answerer per Run, started on the first Question and resumed on every
    one after it, so that its later answers cannot contradict its earlier ones."""
    session_id = run.answerer_session_id
    resume = session_id is not None
    if session_id is None:
        session_id = str(uuid.uuid4())
        run.attach_answerer(session_id)
    return ConsultationSpec(
        cwd=run.target_repo,
        claude_session_id=session_id,
        text=render_consultation(question, task=run.task),
        resume=resume,
        model=workflow.answerer_model,
        effort=workflow.answerer_effort,
        fallback=workflow.answerer_fallback,
    )


def _pane(run: Run) -> str:
    pane = run.tmux_pane
    if not pane:
        # tmux reads an empty -t target as the attached pane, so coercing a
        # missing one would deliver into whatever session the operator is
        # looking at — and Clear it first.
        raise UndrivableRun(f"run {run.id} has no pane recorded to deliver into")
    return pane


__all__ = ["Answerer", "Notifier", "Session", "tick"]
