"""Workflow parsing and validation.

A Workflow is an ordered list of States read from a TOML file. Naiad knows
nothing about what any particular Workflow means; it only needs the order, the
Prompts, which States Clear, and which State ends the Run.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = "<workflow>"


class WorkflowError(Exception):
    """A Workflow file that cannot be run, rejected before a Run exists."""


# Names the workflow source in every message, so an error always says which file.
Reject = Callable[[str], WorkflowError]


@dataclass(frozen=True)
class State:
    name: str
    prompt: str | None = None
    clear: bool = False
    terminal: bool = False
    next_candidates: tuple[str, ...] = ()

    @property
    def is_gate_state(self) -> bool:
        """A State with no Prompt: Naiad delivers nothing and the human types."""
        return self.prompt is None


@dataclass(frozen=True)
class Workflow:
    name: str
    states: tuple[State, ...]

    def state(self, name: str) -> State | None:
        for state in self.states:
            if state.name == name:
                return state
        return None


def load_workflow(path: Path) -> Workflow:
    try:
        text = path.read_text()
    except OSError as error:
        raise WorkflowError(f"workflow {path}: cannot be read ({error.strerror})") from error
    return parse_workflow(text, source=str(path))


def parse_workflow(text: str, *, source: str = DEFAULT_SOURCE) -> Workflow:
    def reject(problem: str) -> WorkflowError:
        return WorkflowError(f"workflow {source}: {problem}")

    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise reject(f"not valid TOML ({error})") from error

    name = document.get("name")
    if not isinstance(name, str) or not name:
        raise reject("has no name")

    raw_states = document.get("states")
    if not raw_states or not isinstance(raw_states, list):
        raise reject("declares no states")

    states: list[State] = []
    seen: set[str] = set()
    for position, raw in enumerate(raw_states, start=1):
        if not isinstance(raw, dict):
            raise reject(f"state {position} is not a table")
        state = _parse_state(raw, position, reject)
        if state.name in seen:
            raise reject(f"duplicate state name '{state.name}'")
        seen.add(state.name)
        states.append(state)

    for state in states:
        for candidate in state.next_candidates:
            if candidate not in seen:
                raise reject(f"state '{state.name}' declares unknown successor '{candidate}'")

    if not any(state.terminal for state in states):
        raise reject("has no terminal state, so a run could never end")

    return Workflow(name=name, states=tuple(states))


def _parse_state(raw: dict[str, Any], position: int, reject: Reject) -> State:
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise reject(f"state {position} has no name")

    def bad(problem: str) -> WorkflowError:
        return reject(f"state '{name}': {problem}")

    prompt = raw.get("prompt")
    if prompt is not None and not isinstance(prompt, str):
        raise bad("prompt must be a string")

    clear = raw.get("clear", False)
    if not isinstance(clear, bool):
        raise bad("clear must be a boolean")

    terminal = raw.get("terminal", False)
    if not isinstance(terminal, bool):
        raise bad("terminal must be a boolean")

    successors = raw.get("next", [])
    if not isinstance(successors, list) or not all(isinstance(s, str) for s in successors):
        raise bad("next must be a list of state names")

    return State(
        name=name,
        prompt=prompt,
        clear=clear,
        terminal=terminal,
        next_candidates=tuple(successors),
    )
