"""What the agent said, as data.

Announcements are distinct and ordered even when they name the same State
twice: seq is what makes the fifth implement iteration a fifth Announcement
rather than a no-op change of value. Naiad acts once per seq, never twice.

A Question is announced the same way and takes its number from the same
sequence, so a Question and a State are ordered against each other rather than
each having its own idea of what came first. That ordering is what the Answer
log is read by. An Announcement carrying a Question still names the State the
agent is standing in, because that is where it will carry on once answered.

A Subject is what the Announcement is about — the item a repeating State is
repeating over. It belongs here rather than to the Prompt because the Prompt is
only one of its readers: a Gate State substitutes nothing and its Subject is
read by the human out of the Run log (ADR 0009).
"""

from __future__ import annotations

from dataclasses import dataclass

from naiad.domain.question import Question


@dataclass(frozen=True)
class Announcement:
    seq: int
    state: str
    question: Question | None = None
    subject: str | None = None
