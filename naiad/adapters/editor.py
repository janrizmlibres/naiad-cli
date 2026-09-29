"""The author's own editor, opened on a file of text.

A Prompt is prose, and writing prose in a terminal is what `$VISUAL` and
`$EDITOR` are for. Naiad hands the editor a file and reads back what it left,
and has no opinion on which editor: none is assumed when none is set, since a
guess (`vi`) is the trap the environment variables exist to avoid.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path


class EditorError(Exception):
    """An editor that could not be opened, or that did not finish."""


def edit_text(initial: str, *, environ: Mapping[str, str] = os.environ) -> str:
    """Open `$VISUAL`, else `$EDITOR`, on a file holding `initial`, and return
    what the file holds once the editor closes."""
    editor = (environ.get("VISUAL") or "").strip() or (environ.get("EDITOR") or "").strip()
    if not editor:
        raise EditorError(
            "no editor to write the Prompt in: set $VISUAL or $EDITOR, "
            "or pass --from FILE (--from - reads standard input)"
        )

    # A .md suffix so an editor that picks its mode by extension treats a
    # Prompt as the prose it is.
    handle, name = tempfile.mkstemp(prefix="naiad-prompt-", suffix=".md")
    path = Path(name)
    try:
        with os.fdopen(handle, "w") as file:
            file.write(initial)
        try:
            finished = subprocess.run([*shlex.split(editor), name], check=False)
        except (OSError, ValueError) as error:
            reason = getattr(error, "strerror", None) or error
            raise EditorError(f"cannot run the editor '{editor}' ({reason})") from error
        if finished.returncode != 0:
            raise EditorError(f"the editor '{editor}' exited with status {finished.returncode}")
        return path.read_text()
    finally:
        path.unlink(missing_ok=True)


__all__ = ["EditorError", "edit_text"]
