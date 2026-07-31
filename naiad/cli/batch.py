"""A batch file: many Entries described in one document.

What makes a file worth having is that a batch is heterogeneous — three bugs
starting at the diagnosing State and two designs starting at the grilling
State, each naming its own Working branch and pinned base. Repeated flags
cannot express that without positional pairing nobody can read.

TOML, like a Workflow file, because it is written by a person or an agent
rather than by Naiad — where an Entry's own storage is JSON, like a Run's
metadata, because Naiad writes that.

A batch is not a domain concept. It produces N Entries and the Queue does not
know they arrived together: nothing has been asked of it that requires knowing.
So there is nothing here but reading a file and queueing what it declares, and
this module lives with the commands rather than in the domain layer.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from naiad.cli.enqueue import REFUSALS, Work, prepare
from naiad.cli.library import LibraryError, resolve_workflow
from naiad.cli.refusals import BATCH_ENTRY
from naiad.domain.entry import Entry
from naiad.domain.workflow import WorkflowError
from naiad.runtime.queue import Queue
from naiad.runtime.run import RunStore

# The table an Entry is declared in, plural and repeated the way a Workflow
# declares its States.
ENTRIES = "entries"

# What an Entry may say, spelled as the flags that describe one on the command
# line are spelled: an operator writing a file and an operator typing a command
# should not have to hold two vocabularies. Every one of them may also appear
# at the top level, where it is the default for every Entry below.
WORKFLOW = "workflow"
TASK = "task"
REPO = "repo"
BRANCH = "branch"
BASE = "base"
AT = "at"
SUBJECT = "subject"
SKIP_GATES = "skip-gates"

KEYS = (WORKFLOW, TASK, REPO, BRANCH, BASE, AT, SUBJECT, SKIP_GATES)


class BatchError(Exception):
    """A batch file that cannot be queued, rejected before any of it is.

    One exception for a file that is not TOML, an Entry that is not a table and
    an Entry the single-Entry path refuses, because all three are the same
    thing to whoever wrote the file: a line to go and fix. Every message names
    the file, and every message about an Entry names its position, the way
    Workflow parsing names a State's.
    """


# Names the batch in every message, so an error always says which file.
Reject = Callable[[str], BatchError]


def load_batch(path: Path, *, repo: Path, library: Path) -> list[Work]:
    """Everything one file describes. `repo` is where an Entry that names no
    repository stands, which is the working directory, as `--repo`'s default
    already is; `library` is where a Workflow given as a bare name resolves
    (ADR 0023)."""
    try:
        text = path.read_text()
    except OSError as error:
        raise BatchError(f"batch {path}: cannot be read ({error.strerror})") from error
    return parse_batch(text, source=str(path), repo=repo, library=library)


def parse_batch(text: str, *, repo: Path, source: str, library: Path) -> list[Work]:
    """One piece of work per Entry, in the order the file writes them.

    Ordering follows the file because file order is what the Predecessor rule
    reads: a batch is usually also a stack.
    """

    def reject(problem: str) -> BatchError:
        return BatchError(f"batch {source}: {problem}")

    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise reject(f"not valid TOML ({error})") from error

    # Everything beside the Entries is a default for all of them, so that five
    # Entries against one repository do not repeat the same Workflow and
    # repository five times. A convenience rather than a concept.
    defaults = {key: value for key, value in document.items() if key != ENTRIES}
    _refuse_a_key_naiad_does_not_read(defaults, reject)

    declared = document.get(ENTRIES)
    if not declared or not isinstance(declared, list):
        raise reject(f"declares no entries; a batch names each one under [[{ENTRIES}]]")

    works = []
    for position, raw in enumerate(declared, start=1):
        if not isinstance(raw, dict):
            raise reject(f"entry {position} is not a table")
        # The Entry's own keys last, so that they override the defaults above.
        works.append(
            _work(
                {**defaults, **raw},
                position=position,
                reject=reject,
                repo=repo,
                library=library,
            )
        )
    return works


def enqueue_batch(
    works: Sequence[Work],
    *,
    queue: Queue,
    runs: RunStore,
    entry_ids: Sequence[str],
    created_at: str,
    source: str,
) -> list[Entry]:
    """Every Entry the file declares, or none of them.

    A file with one bad Entry queues none: a half-failed batch leaves a partial
    Queue with no signal, which is worse than an error. So every Entry is
    prepared before any is written, and each is checked against the Entries the
    same file has already declared as well as against the Queue — two Entries
    in one file claiming one branch is the same silent stacking that two
    already-queued Entries claiming one branch would be.
    """
    held = queue.all()
    prepared: list[Entry] = []
    for position, (work, entry_id) in enumerate(zip(works, entry_ids, strict=True), start=1):
        try:
            prepared.append(
                prepare(
                    work,
                    claimed=[*held, *prepared],
                    runs=runs,
                    entry_id=entry_id,
                    created_at=created_at,
                    remedy=BATCH_ENTRY,
                )
            )
        except REFUSALS as error:
            raise BatchError(f"batch {source}: entry {position}: {error}") from error

    return [queue.add(entry) for entry in prepared]


def _work(
    fields: dict[str, Any], *, position: int, reject: Reject, repo: Path, library: Path
) -> Work:
    def bad(problem: str) -> BatchError:
        return reject(f"entry {position}: {problem}")

    _refuse_a_key_naiad_does_not_read(fields, bad)

    skip_gates = fields.get(SKIP_GATES, False)
    if not isinstance(skip_gates, bool):
        raise bad(f"`{SKIP_GATES}` must be true or false")

    named_repo = _text(fields, REPO, bad)
    return Work(
        workflow_path=_workflow(_required(fields, WORKFLOW, bad), library=library, bad=bad),
        task=_required(fields, TASK, bad),
        target_repo=_path(named_repo) if named_repo else repo,
        # Optional, as `--branch` is: an Entry that names none starts a Run
        # with no Working branch, and the agent at its head derives and
        # declares one there (ADR 0022).
        working_branch=_text(fields, BRANCH, bad),
        pinned_base=_text(fields, BASE, bad),
        start_state=_text(fields, AT, bad),
        subject=_text(fields, SUBJECT, bad),
        skip_gates=skip_gates,
    )


def _refuse_a_key_naiad_does_not_read(fields: dict[str, Any], reject: Reject) -> None:
    """A key nothing reads is a setting its writer believes they made, and a
    misspelt `skip-gates` would park the unattended night the file was written
    to run. Refused rather than ignored, for the reason the whole file is
    refused for one bad Entry."""
    for key in fields:
        if key not in KEYS:
            raise reject(f"`{key}` is not a key naiad reads ({', '.join(KEYS)})")


def _required(fields: dict[str, Any], key: str, bad: Reject) -> str:
    value = _text(fields, key, bad)
    if value is None:
        raise bad(f"names no `{key}`, and nothing above it does either")
    return value


def _text(fields: dict[str, Any], key: str, bad: Reject) -> str | None:
    value = fields.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise bad(f"`{key}` must be a non-empty string")
    return value


def _workflow(value: str, *, library: Path, bad: Reject) -> Path:
    """A path as `_path` reads one, or a bare name resolved through the
    Workflow library (ADR 0023) — refused naming the Entry's position, as
    every other complaint about an Entry is."""
    try:
        return resolve_workflow(value, library=library)
    except (LibraryError, WorkflowError) as error:
        raise bad(str(error)) from error


def _path(value: str) -> Path:
    """Read as a path typed at the command line is: `~` expanded, and anything
    relative taken from the working directory rather than from the file, since
    that is where the operator is standing when they run the command."""
    return Path(value).expanduser().resolve()


__all__ = ["BatchError", "enqueue_batch", "load_batch", "parse_batch"]
