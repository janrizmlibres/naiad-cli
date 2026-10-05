"""How Naiad's output looks, and who it is styled for.

Two audiences read what Naiad prints. A person at a terminal reads it at a
glance, and colour tells them which line wants them. An agent's Bash tool, a
hook and a file redirect read the same stream as text, where an escape code is
noise inside the words they match on. So colour is never chosen by the caller:
every Console is made here, and colours only a stream that is a real terminal,
with NO_COLOR unset. FORCE_COLOR colours a stream that is not one, for the
operator who pipes into a pager that understands it. NO_COLOR wins over both,
and drops every style rather than only the colours: nothing here is more than
decoration, and the operator who set it asked for plain text.

Colour is the only part that knows its audience. Layout — columns, glyphs, the
lines drawn between a Parent and its Children — is the same for every reader,
so a change of layout reaches the agents and hooks that read the output too.
Text another program parses or matches against is laid out with that in mind
before it is styled.

Styles are named for what they mean (`status.parked`, `repo`, `refusal`), never
for a colour, so that a line is styled by saying what each piece is and the
palette lives in one place.

Width is measured on the text, never on what is printed: an escape code takes
bytes and no columns. Build a line as plain strings or a rich `Text` (whose
`cell_len` counts columns, a wide character as two), cut and pad it there, and
style it last. naiad.cli.terminal's `cut` counts characters, which is the same
measure for the text Naiad prints today. A Console made here never wraps or
crops a line itself: a line is cut to the width before it is printed, and one
the reader needs whole — a path, an id — must not be broken by a second wrap.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from rich.console import Console
from rich.text import Text
from rich.theme import Theme

from naiad.cli.terminal import terminal_width
from naiad.runtime.queue import DONE, JOINING, PARKED, RUNNING, WAITING, Status

# What became of an Entry, as a mark before its word. Filled where an agent is
# at work, hollow where nothing is happening yet or a person is wanted, and a
# tick once it is over. The word always follows: the mark is for the eye, and a
# reader matching on text matches the word.
GLYPHS: Mapping[Status, str] = {
    WAITING: "◌",
    RUNNING: "●",
    JOINING: "●",
    PARKED: "◌",
    DONE: "✓",
}

THEME = Theme(
    {
        # What became of an Entry or a Run. Parked is the loud one, because it
        # is the only one waiting on the person reading.
        "status.waiting": "dim",
        "status.running": "green",
        "status.joining": "cyan",
        "status.parked": "bold yellow",
        "status.done": "dim",
        # What a line names.
        "id": "bold",
        "repo": "blue",
        "branch": "magenta",
        "state": "cyan",
        # A column's name, and anything said beside the line rather than in it.
        "header": "bold",
        "secondary": "dim",
        # What `naiad doctor` found, by how much it matters.
        "severity.fail": "bold red",
        "severity.warn": "yellow",
        "severity.info": "blue",
        # The `naiad:` that opens a refusal.
        "refusal": "bold red",
    }
)


def console(*, stderr: bool = False) -> Console:
    """A Console for stdout, or for stderr, as the stream is at this moment.

    Made per call rather than once at import, because whether the stream is a
    terminal is decided when the Console is made, and the stream itself may
    have been replaced since — by a test capturing it, or a caller redirecting
    it.

    Markup, highlighting and emoji codes are all off: a Task, a path or an
    answer is printed as it was written, and `[bold]` or `:smile:` in one is the
    writer's text rather than an instruction.
    """
    return Console(
        stderr=stderr,
        theme=THEME,
        width=terminal_width(),
        color_system=None if _no_color() else "auto",
        markup=False,
        highlight=False,
        emoji=False,
        soft_wrap=True,
    )


def status(word: Status) -> Text:
    """What became of an Entry, as its mark and its word in its own style."""
    return Text(f"{GLYPHS[word]} {word}", style=f"status.{word}")


def refusal(message: str) -> Text:
    """A refusal as every command words it, `naiad: ` and then what was refused,
    with the prefix marked so the eye finds it among a Supervisor's lines."""
    return Text.assemble(("naiad:", "refusal"), " ", message)


def _no_color() -> bool:
    """Whether the operator asked for no colour. Any value but empty asks."""
    return os.environ.get("NO_COLOR", "") != ""


__all__ = ["GLYPHS", "THEME", "console", "refusal", "status"]
