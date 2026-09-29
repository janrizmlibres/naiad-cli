"""Editing a Workflow file without taking it from its author.

A Workflow is configuration a human hand-edits, so every writing verb goes
through here and gets the same guarantees: comments, key order and multi-line
Prompts survive the write; a file the loader would refuse is never left behind;
and a symlinked library entry has its target written, the link untouched
(ADR 0049). Reading for a Run still goes through the standard loader; this is
the only place the TOML writer is used.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from naiad.domain.workflow import Workflow, WorkflowError, load_workflow, parse_workflow
from naiad.runtime.atomic import write_atomically

Edit = Callable[[tomlkit.TOMLDocument], None]


def edit_workflow(path: Path, edit: Edit) -> Workflow:
    """Apply `edit` to the file's document, and return the Workflow it now holds.

    Validated before it is written, so a reader (a Run's tick) never meets a
    file the loader refuses. Reloaded after, through the one load path, and the
    previous bytes restored if that fails: the check ahead of the write is the
    loader too, but the reload is the one the next Run will make.
    """
    target = path.resolve()
    try:
        original = target.read_bytes()
    except OSError as error:
        raise WorkflowError(f"workflow {path}: cannot be read ({error.strerror})") from error

    try:
        document = tomlkit.parse(original.decode())
        edit(document)
        written = tomlkit.dumps(document)
    except (TOMLKitError, UnicodeDecodeError) as error:
        raise WorkflowError(f"workflow {path}: not valid TOML ({error})") from error

    parse_workflow(written, source=str(path))
    write_atomically(target, written.encode())
    try:
        return load_workflow(target)
    except WorkflowError:
        write_atomically(target, original)
        raise


def scaffold_workflow(path: Path, name: str) -> Workflow:
    """A new Workflow file holding `name` and a terminal `done`, and nothing else.

    Refuses a file that is there, and a link that is, whatever it points at:
    the name is taken either way.
    """
    if path.is_symlink() or path.exists():
        raise FileExistsError(str(path))

    document = tomlkit.document()
    document.add("name", name)
    states = tomlkit.aot()
    done = tomlkit.table()
    done.add("name", "done")
    done.add("terminal", True)
    states.append(done)
    document.add("states", states)

    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, tomlkit.dumps(document).encode())
    return load_workflow(path)


__all__ = ["edit_workflow", "scaffold_workflow"]
