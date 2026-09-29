"""Editing a Workflow's States in its TOML document.

The operations behind `naiad state`, each taking the document an
`edit_workflow` hands its callback (naiad.runtime.workflow_file), which is
where they are validated, written and undone. Here is only what each does to
the document, and the refusals an author needs worded in their own terms: a
State that is not there, a name taken, an edge that would be left dangling.

A State keeps whatever the author wrote around it. New keys go in beside its
others, ahead of the blank line and comment that follow it, and a State put
somewhere new is set apart from its neighbours by a blank line.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import tomlkit
import tomlkit.items

from naiad.domain.workflow import State, Workflow, WorkflowError

Table = tomlkit.items.Table


def add_state(
    document: tomlkit.TOMLDocument,
    name: str,
    *,
    prompt: str | None = None,
    terminal: bool = False,
    clear: bool = False,
    model: str | None = None,
    effort: str | None = None,
    questions: str | None = None,
    successors: Sequence[str] = (),
    after: str | None = None,
    before: str | None = None,
) -> None:
    """Insert a State. Before the first terminal State unless placed with
    `after` or `before`, and at the end when it is itself terminal. A key not
    given is not written, because a State's silence is no opinion."""
    states = _states(document)
    _check_placeable(_title(document), _names(states), name, (after, before))

    table = tomlkit.table()
    table.add("name", name)
    for key, value in (("model", model), ("effort", effort)):
        if value is not None:
            table.add(key, value)
    if clear:
        table.add("clear", True)
    if terminal:
        table.add("terminal", True)
    if questions is not None:
        table.add("questions", questions)
    if successors:
        table.add("next", list(successors))
    if prompt is not None:
        table.add("prompt", _prompt_item(prompt))

    if after is not None:
        index = _find(document, after)[0] + 1
    elif before is not None:
        index = _find(document, before)[0]
    elif terminal:
        index = len(states)
    else:
        index = _first_terminal(states)
    _seat(states, index, table)


def set_state_key(
    document: tomlkit.TOMLDocument, state: str, key: str, value: str | bool
) -> None:
    _put(_find(document, state)[1], key, value)


def unset_state_key(document: tomlkit.TOMLDocument, state: str, key: str) -> bool:
    """Delete a State's key, because its absence means no opinion. Returns
    whether there was a key to delete, so the caller can say which."""
    table = _find(document, state)[1]
    if key not in table:
        return False
    del table[key]
    return True


def set_prompt(document: tomlkit.TOMLDocument, state: str, text: str) -> None:
    """Replace a State's Prompt, giving a Gate one."""
    _put(_find(document, state)[1], "prompt", _prompt_item(text))


def set_next(document: tomlkit.TOMLDocument, state: str, successors: Sequence[str]) -> None:
    """Replace a State's successors. None deletes the key: a State without
    `next` hands over to the one declared after it."""
    table = _find(document, state)[1]
    if successors:
        _put(table, "next", list(successors))
    elif "next" in table:
        del table["next"]


def rename_state(document: tomlkit.TOMLDocument, state: str, new: str) -> None:
    """Rename a State and every edge that names it."""
    _, table = _find(document, state)
    if _index_of(_states(document), new) is not None:
        raise _taken(_title(document), new)

    table["name"] = new
    for other in _states(document):
        successors = other.get("next")
        for at, successor in enumerate(successors or ()):
            if successor == state:
                successors[at] = new


def remove_state(document: tomlkit.TOMLDocument, state: str) -> None:
    """Delete a State, unless another still names it: the edge would be left
    pointing at nothing, and the author is told which States to change."""
    index, table = _find(document, state)
    naming = [
        other["name"]
        for other in _states(document)
        if other is not table and state in other.get("next", ())
    ]
    if naming:
        raise WorkflowError(
            f"cannot remove '{state}': {', '.join(naming)} name{'s' if len(naming) == 1 else ''} "
            "it in `next`; change that first with `naiad state next`"
        )
    del _states(document)[index]


def move_state(
    document: tomlkit.TOMLDocument,
    state: str,
    *,
    after: str | None = None,
    before: str | None = None,
) -> None:
    """Reorder the declared States, the State's own keys and comments with it."""
    anchor = after if after is not None else before
    if anchor is None:
        raise WorkflowError("say where to move it: --after or --before another State")
    index, table = _find(document, state)
    _find(document, anchor)
    if anchor == state:
        raise WorkflowError(f"cannot place '{state}' beside itself")

    states = _states(document)
    del states[index]
    target = _index_of(states, anchor)
    assert target is not None
    _seat(states, target + 1 if after is not None else target, table)


