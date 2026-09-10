"""What a Workflow declares, laid out for an agent choosing where to start.

The operator names a phase in their own words — "spec this out" — and the
State is called `spec` while the Prompt that runs it opens with `/to-spec`.
Nothing joined those two until this listing did, and an agent guessing at
States it has not read is what it exists to prevent (ADR 0032).

Pure: a Workflow in, a block of text out. Which Workflows to render, and where
the text goes, belong to the command (naiad.cli.main).
"""

from __future__ import annotations

from naiad.domain.workflow import State, Workflow

# Between columns. Two, so that a name and a command stay legible as separate
# things without a rule drawn between them.
GAP = "  "


def render_states(workflow: Workflow) -> str:
    """Every State the Workflow declares, in declared order, one per line.

    Declared order rather than any resolution of it: the agent is choosing
    where along the Workflow the human stopped, which is a position in the
    file rather than a path through it.
    """
    commands = [_opening_command(state) or "" for state in workflow.states]
    names = [state.name for state in workflow.states]
    name_width = max(len(name) for name in names)
    command_width = max(len(command) for command in commands)

    lines = [_heading(workflow)]
    for state, command in zip(workflow.states, commands):
        lines.append(_line(state, command, name_width, command_width))
    return "\n".join(lines)


def _heading(workflow: Workflow) -> str:
    """The Workflow's name, and beside it the one file-level fact an Adoption
    has to relay: the point at which the Workflow wants the Session to
    summarise itself. An Adoption types nothing into the human's Session, so
    the human is told what it wants instead, and this is where the adopt skill
    reads it (ADR 0047)."""
    if workflow.autocompact is None:
        return workflow.name
    return f"{workflow.name}{GAP}(autocompact {workflow.autocompact})"


def _line(state: State, command: str, name_width: int, command_width: int) -> str:
    cells = [f"{state.name:<{name_width}}"]
    # A Workflow whose every Prompt opens with prose has no command column at
    # all, rather than a column of blanks the reader has to account for.
    if command_width:
        cells.append(f"{command:<{command_width}}")
    note = _note(state)
    if note:
        cells.append(note)
    return (GAP + GAP.join(cells)).rstrip()


def _opening_command(state: State) -> str | None:
    """The slash command the State's Prompt opens with, where it opens with one.

    A Prompt that runs a skill must open with its command, because Claude Code
    reads one only at the start of a message — which is what makes the first
    token worth reading and the rest of the Prompt not. A Prompt opening with
    prose has no command, and its first word is not one.
    """
    if state.prompt is None:
        return None
    opening = state.prompt.strip().split(maxsplit=1)
    if not opening or not opening[0].startswith("/"):
        return None
    return opening[0]


def _note(state: State) -> str:
    """What starting here would commit the Run to.

    Terminal before Gate, and never both: a Terminal State with no Prompt ends
    the Run rather than holding it for a human, so reading it as a Gate State
    would promise a handover that never comes.
    """
    marks = []
    if state.terminal:
        marks.append("terminal")
    elif state.is_gate_state:
        marks.append("gate")
    if state.next_candidates:
        marks.append("branches: " + ", ".join(state.next_candidates))
    return GAP.join(marks)


__all__ = ["render_states"]
