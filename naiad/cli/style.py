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
style it last. A Console made here never wraps or
crops a line itself: a line is cut to the width before it is printed, and one
the reader needs whole — a path, an id — must not be broken by a second wrap.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

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
        "workflow": "bold",
        # How many a line reports, such as the Entries a Prune took.
        "count": "bold",
        # What Naiad does on entering a State. A Gate is the one that wants
        # a person, and a Terminal State does nothing but end the Run.
        "kind.prompt": "none",
        "kind.gate": "yellow",
        "kind.terminal": "dim",
        # The slash command a State's Prompt opens with: the words an operator
        # says a phase by.
        "command": "bold",
        # A column's name, and anything said beside the line rather than in it.
        "header": "bold",
        "secondary": "dim",
        # What `naiad doctor` found, by how much it matters, and a check
        # that found nothing wrong.
        "severity.ok": "green",
        "severity.fail": "bold red",
        "severity.warn": "yellow",
        "severity.info": "blue",
        # The `naiad:` that opens a refusal.
        "refusal": "bold red",
        # The verb that leads a line of a Run's narration, by what kind of
        # thing happened: the work going ahead, something the operator may
        # want to look at (an agent gone quiet, a Question put to the
        # Answerer, the Supervisor holding back), and an ending.
        "event.progress": "green",
        "event.attention": "bold yellow",
        "event.ended": "bold green",
        # Whose outcome a Question had in `naiad queue answers`: the
        # Answerer's, the operator's — loud, as parked is, since it was put to
        # them — or walked away from by the agent that asked it.
        "answer.answerer": "green",
        "answer.yours": "bold yellow",
        "answer.abandoned": "red",
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


# Where a cell has nothing to show: a dash wide enough not to be read as a
# hyphen in a name, rather than an empty cell that shifts the eye to the next.
ABSENT = "—"

# Between columns. Two spaces, so that a reader splitting a row on runs of two
# or more finds every cell, single spaces inside a cell included.
GAP = "  "

# The fewest columns the cut column is given, however narrow the terminal: a
# row too wide already is better wider still than showing nothing of it.
LEAST = 20


def columns(
    rows: Sequence[Sequence[Text | str]], *, width: int | None, least: int = LEAST
) -> list[Text]:
    """Rows as lines: each column padded to its widest cell, and the last cut
    with an ellipsis so that the line fits in width columns — or not cut at
    all where width is None, for a last column the reader needs whole, which a
    terminal wraps instead.

    Only the last column is cut, and the others are never touched, because they
    hold what a reader matches whole — an id, a path, a branch. When those
    alone fill the width, the last still keeps `least` columns and the line
    runs over; a terminal wraps it, and nothing a reader needs is lost. The
    last column is not padded, so no line ends in spaces.

    The first row is a header if the caller styles it as one. Cells are
    measured in cells rather than characters, and keep their styles.
    """
    lines = [[cell if isinstance(cell, Text) else Text(cell) for cell in row] for row in rows]
    widths = [max(line[at].cell_len for line in lines) for at in range(len(lines[0]) - 1)]
    room = None if width is None else max(width - sum(widths) - len(GAP) * len(widths), least)
    laid_out = []
    for line in lines:
        text = Text()
        for cell, column_width in zip(line, widths):
            text.append_text(cell)
            text.append(" " * (column_width - cell.cell_len) + GAP)
        last = line[-1].copy()
        if room is not None:
            last.truncate(room, overflow="ellipsis")
        text.append_text(last)
        laid_out.append(text)
    return laid_out


def status(word: Status) -> Text:
    """What became of an Entry, as its mark and its word in its own style."""
    return Text(f"{GLYPHS[word]} {word}", style=f"status.{word}")


def refusal(message: str) -> Text:
    """A refusal as every command words it, `naiad: ` and then what was refused,
    with the prefix marked so the eye finds it among a Supervisor's lines."""
    return Text.assemble(("naiad:", "refusal"), " ", message)


class Styled(str):
    """A line as its words, carrying the same words styled for a terminal.

    A str, so that whatever takes a line as text takes this one unchanged: a
    test's list, a log, `print`, a reader matching on its words. Only `say`
    looks for the styles, and a line that went through anything else — sliced,
    joined, formatted — is plain words again, which is never wrong, only
    undecorated.
    """

    text: Text

    def __new__(cls, text: Text, *, words: str | None = None) -> Styled:
        line = super().__new__(cls, text.plain if words is None else words)
        line.text = text
        return line

    @classmethod
    def assemble(cls, *pieces: str | tuple[str, str] | Text) -> Styled:
        """A line from its pieces in order, each plain, a Text, or words with
        the name of their style.

        Its words are the pieces' own rather than the Text's, which drops a
        control character such as a carriage return: a path or a Task quoted
        into a line reaches a reader off a terminal exactly as it was."""
        return cls(Text.assemble(*pieces), words="".join(map(_words, pieces)))


def _words(piece: str | tuple[str, str] | Text) -> str:
    """What one piece of a line says, without its style."""
    if isinstance(piece, Text):
        return piece.plain
    return piece if isinstance(piece, str) else piece[0]


def styled(line: str) -> Text:
    """A line as a terminal is shown it: its styles where it carries them,
    its words alone where it does not."""
    return line.text.copy() if isinstance(line, Styled) else Text(line)


def say(line: str, *, stderr: bool = False) -> None:
    """Print one line, styled only where the stream is a terminal.

    Where nothing will be coloured, the words are printed as they are rather
    than through the Console, which turns a tab into spaces and drops a
    carriage return. Off a terminal an agent, a hook or a script is reading,
    and a tab in a Task or an answer is the writer's; under NO_COLOR at a
    terminal, the terminal lays a tab out just as the Console would have.
    """
    out = console(stderr=stderr)
    if out.color_system is None:
        print(line, file=out.file, flush=True)
    else:
        out.print(styled(line))


def _no_color() -> bool:
    """Whether the operator asked for no colour. Any value but empty asks."""
    return os.environ.get("NO_COLOR", "") != ""


__all__ = [
    "ABSENT",
    "GAP",
    "GLYPHS",
    "LEAST",
    "THEME",
    "Styled",
    "columns",
    "console",
    "refusal",
    "say",
    "status",
    "styled",
]
