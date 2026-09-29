"""The keys `naiad workflow set` and `unset` reach, and what each accepts.

One table rather than a verb per key, so a key another change promotes rides
both verbs by gaining a row. A value is checked before anything is written; the
reload after a write is the backstop, not the check. Model, effort and the
autocompact point are the platform's own syntax and are passed on as written,
so the check is that a value is one line of text and not that it is a known one.

`name` is not a row: renaming moves the file too, so it has a verb of its own,
and the refusal names that verb.
"""

from __future__ import annotations

from dataclasses import dataclass

from naiad.domain.workflow import WorkflowError

# A shape says what a value looks like to the author reading `--help`, and
# stands for the check that enforces it.
TEXT = "text"


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

# Keys a verb owns, and the verb that changes each.
_OWNED_BY_A_VERB = {"name": "naiad workflow rename"}


def file_value(key: str, text: str) -> str:
    """The value to write for `key`, or the reason it cannot be written.

    Raised as a WorkflowError so a caller answers a bad key and a bad file in
    one way.
    """
    row = _row(key, "set")
    if not text.strip():
        raise WorkflowError(
            f"{row.name} needs a value ({row.shape}); an empty one is not "
            f"an absence: remove the key with `naiad workflow unset WF {row.name}`"
        )
    if "\n" in text or "\r" in text:
        raise WorkflowError(f"{row.name} takes one line of text, not several")
    return text


def file_row(key: str) -> Key:
    """The row for `key`, for `unset`, which takes no value to check."""
    return _row(key, "unset")


def file_key_help() -> str:
    """The table as `--help` prints it: each key, its value shape, what it does."""
    width = max(len(key.name) for key in FILE_KEYS_TABLE)
    shape_width = max(len(key.shape) for key in FILE_KEYS_TABLE)
    return "\n".join(
        f"{key.name:<{width}}  {key.shape:<{shape_width}}  {key.meaning}"
        for key in FILE_KEYS_TABLE
    )


def _row(key: str, verb: str) -> Key:
    if key in _OWNED_BY_A_VERB:
        raise WorkflowError(f"'{key}' is changed with `{_OWNED_BY_A_VERB[key]}`, not {verb}")
    for row in FILE_KEYS_TABLE:
        if row.name == key:
            return row
    keys = ", ".join(row.name for row in FILE_KEYS_TABLE)
    raise WorkflowError(f"unknown key '{key}'; the keys are: {keys}")
