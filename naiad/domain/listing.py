"""What a Workflow declares, laid out for an agent choosing where to start.

The operator names a phase in their own words — "spec this out" — and the
State is called `spec` while the Prompt that runs it opens with `/to-spec`.
Nothing joined those two until this listing did, and an agent guessing at
States it has not read is what it exists to prevent.

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
    return "\n".join([_heading(workflow), *_state_lines(workflow)])


def render_workflow(workflow: Workflow) -> str:
    """The file-level keys the Workflow declares, then its States through the
    same lines `render_states` prints, so the two readers cannot disagree."""
    return "\n".join([*_file_lines(workflow), "", *_state_lines(workflow)])


def render_state_list(workflow: Workflow) -> str:
    """The States alone, one per line: what `render_states` prints under the
    Workflow's name, for the reader who has already named the Workflow."""
    return "\n".join(_state_lines(workflow))


def render_state(workflow: Workflow, state: State) -> str:
    """One State: its line exactly as the listing prints it, columns aligned to
    the States around it, then its Prompt in full.

    The Prompt is what the listing cuts to a command, and the only part of a
    State an author cannot read off a line. A Gate and a Terminal State without
    one show their line alone.
    """
    line = _state_lines(workflow)[workflow.states.index(state)]
    if state.prompt is None:
        return line
    return f"{line}\n\n{state.prompt.rstrip()}"


def _state_lines(workflow: Workflow) -> list[str]:
    commands = [_opening_command(state) or "" for state in workflow.states]
    names = [state.name for state in workflow.states]
    name_width = max(len(name) for name in names)
    kind_width = max(len(_kind(state)) for state in workflow.states)
    command_width = max(len(command) for command in commands)
    return [
        _line(state, command, name_width, kind_width, command_width)
        for state, command in zip(workflow.states, commands)
    ]


def _file_lines(workflow: Workflow) -> list[str]:
    """Only what the file says: a key it leaves out is no opinion, and listing
    it as empty would read as one."""
    declared = [
        ("name", workflow.name),
        ("model", workflow.model),
        ("effort", workflow.effort),
        ("autocompact", workflow.autocompact),
        ("answerer.model", workflow.answerer_model),
        ("answerer.effort", workflow.answerer_effort),
        ("answerer.fallback", workflow.answerer_fallback),
    ]
    shown = [(key, value) for key, value in declared if value is not None]
    width = max(len(key) for key, _ in shown)
    return [f"{key:<{width}}{GAP}{value}" for key, value in shown]


def _heading(workflow: Workflow) -> str:
    """The Workflow's name, and beside it the one file-level fact an Adoption
    has to relay: the point at which the Workflow wants the Session to
    summarise itself. An Adoption types nothing into the human's Session, so
    the human is told what it wants instead, and this is where the adopt skill
    reads it."""
    if workflow.autocompact is None:
        return workflow.name
    return f"{workflow.name}{GAP}(autocompact {workflow.autocompact})"


def _line(
    state: State, command: str, name_width: int, kind_width: int, command_width: int
) -> str:
    cells = [f"{state.name:<{name_width}}", f"{_kind(state):<{kind_width}}"]
    # A Workflow whose every Prompt opens with prose has no command column at
    # all, rather than a column of blanks the reader has to account for.
    if command_width:
        cells.append(f"{command:<{command_width}}")
    marks = _marks(state)
    if marks:
        cells.append(marks)
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


def _kind(state: State) -> str:
    """What Naiad does on entering the State.

    Terminal before Gate, and never both: a Terminal State with no Prompt ends
    the Run rather than holding it for a human, so reading it as a Gate State
    would promise a handover that never comes.
    """
    if state.terminal:
        return "terminal"
    if state.is_gate_state:
        return "gate"
    return "prompt"


def _marks(state: State) -> str:
    """What else starting here would commit the Run to, after the kind."""
    marks = []
    if state.next_candidates:
        marks.append("→ " + ", ".join(state.next_candidates))
    if state.clear:
        marks.append("clears")
    if state.report:
        marks.append("report")
    # Only where a Prompt is delivered: a Gate hands the Run to a human and a
    # Terminal State ends it, so neither asks a Question or runs on a Model.
    if _kind(state) == "prompt":
        marks.append(f"questions: {state.questions}")
        if state.model is not None:
            marks.append(f"model: {state.model}")
        if state.effort is not None:
            marks.append(f"effort: {state.effort}")
    return GAP.join(marks)


__all__ = ["render_state", "render_state_list", "render_states", "render_workflow"]
