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
    # The effective Model and Effort, file-level default already applied — what
    # a State runs on is readable here with no walk back to the file's top.
    # None only when the file mentions the key nowhere, which is what lets
    # delivery leave the session's settings alone (ADR 0026).
    model: str | None = None
    effort: str | None = None

    @property
    def is_gate_state(self) -> bool:
        """A State with no Prompt: Naiad delivers nothing and the human types."""
        return self.prompt is None


@dataclass(frozen=True)
class Workflow:
    name: str
    states: tuple[State, ...]
    # The Answerer's model and effort, passed as flags on its headless invocation. No
    # required-default rule applies: a headless session starts clean every
    # time, so absence has no stickiness to be ambiguous about (ADR 0026).
    answerer_model: str | None = None
    answerer_effort: str | None = None
    # Models the platform may degrade to when the Answerer's is unavailable,
    # forwarded as --fallback-model and never parsed: a comma-separated list is
    # the flag's own syntax, not Naiad's (ADR 0031).
    answerer_fallback: str | None = None

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

    default_model = _optional_string(document, "model", reject)
    default_effort = _optional_string(document, "effort", reject)
    answerer_model, answerer_effort, answerer_fallback = _parse_answerer(document, reject)

    raw_states = document.get("states")
    if not raw_states or not isinstance(raw_states, list):
        raise reject("declares no states")

    states: list[State] = []
    seen: set[str] = set()
    for position, raw in enumerate(raw_states, start=1):
        if not isinstance(raw, dict):
            raise reject(f"state {position} is not a table")
        state = _parse_state(
            raw,
            position,
            reject,
            default_model=default_model,
            default_effort=default_effort,
        )
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

    return Workflow(
        name=name,
        states=tuple(states),
        answerer_model=answerer_model,
        answerer_effort=answerer_effort,
        answerer_fallback=answerer_fallback,
    )


def _optional_string(
    table: dict[str, Any], key: str, reject: Reject, *, owner: str = ""
) -> str | None:
    value = table.get(key)
    if value is not None and not isinstance(value, str):
        raise reject(f"{owner}{key} must be a string")
    return value


def _parse_answerer(
    document: dict[str, Any], reject: Reject
) -> tuple[str | None, str | None, str | None]:
    raw = document.get("answerer")
    if raw is None:
        return None, None, None
    if not isinstance(raw, dict):
        raise reject("answerer must be a table")
    return (
        _optional_string(raw, "model", reject, owner="answerer "),
        _optional_string(raw, "effort", reject, owner="answerer "),
        _optional_string(raw, "fallback", reject, owner="answerer "),
    )


def _parse_state(
    raw: dict[str, Any],
    position: int,
    reject: Reject,
    *,
    default_model: str | None,
    default_effort: str | None,
) -> State:
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

    # A State's own key without a file-level default is refused, because a
    # model set in the session is sticky: the States declaring nothing would
    # mean "whatever the previous State left behind", an order-dependent
    # surprise nobody chose (ADR 0026). Effort is refused identically.
    own_model = _optional_string(raw, "model", bad)
    if own_model is not None and default_model is None:
        raise reject(
            f"state '{name}' declares a model but the workflow has no file-level model default"
        )
    own_effort = _optional_string(raw, "effort", bad)
    if own_effort is not None and default_effort is None:
        raise reject(
            f"state '{name}' declares an effort but the workflow has no file-level effort default"
        )

    return State(
        name=name,
        prompt=prompt,
        clear=clear,
        terminal=terminal,
        next_candidates=tuple(successors),
        model=own_model if own_model is not None else default_model,
        effort=own_effort if own_effort is not None else default_effort,
    )
