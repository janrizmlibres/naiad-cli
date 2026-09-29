"""The keys `naiad workflow set` and `unset` reach, and what each accepts.

One table rather than a verb per key, so a key another change promotes rides
both verbs by gaining a row. A value is checked before anything is written; the
reload after a write is the backstop, not the check. Model, effort and the
autocompact point are the platform's own syntax and are passed on as written,
so the check is that a value is one line of text and not that it is a known one.

A key a verb owns is not a row: `name` moves a file or edges, `prompt` is a
whole editing session and `next` a list, so each has a verb of its own and the
refusal names it.
"""

from __future__ import annotations

from dataclasses import dataclass

from naiad.domain.workflow import QUESTIONS_TO, WorkflowError

# A shape says what a value looks like to the author reading `--help`, and
# stands for the check that enforces it.
TEXT = "text"
FLAG = "true|false"
QUESTIONS = "|".join(QUESTIONS_TO)


@dataclass(frozen=True)
class Key:
    name: str
    shape: str
    meaning: str


FILE_KEYS_TABLE: tuple[Key, ...] = (
    Key("model", TEXT, "the Model every State asks for unless it names its own"),
    Key("effort", TEXT, "the Effort every State asks for unless it names its own"),
    Key("autocompact", "text, such as 200k", "where the Session summarises its own context"),
    Key("answerer.model", TEXT, "the Answerer's Model"),
    Key("answerer.effort", TEXT, "the Answerer's Effort"),
    Key("answerer.fallback", "text, comma-separated", "the Models the Answerer may degrade to"),
)

STATE_KEYS_TABLE: tuple[Key, ...] = (
    Key("model", TEXT, "the Model this State asks for, over the file's"),
    Key("effort", TEXT, "the Effort this State asks for, over the file's"),
    Key("clear", FLAG, "whether entering this State opens a fresh context"),
    Key("terminal", FLAG, "whether this State ends the Run"),
    Key("questions", QUESTIONS, "whose a Question asked from this State is"),
    Key("report", FLAG, "whether the operator is told when the Run enters this State"),
)

# Keys a verb owns, and the verb that changes each.
_FILE_KEYS_OWNED = {"name": "naiad workflow rename"}
_STATE_KEYS_OWNED = {
    "name": "naiad state rename",
    "prompt": "naiad state set-prompt",
    "next": "naiad state next",
}


def file_value(key: str, text: str) -> str:
    """The value to write for a file-level `key`, or the reason it cannot be
    written.

    Raised as a WorkflowError so a caller answers a bad key and a bad file in
    one way.
    """
    return _one_line(_FILE, key, text)[1]


def file_row(key: str) -> Key:
    """The row for `key`, for `unset`, which takes no value to check."""
    return _row(_FILE, key, "unset")


def file_key_help() -> str:
    """The table as `--help` prints it: each key, its value shape, what it does."""
    return _help(FILE_KEYS_TABLE)


def state_value(key: str, text: str) -> str | bool:
    """The value to write for a State's `key`: a boolean for a flag, else the
    text as given."""
    row, value = _one_line(_STATE, key, text)
    if row.shape == FLAG:
        return _flag(row, value)
    if row.shape == QUESTIONS:
        return _questions(row, value)
    return value


def state_row(key: str) -> Key:
    """The row for a State's `key`, for `unset`."""
    return _row(_STATE, key, "unset")


def state_key_help() -> str:
    return _help(STATE_KEYS_TABLE)


@dataclass(frozen=True)
class _Level:
    """One place a key can live: its rows, the keys a verb owns there, and the
    words that name the `unset` a refusal points at."""

    rows: tuple[Key, ...]
    owned: dict[str, str]
    unset: str


_FILE = _Level(FILE_KEYS_TABLE, _FILE_KEYS_OWNED, "naiad workflow unset WF")
_STATE = _Level(STATE_KEYS_TABLE, _STATE_KEYS_OWNED, "naiad state unset WF STATE")


def _one_line(level: _Level, key: str, text: str) -> tuple[Key, str]:
    row = _row(level, key, "set")
    if not text.strip():
        raise WorkflowError(
            f"{row.name} needs a value ({row.shape}); an empty one is not "
            f"an absence: remove the key with `{level.unset} {row.name}`"
        )
    if "\n" in text or "\r" in text:
        raise WorkflowError(f"{row.name} takes one line of text, not several")
    return row, text


def _flag(row: Key, text: str) -> bool:
    if text.lower() not in ("true", "false"):
        raise WorkflowError(f"{row.name} is {FLAG}, not '{text}'")
    return text.lower() == "true"


def _questions(row: Key, text: str) -> str:
    if text not in QUESTIONS_TO:
        raise WorkflowError(f"{row.name} is {QUESTIONS}, not '{text}'")
    return text


def _help(rows: tuple[Key, ...]) -> str:
    width = max(len(key.name) for key in rows)
    shape_width = max(len(key.shape) for key in rows)
    return "\n".join(
        f"{key.name:<{width}}  {key.shape:<{shape_width}}  {key.meaning}" for key in rows
    )


def _row(level: _Level, key: str, verb: str) -> Key:
    if key in level.owned:
        raise WorkflowError(f"'{key}' is changed with `{level.owned[key]}`, not {verb}")
    for row in level.rows:
        if row.name == key:
            return row
    keys = ", ".join(row.name for row in level.rows)
    raise WorkflowError(f"unknown key '{key}'; the keys are: {keys}")
