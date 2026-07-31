"""Writing a file so that a concurrent reader never sees half of it.

Naiad's files are read by one process while written by another — a tick reads
the State file while the agent's announce command writes it. Writing in place
would let a read land between truncation and content, so the content is written
elsewhere and moved into position in one step.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_atomically(path: Path, text: str) -> None:
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w") as file:
            file.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


__all__ = ["write_atomically"]
