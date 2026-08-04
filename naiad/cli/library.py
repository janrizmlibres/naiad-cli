"""The Workflow library: bare names for Workflow files (ADR 0023).

One machine-wide directory of Workflow files addressable by name, where a name
is the file's stem. Which of the two an argument is, its shape alone decides —
a path separator or a `.toml` suffix makes it a path, anything else a name —
never what happens to exist on disk, so the same string means the same thing
in every directory.

A name resolves to a path here, at the entrance, and nowhere else: the Entry
stores what came out exactly as it stores a path typed explicitly, and
everything downstream is untouched.

What the library holds is addresses rather than content (ADR 0037), which is
why this module both reads and writes it: an entry is a symlink to the file its
author maintains, and install makes the one for the Workflow that ships.
"""

from __future__ import annotations

from pathlib import Path

from naiad.domain.workflow import load_workflow

# Where the shipped Workflow files are: beside the package, in the checkout.
# pyproject packages `naiad*` alone, so a distribution carries none of them and
# this directory is absent there rather than empty (ADR 0037).
SHIPPED_WORKFLOWS = Path(__file__).resolve().parents[2] / "workflows"


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


def shipped_workflows(root: Path | None = None) -> tuple[Path, ...]:
    """The Workflow files Naiad ships, as they stand in the checkout.

    Empty where no such directory exists, which is every installed
    distribution: `workflows/` sits outside the package, so a wheel carries no
    Workflow to link and the caller says so rather than failing (ADR 0037).
    """
    return workflows_in(SHIPPED_WORKFLOWS if root is None else root)


def link_shipped_workflows(*, library: Path, shipped: Path | None = None) -> tuple[Path, ...]:
    """Address each shipped Workflow from the library, and say which (ADR 0037).

    Idempotent, because installing is something an operator will do again
    without thinking, and re-running it is how a library that drifted is
    repaired: a link is replaced whatever it points at, since an address is
    cheap to rewrite and a wrong one is the fault this exists to prevent.

    A regular file of the same name is refused rather than replaced. It is a
    copy, which is the thing that fell four days behind the Workflow it copied
    — and deleting what a human put there, to install what they can reinstall
    at any time, trades their work for ours. The refusal is also the report
    that was missing while the copy rotted.

    Every entry is refused before any is written, so a refusal leaves the
    library as it found it. The caller reports what landed, and a call that
    wrote some of its entries and returned none of them would be read against
    a library the operator cannot see.
    """
    files = shipped_workflows(shipped)
    if not files:
        return ()

    entries = [Path(library) / file.name for file in files]
    for entry in entries:
        _refuse_a_copy(entry)

    Path(library).mkdir(parents=True, exist_ok=True)
    for entry, file in zip(entries, files):
        if entry.is_symlink():
            entry.unlink()
        entry.symlink_to(file)
    return tuple(entries)


def _refuse_a_copy(entry: Path) -> None:
    if entry.is_symlink() or not entry.exists():
        return
    raise ValueError(
        f"{entry} is a file rather than a link to the workflow it names; "
        "a copy can fall behind the file it copies, so naiad will not replace "
        "it. Move it aside to have naiad address the shipped workflow instead."
    )


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
    "SHIPPED_WORKFLOWS",
    "LibraryError",
    "empty_library_message",
    "link_shipped_workflows",
    "resolve_workflow",
    "shipped_workflows",
    "workflows_in",
]