def require_state(workflow: Workflow, name: str) -> State:
    """The State of this name, or the refusal naming the States there are.

    For the verb that must know before it asks the author for anything: an
    editor session lost to a misspelt name is the cost of finding out late.
    """
    state = workflow.state(name)
    if state is None:
        raise _no_state(workflow.name, [held.name for held in workflow.states], name)
    return state


def check_placeable(
    workflow: Workflow, name: str, *, after: str | None = None, before: str | None = None
) -> None:
    """Refuse a State that could not be added, ahead of asking for its Prompt."""
    _check_placeable(workflow.name, [held.name for held in workflow.states], name, (after, before))


def _check_placeable(
    title: str, held: Sequence[str], name: str, anchors: Sequence[str | None]
) -> None:
    if name in held:
        raise _taken(title, name)
    for anchor in anchors:
        if anchor is not None and anchor not in held:
            raise _no_state(title, held, anchor)


def _taken(title: str, name: str) -> WorkflowError:
    return WorkflowError(f"State '{name}' already exists in workflow '{title}'")


def _no_state(title: str, held: Sequence[str], name: str) -> WorkflowError:
    return WorkflowError(
        f"workflow '{title}' has no State '{name}'; its States are: {', '.join(held)}"
    )


def _names(states: tomlkit.items.AoT) -> list[str]:
    return [str(table.get("name")) for table in states]


def _first_terminal(states: tomlkit.items.AoT) -> int:
    """Where a State lands by default: ahead of the first terminal one, so it
    runs before the Run ends. At the end when nothing there is terminal."""
    for at, table in enumerate(states):
        if table.get("terminal") is True:
            return at
    return len(states)


def _states(document: tomlkit.TOMLDocument) -> tomlkit.items.AoT:
    states = document.get("states")
    if not isinstance(states, tomlkit.items.AoT):
        raise WorkflowError(f"workflow '{_title(document)}' declares no states")
    return states


def _title(document: tomlkit.TOMLDocument) -> str:
    return str(document.get("name", "?"))


def _index_of(states: tomlkit.items.AoT, name: str) -> int | None:
    for at, table in enumerate(states):
        if table.get("name") == name:
            return at
    return None


def _find(document: tomlkit.TOMLDocument, name: str) -> tuple[int, Table]:
    states = _states(document)
    index = _index_of(states, name)
    if index is None:
        raise _no_state(_title(document), _names(states), name)
    return index, states[index]


def _put(table: Table, key: str, value: Any) -> None:
    """Write a key where it stands, or beside the State's others when new: a
    plain assignment would append it after the blank line and comment that
    close the State, where a reader takes it for the next State's.

    Placed through the table's own container, the call that puts a key
    mid-table with the trivia around it intact; tests/test_state_file.py holds
    the placement, so an upgrade that changes it fails there."""
    if key in table:
        table[key] = value
    else:
        table.value._insert_after(list(table.keys())[-1], key, value)


def _seat(states: tomlkit.items.AoT, index: int, table: Table) -> None:
    states.insert(index, table)
    if index > 0:
        _separate(states[index - 1])
    if index < len(states) - 1:
        _separate(states[index])


def _separate(table: Table) -> None:
    if not table.as_string().endswith("\n\n"):
        table.add(tomlkit.nl())


def _prompt_item(text: str) -> tomlkit.items.Item:
    """A Prompt as the file's own prompts are written: on one line when it is
    one line, and otherwise a multi-line string opening on its own line and
    ending on a newline, so the block reads as it will be delivered."""
    text = text.replace("\r\n", "\n").lstrip("\n").rstrip()
    if "\n" not in text:
        return tomlkit.string(text)
    escaped = "".join(_escaped(character) for character in text + "\n")
    escaped = escaped.replace('"""', '""\\"')
    item = tomlkit.parse(f'prompt = """\n{escaped}"""\n').item("prompt")
    assert isinstance(item, tomlkit.items.String)
    return item


def _escaped(character: str) -> str:
    if character == "\\":
        return "\\\\"
    if character not in "\n\t" and (ord(character) < 0x20 or ord(character) == 0x7F):
        return f"\\u{ord(character):04x}"
    return character


__all__ = [
    "add_state",
    "check_placeable",
    "move_state",
    "remove_state",
    "rename_state",
    "require_state",
    "set_next",
    "set_prompt",
    "set_state_key",
    "unset_state_key",
]
