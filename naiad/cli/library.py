"""The Workflow library: bare names for Workflow files (ADR 0023).

One machine-wide directory of Workflow files addressable by name, where a name
is the file's stem. Which of the two an argument is, its shape alone decides —
a path separator or a `.toml` suffix makes it a path, anything else a name —
never what happens to exist on disk, so the same string means the same thing
in every directory.

A name resolves to a path here, at the entrance, and nowhere else: the Entry
stores what came out exactly as it stores a path typed explicitly, and
everything downstream is untouched.

The library is the operator's store (ADR 0049): regular files they own, or a
hand-made symlink to a Workflow maintained in a repository. This module both
reads it and, on request, writes the starter into it.
"""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path

from naiad.domain.workflow import Workflow, WorkflowError, load_workflow
from naiad.runtime.atomic import write_atomically
from naiad.runtime.queue import Queue
from naiad.runtime.run import RunStore
from naiad.runtime.workflow_file import (
    copy_workflow,
    edit_workflow,
    scaffold_workflow,
    set_name,
)
from naiad.runtime.workflow_use import addressing

STARTER_FILE = "starter.toml"


class LibraryError(Exception):
    """A name the library cannot answer, refused where it was typed.

    Carries the library's actual contents, because the refusal is the listing
    command this feature declined to add: it names what the library does hold,
    or — empty or missing — where to put files so it holds something.
    """


def resolve_workflow(argument: str, *, library: Path) -> Path:
    """The file a Workflow argument names, resolved absolute."""
    if not _is_name(argument):
        return Path(argument).expanduser().resolve()
    path = library / f"{argument}.toml"
    if path.is_symlink() and not path.exists():
        # The library holds the name, so 'no workflow named' would send the
        # operator looking for a file they made: what is wrong is where it leads.
        raise LibraryError(
            f"workflow '{argument}' is a broken link: {path} points at "
            f"{os.readlink(path)}, which does not exist"
        )
    if not path.is_file():
        raise LibraryError(_unknown(argument, library))
    declared = load_workflow(path).name
    if declared != argument:
        # In the library the filename has become an address: a file reachable
        # as one name that calls itself another in every log is misfiled.
        raise LibraryError(
            f"workflow '{argument}' is misfiled: {path} declares name "
            f"'{declared}'; a library file must declare its own stem"
        )
    return path


def workflows_in(library: Path) -> tuple[Path, ...]:
    """Every Workflow file the library holds, by name.

    A listing rather than a resolution, and the one place both readers share:
    the refusal below names what the library holds, and `naiad states` prints
    what each of them declares (ADR 0032). Sorted by stem, because the stem is
    the address and a directory's own order is not one an operator can predict.

    Files only, so nothing is claimed about a directory that happens to end in
    the suffix; a library that does not exist holds nothing, which is the same
    answer as an empty one and needs no separate telling.
    """
    if not library.is_dir():
        return ()
    return tuple(sorted((file for file in library.glob("*.toml") if file.is_file()), key=_stem))


def install_starter(*, library: Path, force: bool = False) -> Path:
    """Copy the shipped starter into the library as a regular file (ADR 0049).

    Nothing there: it is written. A file byte-identical to the shipped starter
    is rewritten, so an older copy is refreshed and nothing is lost. Anything
    else is the operator's — an edited copy, or a symlink they made for a file
    maintained elsewhere — and is refused in one sentence naming `force`,
    because a re-run done without thinking must not destroy their work.

    `force` replaces whatever is there, a symlink included: the link is removed
    rather than written through, so the file behind it is not edited.
    """
    entry = Path(library) / STARTER_FILE
    shipped = files("naiad.workflows").joinpath(STARTER_FILE).read_bytes()
    if not force and _is_theirs(entry, shipped):
        raise ValueError(
            f"{STARTER_FILE} differs from the shipped starter; pass --force or move it aside"
        )

    entry.parent.mkdir(parents=True, exist_ok=True)
    if entry.is_symlink():
        entry.unlink()
    write_atomically(entry, shipped)
    return entry


def new_workflow(
    name: str, *, library: Path, source: str | None = None
) -> tuple[Path, Workflow]:
    """Create a Workflow of this name in the library, refusing one that is
    there: scaffolded, or a copy of `source` (a name or a path, by shape) with
    its `name` rewritten to the new stem. Only a bare name is taken for the new
    one: a path would put the file somewhere the name does not address."""
    _require_a_name(name)
    path = library / f"{name}.toml"
    original = None if source is None else resolve_workflow(source, library=library)
    try:
        if original is None:
            return path, scaffold_workflow(path, name)
        return path, copy_workflow(original, path, name)
    except FileExistsError:
        raise LibraryError(f"workflow '{name}' already exists: {path}") from None


