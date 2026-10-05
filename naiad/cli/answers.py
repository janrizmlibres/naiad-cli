"""Reading a Run's Answer log as an operator does, without opening JSON.

One numbered block per Question, in the order they were asked, because the log
is read as one narrative of an unattended Run's judgment. `answers.json` is the
machine form, so this one is laid out for a person, and at a terminal whose
outcome each was — the Answerer's, the operator's, or walked away from — is told
apart by its colour as well as its word. The words are the same off a terminal,
where nothing is coloured.
"""

from __future__ import annotations

import textwrap
from collections.abc import Sequence

from rich.text import Text

from naiad.cli.style import Styled
from naiad.runtime.answers import Answer

INDENT = "   "


def render_answers(run_id: str, entries: Sequence[Answer], *, width: int) -> Styled:
    """What `naiad queue answers` prints for one Run, wrapped to width."""
    if not entries:
        return Styled.assemble(("no questions were asked in ", "secondary"), (run_id, "id"))
    blocks = [_block(number, entry, width) for number, entry in enumerate(entries, start=1)]
    return Styled(Text("\n\n").join(blocks))


def _block(number: int, entry: Answer, width: int) -> Text:
    # Wrapped as plain text and styled after, so that a style never counts
    # towards the width.
    question = textwrap.fill(
        entry.question, width=width, initial_indent=INDENT, subsequent_indent=INDENT
    )
    lines = [
        Text.assemble((str(number), "header"), *_state(entry)),
        Text(question),
        Text.assemble(INDENT, ("options:", "secondary")),
        *(Text.assemble(INDENT, ("  - ", "secondary"), option) for option in entry.options),
        Text.assemble(INDENT, _outcome(entry), " ", entry.answer),
    ]
    return Text("\n").join(lines)


def _state(entry: Answer) -> tuple[str | tuple[str, str], ...]:
    """The State a Question was asked from, beside its number, where it was
    recorded."""
    return ("  ", (entry.state, "state")) if entry.state else ()


def _outcome(entry: Answer) -> tuple[str, str]:
    """Whose outcome it was, said plainly. An escalation and a Question the
    Workflow gave the human are both the operator's: Naiad knows who put the
    Question with them, and never what they typed into the Session."""
    if entry.abandoned:
        return ("→ abandoned:", "answer.abandoned")
    if entry.escalated:
        return ("→ yours:", "answer.yours")
    return ("→ answerer:", "answer.answerer")


__all__ = ["render_answers"]
