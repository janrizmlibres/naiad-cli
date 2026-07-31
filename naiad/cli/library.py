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


def _unknown(name: str, library: Path) -> str:
    held = sorted(file.stem for file in library.glob("*.toml"))
    if not held:
        return (
            f"no workflow named '{name}': the library at {library} holds no "
            "workflows; drop a Workflow file there to run it by name"
        )
    return f"no workflow named '{name}' in {library} — the library holds: {', '.join(held)}"


def _is_name(argument: str) -> bool:
    """Shape alone: a separator or the suffix makes it a path."""
    return "/" not in argument and not argument.endswith(".toml")
