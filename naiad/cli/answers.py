"""Reading a Run's Answer log as an operator does, without opening JSON.

One numbered block per Question, in the order they were asked, because the log
is read as one narrative of an unattended Run's judgment. No colour and no
machine form: `answers.json` is the machine form.
"""

from __future__ import annotations

import textwrap
from collections.abc import Sequence

from naiad.runtime.answers import Answer

INDENT = "   "


def render_answers(run_id: str, entries: Sequence[Answer], *, width: int) -> str:
    """What `naiad queue answers` prints for one Run, wrapped to width."""
    if not entries:
        return f"no questions were asked in {run_id}\n"
    blocks = [_block(number, entry, width) for number, entry in enumerate(entries, start=1)]
    return "\n\n".join(blocks) + "\n"


def _block(number: int, entry: Answer, width: int) -> str:
    heading = f"{number}  {entry.state}" if entry.state else str(number)
    question = textwrap.fill(
        entry.question, width=width, initial_indent=INDENT, subsequent_indent=INDENT
    )
    options = [f"{INDENT}options:", *(f"{INDENT}  - {option}" for option in entry.options)]
    return "\n".join([heading, question, *options, f"{INDENT}{_outcome(entry)}"])


def _outcome(entry: Answer) -> str:
    """Whose outcome it was, said plainly. An escalation and a Question the
    Workflow gave the human are both the operator's: Naiad knows who put the
    Question with them, and never what they typed into the Session."""
    if entry.abandoned:
        return f"→ abandoned: {entry.answer}"
    if entry.escalated:
        return f"→ yours: {entry.answer}"
    return f"→ answerer: {entry.answer}"


__all__ = ["render_answers"]
