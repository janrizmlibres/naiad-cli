"""What an author reads of a Workflow: the library, the keys a file declares,
and its States as a table under a header.

The facts are the ones the adopting agent reads in `naiad states`, worded once
in naiad.domain.listing; only the layout here is the author's. That listing is
parsed by a skill installed on the operator's machine and keeps its text, so
everything a person might want of a table — a header, a dash in an empty cell,
colour — is here instead, where no program reads it.

Each renderer gives back a naiad.cli.style.Styled: the table's words, which a
test or a script reads as text, carrying the styles `say` prints at a
terminal.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text

from naiad.cli.style import ABSENT, GAP, Styled, columns
from naiad.domain.listing import file_keys, kind, marks, opening_command, successors
from naiad.domain.workflow import State, Workflow

STATE_COLUMNS = ("STATE", "KIND", "COMMAND", "NEXT", "MARKS")
LIBRARY_COLUMNS = ("WORKFLOW", "PROBLEM")


def render_library(held: Sequence[tuple[str, str | None]]) -> Styled:
    """Every entry the library holds, under a header, with what stops a Run
    starting from it beside its name.

    The problem is printed whole, however wide, because it is the sentence
    that says what to fix and a cut loses its end, which is that part.
    """
    rows = [
        [Text(name, style="workflow"), _cell(problem, style="severity.fail")]
        for name, problem in held
    ]
    return _table(LIBRARY_COLUMNS, rows, width=None)


def render_workflow(workflow: Workflow, *, width: int) -> Styled:
    """The keys the file declares, each dim beside its value, then the table
    of its States."""
    keys = [
        [Text(key, style="secondary"), Text(value, style="workflow" if key == "name" else "")]
        for key, value in file_keys(workflow)
    ]
    return Styled(
        Text("\n").join(
            [*columns(keys, width=width), Text(), render_state_list(workflow, width=width).text]
        )
    )


def render_state_list(workflow: Workflow, *, width: int) -> Styled:
    """Every State in declared order, one row each."""
    return _table(STATE_COLUMNS, [_state_row(state) for state in workflow.states], width=width)


def render_state(state: State) -> Styled:
    """One State's row under the header, with the columns that State fills,
    and nothing cut: asking for one State is asking for all of it, and a
    terminal wraps a row too wide for it.

    Its Prompt is not part of it: the command prints that as the author wrote
    it, since a Console would turn its tabs into spaces.
    """
    return _table(STATE_COLUMNS, [_state_row(state)], width=None)


def _state_row(state: State) -> list[Text]:
    """A State's cells: its name, its kind, the command its Prompt opens with,
    where the Run may go next, then its marks in one run, the last column and
    the one a narrow terminal cuts."""
    return [
        Text(state.name, style="state"),
        Text(kind(state), style=f"kind.{kind(state)}"),
        _cell(opening_command(state), style="command"),
        _successors(state),
        _cell(GAP.join(marks(state)) or None),
    ]


def _successors(state: State) -> Text:
    """The successors as `successors` words them, an arrow and the names, with
    each name styled as the State it is."""
    if successors(state) is None:
        return Text(ABSENT)
    names = Text(", ").join(Text(name, style="state") for name in state.next_candidates)
    return Text.assemble(("→ ", "secondary"), names)


def _cell(words: str | None, *, style: str = "") -> Text:
    return Text(ABSENT) if words is None else Text(words, style=style)


def _table(header: Sequence[str], rows: list[list[Text]], *, width: int | None) -> Styled:
    """The rows under the header, leaving out a column where no row has
    anything to show: a column of dashes is one more thing to read past, as a
    column of blanks is in the agent's listing."""
    kept = [at for at in range(len(header)) if any(row[at].plain != ABSENT for row in rows)]
    laid_out = [
        [Text(header[at], style="header") for at in kept],
        *([row[at] for at in kept] for row in rows),
    ]
    return Styled(Text("\n").join(columns(laid_out, width=width)))


__all__ = [
    "LIBRARY_COLUMNS",
    "STATE_COLUMNS",
    "render_library",
    "render_state",
    "render_state_list",
    "render_workflow",
]
