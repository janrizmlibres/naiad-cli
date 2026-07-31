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
import uuid
from typing import Protocol

from naiad.domain.answerer import Answered, ConsultationSpec, Escalated, render_consultation
from naiad.domain.decide import (
    Action,
    Clear,
    Consult,
    Deliver,
    Finish,
    Notify,
    Nudge,
    Respond,
    Signals,
    decide,
)
from naiad.domain.announcement import Announcement
from naiad.domain.prompt import render_prompt
from naiad.domain.protocol import DEFAULT_NAIAD, render_answer, render_nudge
from naiad.domain.question import Question
from naiad.domain.transitions import deviation
from naiad.domain.workflow import Workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.answers import AnswerLog
from naiad.runtime.log import RunLog
from naiad.runtime.records import (
    ClearAttempts,
    Clears,
    Consultations,
    Handled,
    Notices,
    Turns,
    idle_seconds,
)
from naiad.runtime.run import Run


class UndrivableRun(Exception):
    """A Run with no session to deliver into."""


class Session(Protocol):
    def send(self, pane: str, text: str) -> None: ...
    def clear(self, pane: str) -> None: ...


class Notifier(Protocol):
    def notify(self, title: str, message: str) -> None: ...


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
) -> Action:
    """now is a parameter so the rules that depend on elapsed time can be
    driven from data rather than from a test that waits. Every other caller
    means the current moment, so that is what it defaults to."""
    announcement = Announcements(run.root).latest()
    log = RunLog(run.root)
    turns = Turns(run.root)
    handled = Handled(run.root)
    notices = Notices(run.root)
    consultations = Consultations(run.root)
    clears = Clears(run.root)
    clearing = ClearAttempts(run.root)
    answers = AnswerLog(run.root)
    notified, nudges = notices.of(announcement)

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
            handled_seq=handled.seq(),
            stopped=turns.ended_since(announcement),
            stopped_since_action=turns.ended_since_action(handled),
            notified=notified,
            nudges=nudges,
            idle_for=idle_seconds(run.root, now=now if now is not None else time.time()),
            consultation=consultations.of(announcement),
            finished=log.finished(),
            cleared=clearing.confirmed(announcement, clears),
            clear_attempts=clearing.attempts(announcement),
        ),
        skip_gates=run.skip_gates,
    )

    if isinstance(action, Clear) and announcement is not None:
        # Type /clear and record the attempt against the current Clear count,
        # so a landing after this can be told from one before it. The Prompt
        # does not follow yet: a later tick delivers it, once the SessionStart
        # hook has confirmed the discard (ADR 0019).
        session.clear(_pane(run))
        clearing.record_attempt(announcement, landed=clears.count())
    elif isinstance(action, Deliver) and announcement is not None:
        session.send(
            _pane(run),
            render_prompt(
                action.prompt,
                task=run.task,
                next_states=action.next_states,
                subject=action.subject,
                # Read off the Run rather than off the Action: the branch and
                # what it stands on are facts of the Run like the task, so they
                # reach every delivery rather than being decided per
                # Announcement as the Subject is.
                branch=run.working_branch,
                predecessor=run.predecessor,
            ),
        )
        handled.record(announcement.seq, turns=turns.count())
    elif isinstance(action, Consult):
        consultations.record(announcement, answerer.consult(_consultation(run, action.question)))
    elif isinstance(action, Respond) and announcement is not None:
        session.send(_pane(run), render_answer(action.answer))
        answers.record(question=action.question, answer=action.answer)
        handled.record(announcement.seq, turns=turns.count())
    elif isinstance(action, Nudge):
        session.send(_pane(run), render_nudge(attempt=action.attempt, naiad=naiad))
        notices.record_nudge(announcement)
    elif isinstance(action, Finish):
        # The session is deliberately not touched: nothing is sent into it and
        # it is not killed, because it holds the evidence of what the Run did.
        # Nothing is recorded here either — the log entry written below is what
        # makes the ending final, so the fact has one home rather than two.
        notifier.notify(title=f"naiad: {run.id}", message=f"finished at {action.state}")
    elif isinstance(action, Notify):
        notifier.notify(title=f"naiad: {run.id}", message=action.reason)
        notices.record_notified(announcement)
        if action.question is not None:
            # An Escalated Question. Recorded here rather than at the
            # consultation so that the log holds what became of it, not merely
            # what was said about it — and once, because a second notification
            # for the same Announcement never arrives.
            answers.record(question=action.question, answer=action.reason, escalated=True)

    log.record(action, seq=announcement.seq if announcement is not None else None)
    return action


def _deviation(
    run: Run, workflow: Workflow, log: RunLog, announcement: Announcement | None
) -> tuple[str, ...]:
    """Whether this Announcement left the expected path, asked of the domain
    (ADR 0004). Where the agent stood before it is read back from the log,
    which is the only place the Announcements before the latest are kept."""
    if announcement is None:
        return ()
    return deviation(
        workflow,
        announced=announcement.state,
        previous_state=log.previous_state(announcement),
        started_at=run.start_state,
        skip_gates=run.skip_gates,
    )


def _consultation(run: Run, question: Question) -> ConsultationSpec:
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
