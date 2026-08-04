"""The Workflow library: bare names for Workflow files (ADR 0023).

One machine-wide directory of Workflow files addressable by name, where a name
is the file's stem. Which of the two an argument is, its shape alone decides —
a path separator or a `.toml` suffix makes it a path, anything else a name —
never what happens to exist on disk, so the same string means the same thing
in every directory.

A name resolves to a path here, at the entrance, and nowhere else: the Entry
stores what came out exactly as it stores a path typed explicitly, and
everything downstream is untouched.
"""

from __future__ import annotations

from pathlib import Path

from naiad.domain.workflow import load_workflow


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
