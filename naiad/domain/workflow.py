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
from typing import Any, Literal

DEFAULT_SOURCE = "<workflow>"

# Whose a State's Questions are. The file decides the default: the Answerer's
# where it declares an `[answerer]` table, the human's where it does not, and a
# State's own key overrides either.
QuestionsTo = Literal["answerer", "human"]
QUESTIONS_TO: tuple[QuestionsTo, ...] = ("answerer", "human")


# The keys each place in a Workflow file accepts. Anything else is refused at
# load, so a misspelt key cannot load as if it were absent and a file written
# for a newer Naiad fails loudly on an older one instead of losing its new keys
# without a word. This is the whole of the format's versioning.
FILE_KEYS = ("name", "model", "effort", "autocompact", "answerer", "states")
STATE_KEYS = (
    "name",
    "prompt",
    "clear",
    "terminal",
    "next",
    "model",
    "effort",
    "questions",
    "report",
)
ANSWERER_KEYS = ("model", "effort", "fallback")


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
    # The Model and Effort this State asks for, file-level default already
    # applied. None where neither the State nor the file names the key, which
    # is what lets delivery leave the session's settings alone and
    # what makes a State's silence an absent opinion rather than a value to
    # find.
    model: str | None = None
    effort: str | None = None
    # Who answers a Question asked from this State, the file's default already
    # applied. "human" means the Answerer is never consulted and the Run parks
    # as it does on an Escalation, with the human answering in the Session.
    questions: QuestionsTo = "answerer"
    # Whether the State wrote the `questions` key itself. It picks the reason a human
    # Question is parked with: a State that asked for the human reserves its
    # Questions, while one the file's default gave them to names the missing
    # Answerer.
    questions_explicit: bool = False
    # Whether an Announcement of this State is Reported: the operator is told
    # the Run entered it and nothing is handed over. Never set on a
    # Gate State or a Terminal State, which already tell on entry.
    report: bool = False

    @property
    def is_gate_state(self) -> bool:
        """A State with no Prompt: Naiad delivers nothing and the human types."""
        return self.prompt is None


@dataclass(frozen=True)
class Workflow:
    name: str
    states: tuple[State, ...]
    # The Answerer's model and effort, passed as flags on its headless
    # invocation. Absence means no opinion here as it does on a State, but
    # resolves elsewhere: a headless session starts clean every time, so it
    # inherits nothing and the platform's own default answers.
    answerer_model: str | None = None
    answerer_effort: str | None = None
    # Models the platform may degrade to when the Answerer's is unavailable,
    # forwarded as --fallback-model and never parsed: a comma-separated list is
    # the flag's own syntax, not Naiad's.
    answerer_fallback: str | None = None
    # Where the Session summarises its own context, handed to the launch as
    # `--autocompact` and never read: the value is the platform's syntax, not
    # Naiad's. File-level and never per State because it is a property of the
    # Session, set once as it opens. None means no flag.
    autocompact: str | None = None
    # The file-level Model and Effort, kept beside the States that already have
    # them applied so that a reader of the file (`naiad workflow show`) can say
    # what the file itself declares rather than only what each State resolved to.
    model: str | None = None
    effort: str | None = None

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

    _refuse_unknown_keys(document, FILE_KEYS, "the file", reject)

    name = document.get("name")
    if not isinstance(name, str) or not name:
        raise reject("has no name")

    default_model = _optional_string(document, "model", reject)
    default_effort = _optional_string(document, "effort", reject)
    answerer_model, answerer_effort, answerer_fallback = _parse_answerer(document, reject)
    default_questions: QuestionsTo = "answerer" if "answerer" in document else "human"
    autocompact = _optional_string(document, "autocompact", reject)

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
            default_questions=default_questions,
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
        autocompact=autocompact,
        model=default_model,
        effort=default_effort,
    )


def _refuse_unknown_keys(
    table: dict[str, Any], allowed: tuple[str, ...], place: str, reject: Reject
) -> None:
    for key in table:
        if key not in allowed:
            raise reject(f"unknown key '{key}' in {place}; allowed: {', '.join(allowed)}")


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
    _refuse_unknown_keys(raw, ANSWERER_KEYS, "[answerer]", reject)
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
    default_questions: QuestionsTo,
) -> State:
    name = raw.get("name")
    # Checked before the name is demanded, so a State whose `name` is misspelt
    # is told which key is unknown rather than that it has no name.
    place = f"state '{name}'" if isinstance(name, str) and name else f"state {position}"
    _refuse_unknown_keys(raw, STATE_KEYS, place, reject)
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

    # A State's own key needs no file-level default beneath it. Absence is no
    # opinion: the State gets None, delivery types no Switch, and it runs on
    # what the session holds — the previous State's setting, since a session's
    # settings are sticky. Effort behaves identically.
    own_model = _optional_string(raw, "model", bad)
    own_effort = _optional_string(raw, "effort", bad)

    report = raw.get("report", False)
    if not isinstance(report, bool):
        raise bad("report must be a boolean")
    # Refused rather than ignored: each of these already tells the operator on
    # entry, a Notify and a Finish, and a second telling is a mistake to point
    # out. `report = false` says nothing and is accepted anywhere.
    if report and terminal:
        raise bad("report is refused on a Terminal State, which already tells on entry")
    if report and prompt is None:
        raise bad("report is refused on a Gate State, which already tells on entry")

    questions = raw.get("questions", default_questions)
    if questions not in QUESTIONS_TO:
        raise bad('questions must be "answerer" or "human"')

    return State(
        name=name,
        prompt=prompt,
        clear=clear,
        terminal=terminal,
        next_candidates=tuple(successors),
        model=own_model if own_model is not None else default_model,
        effort=own_effort if own_effort is not None else default_effort,
        questions=questions,
        questions_explicit="questions" in raw,
        report=report,
    )