def library_entries(library: Path) -> list[tuple[str, str | None]]:
    """Every entry the library holds as (name, problem), the problem None for
    one a Run could start from.

    A listing of what is there rather than of what loads: a link whose target
    is gone is still an entry, and the operator needs it named as broken, not
    left out as though they had never made it.
    """
    if not library.is_dir():
        return []
    held = sorted(
        (file for file in library.glob("*.toml") if file.is_file() or file.is_symlink()),
        key=_stem,
    )
    return [(file.stem, _problem_with(file)) for file in held]


def remove_workflow(argument: str, *, library: Path, queue: Queue, runs: RunStore) -> Path:
    """Delete the library entry named, or the file at the path given.

    A link is removed and its target left, because the file behind it is the
    operator's own and may live in a repository.
    """
    path = _held(argument, library)
    _refuse_while_addressed("remove", argument, path, queue=queue, runs=runs)
    path.unlink()
    return path


def rename_workflow(
    argument: str, new: str, *, library: Path, queue: Queue, runs: RunStore
) -> Path:
    """Move the file and its `name` key together, beside where it was.

    The key is written first, through the editor that validates and can undo
    it, and the move follows; a move that fails puts the key back, so the two
    never part.
    """
    _require_a_name(new)
    path = _held(argument, library)
    destination = path.with_name(f"{new}.toml")
    if destination.is_symlink() or destination.exists():
        raise LibraryError(f"workflow '{new}' already exists: {destination}")
    _refuse_while_addressed("rename", argument, path, queue=queue, runs=runs)

    previous = load_workflow(path.resolve()).name
    edit_workflow(path, lambda document: set_name(document, new))
    try:
        path.rename(destination)
    except OSError as error:
        edit_workflow(path, lambda document: set_name(document, previous))
        raise LibraryError(f"cannot move {path} to {destination} ({error.strerror})") from error
    return destination


def _require_a_name(name: str) -> None:
    # An empty name has the shape of a name, and would be the file `.toml`.
    if not name or not _is_name(name):
        raise LibraryError(
            f"'{name}' is not a workflow name: give a bare name, "
            "with no '/' and no '.toml' suffix"
        )


def _held(argument: str, library: Path) -> Path:
    """The file a verb that changes the library acts on, as it is spelt there:
    not resolved, so a link is the thing acted on and not what it points at."""
    if not _is_name(argument):
        path = Path(argument).expanduser()
        if not path.is_file():
            raise LibraryError(f"no workflow file at {path}")
        return path
    path = library / f"{argument}.toml"
    if not path.is_file() and not path.is_symlink():
        raise LibraryError(_unknown(argument, library))
    return path


def _refuse_while_addressed(
    verb: str, argument: str, path: Path, *, queue: Queue, runs: RunStore
) -> None:
    users = addressing(path, queue=queue, runs=runs)
    if users:
        raise LibraryError(
            f"cannot {verb} '{argument}': {', '.join(users)} "
            f"{'addresses' if len(users) == 1 else 'address'} it; "
            "end each with `naiad queue rm <entry id>` first"
        )


def _problem_with(file: Path) -> str | None:
    if file.is_symlink() and not file.exists():
        return f"broken link: points at {os.readlink(file)}, which does not exist"
    try:
        declared = load_workflow(file).name
    except WorkflowError as error:
        return str(error)
    if declared != file.stem:
        return f"misfiled: declares name '{declared}'; a library file must declare its own stem"
    return None


def _is_theirs(entry: Path, shipped: bytes) -> bool:
    if entry.is_symlink():
        return True
    return entry.exists() and entry.read_bytes() != shipped


def _stem(file: Path) -> str:
    return file.stem


def empty_library_message(library: Path) -> str:
    """What an empty library says, whichever question reached it: a name that
    missed, or a listing with nothing to list (ADR 0032).

    One sentence rather than one per caller, because both answer the same
    fact — there is nothing here — and the remedy for it is the same.
    """
    return (
        f"the library at {library} holds no workflows; "
        "drop a Workflow file there to run it by name"
    )


def _unknown(name: str, library: Path) -> str:
    held = [file.stem for file in workflows_in(library)]
    if not held:
        return f"no workflow named '{name}': {empty_library_message(library)}"
    return f"no workflow named '{name}' in {library} — the library holds: {', '.join(held)}"


def _is_name(argument: str) -> bool:
    """Shape alone: a separator or the suffix makes it a path."""
    return "/" not in argument and not argument.endswith(".toml")


__all__ = [
    "LibraryError",
    "empty_library_message",
    "install_starter",
    "library_entries",
    "new_workflow",
    "remove_workflow",
    "rename_workflow",
    "resolve_workflow",
    "workflows_in",
]
