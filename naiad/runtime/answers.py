"""The Answer log: every Question of a Run, its options, and what came of it.

Written by Naiad rather than by the agent, because Naiad holds both halves. The
agent cannot fail to log an answer it never saw, and asking it to log one would
put the audit trail in the hands of the party being audited.

Append-only and in order, because it is read as one narrative: the operator at
a Gate is judging whether an unattended Run went astray, and a Question is
judgeable only beside the alternatives it was chosen from.

Escalations are recorded here too. They are what became of that Question, and a
log holding only the answered ones would show a Run as tidier than it was.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from naiad.domain.question import Question
from naiad.runtime.atomic import write_atomically

ANSWERS_FILENAME = "answers.json"


@dataclass(frozen=True)
class Answer:
    """One Question and what came of it.

    answer carries the Escalation's reason when escalated is set: the operator
    reads one column for 'what happened', rather than having to look in two
    places to find out that nothing did. An abandonment — the agent announcing
    onward over its own unanswered Question — carries what it walked away to,
    in the same column for the same reason.

    state is the Standing State the Question was asked from, so a Question
    reads beside where the Run stood. None for an entry written before it was
    recorded.
    """

    question: str
    options: tuple[str, ...]
    answer: str
    escalated: bool = False
    abandoned: bool = False
    state: str | None = None


class AnswerLog:
    """A Run's Answer log. Constructed with the Run's directory rather than
    reading a module-level path, so a second Run is a second log (ADR 0004)."""

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / ANSWERS_FILENAME

    def entries(self) -> list[Answer]:
        try:
            document = json.loads(self.path.read_text())
        except FileNotFoundError:
            # A Run that has raised no Question has no log, which is not an
            # absence of information but the information itself.
            return []
        return [
            Answer(
                question=entry["question"],
                options=tuple(entry["options"]),
                answer=entry["answer"],
                escalated=entry.get("escalated", False),
                abandoned=entry.get("abandoned", False),
                state=entry.get("state"),
            )
            for entry in document
        ]

    def answered(self) -> int:
        """How many Questions the Answerer settled. An escalation, a Question
        the Workflow gave the human and an abandonment are not counted: the
        human already saw each of them, and this is what tells them there is
        something they did not."""
        return sum(1 for entry in self.entries() if not entry.escalated and not entry.abandoned)

    def record(
        self,
        *,
        question: Question,
        answer: str,
        state: str | None = None,
        escalated: bool = False,
        abandoned: bool = False,
    ) -> None:
        entries = self.entries()
        entries.append(
            Answer(
                question=question.text,
                options=question.options,
                answer=answer,
                escalated=escalated,
                abandoned=abandoned,
                state=state,
            )
        )
        write_atomically(self.path, json.dumps([_document(e) for e in entries], indent=2) + "\n")


def _document(entry: Answer) -> dict[str, object]:
    return {
        "question": entry.question,
        "options": list(entry.options),
        "answer": entry.answer,
        "escalated": entry.escalated,
        "abandoned": entry.abandoned,
        "state": entry.state,
    }


__all__ = ["ANSWERS_FILENAME", "Answer", "AnswerLog"]
