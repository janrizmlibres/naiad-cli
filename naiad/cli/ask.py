"""The agent's other side of the Protocol: asking a Question.

A command rather than a conversational question, because no human is watching:
a question put to one blocks forever and the Run dies having done nothing. And
a command rather than a file the agent writes, for the same reason announcing
is (ADR 0001).

The Question carries its own text and options because Naiad reads no Claude
Code internals (ADR 0002) — there is no conversation for it to be lifted out
of, so a Question Naiad was not told about does not exist.
"""

from __future__ import annotations

from collections.abc import Sequence

from naiad.domain.announcement import Announcement
from naiad.domain.question import Question
from naiad.domain.transitions import start_state
from naiad.domain.workflow import load_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.run import Run


class AskError(Exception):
    """A Question the agent must see and correct."""


def ask_question(text: str, *, options: Sequence[str], run: Run) -> Announcement:
    if not text.strip():
        raise AskError("a question needs text; pass what you want decided")
    if not options:
        raise AskError(
            "a question needs the options you were weighing, one --option each; "
            "whoever answers must choose between the same alternatives you faced, "
            "and naiad cannot see them unless you say what they were"
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


__all__ = ["AskError", "ask_question"]
