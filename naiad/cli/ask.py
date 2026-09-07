"""The agent's other side of the Protocol: asking a Question.

A command rather than a conversational question, because no human is watching:
a question put to one blocks forever and the Run dies having done nothing. And
a command rather than a file the agent writes, for the same reason announcing
is (ADR 0001).

The Question carries its own text and options because Naiad reads no Claude
Code internals (ADR 0002) — there is no conversation for it to be lifted out
of, so a Question Naiad was not told about does not exist.

One Question at a time (ADR 0044). Only the latest Announcement is kept, so a
second ask would replace the first unanswered — and the agent, promised an
answer for each, would wait on ones that can never come. The refusal carries
the protocol: hold the rest, re-ask as each answer arrives.
"""

from __future__ import annotations

from collections.abc import Sequence

from naiad.domain.announcement import Announcement
from naiad.domain.answerer import Escalated
from naiad.domain.question import Question
from naiad.domain.transitions import start_state
from naiad.domain.workflow import load_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.records import Consultations, Handled
from naiad.runtime.run import Run


class AskError(Exception):
    """A Question the agent must see and correct."""


def unanswered_question(run: Run) -> Announcement | None:
    """The Question still owed an answer, if one stands.

    A Question is resolved by the Respond that sent its answer — which recorded
    its seq as handled — or by the Escalation that handed it to a human. Until
    one of the two, it is the current Announcement and must not be replaced:
    an Announcement written over before Naiad looks is acted on not at all.
    """
    latest = Announcements(run.root).latest()
    if latest is None or latest.question is None:
        return None
    handled = Handled(run.root).seq()
    if handled is not None and latest.seq <= handled:
        return None
    if isinstance(Consultations(run.root).of(latest), Escalated):
        return None
    return latest


def ask_question(text: str, *, options: Sequence[str], run: Run) -> Announcement:
    if not text.strip():
        raise AskError("a question needs text; pass what you want decided")
    if not options:
        raise AskError(
            "a question needs the options you were weighing, one --option each; "
            "whoever answers must choose between the same alternatives you faced, "
            "and naiad cannot see them unless you say what they were"
        )
    pending = unanswered_question(run)
    if pending is not None:
        raise AskError(
            f"your question ({pending.seq}) is still being answered, and only one "
            "question stands at a time — a second would replace it unanswered. "
            "Hold this question and ask it again when the answer arrives in this "
            "session; ask one question at a time, waiting for each answer before "
            "the next"
        )

    announcements = Announcements(run.root)
    latest = announcements.latest()
    # Where the agent is standing: its latest Announcement, or — before it has
    # made one — the State the Run began at, whose Prompt it was handed at
    # kickoff without ever announcing it.
    if latest is not None:
        standing = latest.state
    else:
        standing = start_state(load_workflow(run.workflow_path), run.start_state).name
    return announcements.ask(Question(text=text, options=tuple(options)), state=standing)


__all__ = ["AskError", "ask_question", "unanswered_question"]
