"""The State file — the agent's Announcements.

The agent is its only writer and Naiad only ever reads it, so
progress is always a record of the agent's own judgment rather than a
blackboard the two parties race over.

Only the latest Announcement is kept. What makes a repeat distinct is its
sequence number, not a history: the agent implementing its fifth ticket
announces the same State a fifth time, gets a fifth seq, and Naiad acts a fifth
time. Naiad's own record of what it has acted on lives elsewhere, so that this
file stays single-writer.

An agent that announces twice before Naiad next looks therefore has only its
second Announcement acted on. That is deliberate: the first is stale intent the
agent has already moved on from, and delivering its Prompt would send the
session backwards. Keeping a queue instead would trade a skipped Announcement
for a wrong one.
"""

from __future__ import annotations

import json
from pathlib import Path

from naiad.domain.announcement import Announcement
from naiad.domain.question import Question
from naiad.runtime.atomic import write_atomically

STATE_FILENAME = "state.json"


class Announcements:
    """A Run's State file. Constructed with the Run's directory rather than
    reading a module-level path, so a second Run is a second object."""

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / STATE_FILENAME

    def latest(self) -> Announcement | None:
        try:
            document = json.loads(self.path.read_text())
        except FileNotFoundError:
            return None
        question = document.get("question")
        return Announcement(
            seq=document["seq"],
            state=document["state"],
            question=(
                Question(text=question["text"], options=tuple(question["options"]))
                if question
                else None
            ),
            subject=document.get("subject"),
        )

    def announce(self, state: str, *, subject: str | None = None) -> Announcement:
        """A State, carrying no Question.

        Announcing a State is also how a Question stops being current: the
        agent has been answered and moved on, and a Question left clinging to
        the next Announcement would be consulted again after the fact.

        A Subject is scoped to its own Announcement for the same reason, and
        gets it for free: only the latest Announcement is kept, so the next one
        replaces the document rather than amending it.
        """
        return self._write(state=state, question=None, subject=subject)

    def ask(self, question: Question, *, state: str) -> Announcement:
        """A Question, taking its number from the same sequence as States so
        that the two are ordered against each other.

        The State is carried rather than replaced because it is where the agent
        is standing and where it carries on once the answer arrives.
        """
        return self._write(state=state, question=question)

    def _write(
        self, *, state: str, question: Question | None, subject: str | None = None
    ) -> Announcement:
        previous = self.latest()
        announcement = Announcement(
            seq=(previous.seq + 1) if previous else 1,
            state=state,
            question=question,
            subject=subject,
        )
        document: dict[str, object] = {"seq": announcement.seq, "state": announcement.state}
        if question is not None:
            document["question"] = {"text": question.text, "options": list(question.options)}
        if subject is not None:
            document["subject"] = subject
        write_atomically(self.path, json.dumps(document, indent=2) + "\n")
        return announcement


__all__ = ["Announcements", "STATE_FILENAME"]
