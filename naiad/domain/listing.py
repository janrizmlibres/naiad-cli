"""What a Workflow declares, laid out for an agent choosing where to start.

The operator names a phase in their own words — "spec this out" — and the
State is called `spec` while the Prompt that runs it opens with `/to-spec`.
Nothing joined those two until this listing did, and an agent guessing at
States it has not read is what it exists to prevent.

The facts a line is made of — a State's kind, its command, its successors and
its marks, and the keys the file itself declares — are worded here once, and
the author's tables (naiad.cli.workflow_view) lay out these same words, so a
mark cannot mean one thing to the author and another to the agent. The layout
of `render_states` is the agent's alone, and the adopt skill parses it: an
installed copy of that skill outlives a release, so its text does not change.

Pure: a Workflow in, text out. Which Workflows to render, and where the text
goes, belong to the command (naiad.cli.main).
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


def _state_lines(workflow: Workflow) -> list[str]:
    commands = [opening_command(state) or "" for state in workflow.states]
    names = [state.name for state in workflow.states]
    name_width = max(len(name) for name in names)
    kind_width = max(len(kind(state)) for state in workflow.states)
    command_width = max(len(command) for command in commands)
    return [
        _line(state, command, name_width, kind_width, command_width)
        for state, command in zip(workflow.states, commands)
    ]


def file_keys(workflow: Workflow) -> list[tuple[str, str]]:
    """The file-level keys the Workflow declares, as (key, value), its name
    first.

    Only what the file says: a key it leaves out is no opinion, and listing
    it as empty would read as one.
    """
    declared = [
        ("name", workflow.name),
        ("model", workflow.model),
        ("effort", workflow.effort),
        ("autocompact", workflow.autocompact),
        ("answerer.model", workflow.answerer_model),
        ("answerer.effort", workflow.answerer_effort),
        ("answerer.fallback", workflow.answerer_fallback),
    ]
    return [(key, value) for key, value in declared if value is not None]


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
    cells = [f"{state.name:<{name_width}}", f"{kind(state):<{kind_width}}"]
    # A Workflow whose every Prompt opens with prose has no command column at
    # all, rather than a column of blanks the reader has to account for.
    if command_width:
        cells.append(f"{command:<{command_width}}")
    # The successors lead the marks, on the same line and in the same run.
    led = [successors(state), *marks(state)]
    shown = GAP.join(mark for mark in led if mark is not None)
    if shown:
        cells.append(shown)
    return (GAP + GAP.join(cells)).rstrip()


def opening_command(state: State) -> str | None:
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


def kind(state: State) -> str:
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


def successors(state: State) -> str | None:
    """Where the Run may go from the State, where the State says: the States
    the agent may announce next, as an arrow and their names."""
    if not state.next_candidates:
        return None
    return "→ " + ", ".join(state.next_candidates)


def marks(state: State) -> list[str]:
    """What else starting here would commit the Run to, after the kind and
    the successors."""
    shown = []
    if state.clear:
        shown.append("clears")
    if state.report:
        shown.append("report")
    # Only where a Prompt is delivered: a Gate hands the Run to a human and a
    # Terminal State ends it, so neither asks a Question or runs on a Model.
    if kind(state) == "prompt":
        shown.append(f"questions: {state.questions}")
        if state.model is not None:
            shown.append(f"model: {state.model}")
        if state.effort is not None:
            shown.append(f"effort: {state.effort}")
    return shown


__all__ = ["file_keys", "kind", "marks", "opening_command", "render_states", "successors"]
