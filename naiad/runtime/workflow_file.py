"""Editing a Workflow file without taking it from its author.

A Workflow is configuration a human hand-edits, so every writing verb goes
through here and gets the same guarantees: comments, key order and multi-line
Prompts survive the write; a file the loader would refuse is never left behind;
and a symlinked library entry has its target written, the link untouched
(ADR 0049). Reading for a Run still goes through the standard loader; this
module and naiad.runtime.state_file, which shapes what an edit does to a State,
are the only places the TOML writer is used.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Any

import tomlkit
import tomlkit.items
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
        mode = stat.S_IMODE(target.stat().st_mode)
    except OSError as error:
        raise WorkflowError(f"workflow {path}: cannot be read ({error.strerror})") from error

    try:
        document = tomlkit.parse(original.decode())
        edit(document)
        written = tomlkit.dumps(document)
    except (TOMLKitError, UnicodeDecodeError) as error:
        raise WorkflowError(f"workflow {path}: not valid TOML ({error})") from error

    parse_workflow(written, source=str(path))
    write_atomically(target, written.encode(), mode=mode)
    try:
        return load_workflow(target)
    except WorkflowError:
        write_atomically(target, original, mode=mode)
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
    write_atomically(path, tomlkit.dumps(document).encode(), mode=_default_mode())
    return load_workflow(path)


def copy_workflow(source: Path, path: Path, name: str) -> Workflow:
    """A new Workflow file that is `source`'s bytes with only `name` rewritten.

    Copied through the editor so comments and Prompts arrive as they were
    written; a source the loader refuses is not copied, and a file that is
    there is not replaced.
    """
    if path.is_symlink() or path.exists():
        raise FileExistsError(str(path))

    original = source.resolve()
    try:
        text = original.read_text()
    except (OSError, UnicodeDecodeError) as error:
        raise WorkflowError(f"workflow {source}: cannot be read ({error})") from error
    load_workflow(original)

    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, text.encode(), mode=_default_mode())
    try:
        return edit_workflow(path, lambda document: set_name(document, name))
    except WorkflowError:
        path.unlink(missing_ok=True)
        raise


def set_name(document: tomlkit.TOMLDocument, name: str) -> None:
    """Rewrite the file's `name` where it stands, its line and comments kept."""
    document["name"] = name


def set_file_key(document: tomlkit.TOMLDocument, key: str, value: str) -> None:
    """Write a file-level key, dotted for one in `[answerer]`.

    A new key lands beside `name` and the other file-level keys: appended, it
    would sit after the States, and a reader would take it for a State's.
    """
    table, leaf = _home_of(document, key, create=True)
    if table is document and leaf not in table:
        _insert_file_key(document, leaf, value)
    else:
        table[leaf] = value


def unset_file_key(document: tomlkit.TOMLDocument, key: str) -> bool:
    """Delete a file-level key. An `[answerer]` table left empty stays: its
    presence is what gives the file's Questions to the Answerer (ADR 0050), and
    removing the last key must not switch that off.

    Returns whether there was a key to delete, so the caller can say which."""
    table, leaf = _home_of(document, key, create=False)
    if leaf not in table:
        return False
    del table[leaf]
    return True


def _home_of(
    document: tomlkit.TOMLDocument, key: str, *, create: bool
) -> tuple[MutableMapping[str, Any], str]:
    if "." not in key:
        return document, key
    owner, leaf = key.split(".", 1)
    if owner not in document:
        if not create:
            return {}, leaf
        document[owner] = tomlkit.table()
    return document[owner], leaf


def _insert_file_key(document: tomlkit.TOMLDocument, key: str, value: str) -> None:
    """After the last file-level key already there, which is `name` at the least
    (a file without one does not load, and this is only reached for one that does).

    Placed through tomlkit's `_insert_after`, the only call that puts a key
    mid-document with the comments around it intact; tests/test_workflow_file.py
    holds the placement, so an upgrade that changes it fails there."""
    scalars = [
        existing
        for existing, item in document.items()
        if not isinstance(item, (tomlkit.items.Table, tomlkit.items.AoT))
    ]
    document._insert_after(scalars[-1], key, value)


def _default_mode() -> int:
    """What a file the author made by hand would get: readable as their umask allows."""
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


__all__ = [
    "copy_workflow",
    "edit_workflow",
    "scaffold_workflow",
    "set_file_key",
    "set_name",
    "unset_file_key",
]
