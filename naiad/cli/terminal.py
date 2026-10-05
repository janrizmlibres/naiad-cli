"""What fits on the operator's screen.

Lines Naiad prints for a person are cut or wrapped to the width of the terminal
they are printed to, and to a conventional eighty where there is none — output
piped into a file or another command has no width of its own to honour.
"""

from __future__ import annotations

import os
import re
import sys

PIPED_WIDTH = 80

# A clause ends at a comma, semicolon, colon or full stop followed by a space
# (so `v1.2` and `:3939` are not cut), or at a dash.
_CLAUSE_END = re.compile(r"\s*(?:[,;:.](?=\s|$)|—)")


def terminal_width() -> int:
    """The columns of the terminal being printed to. COLUMNS wins, as it does
    for every other tool that reads it, so an operator can say otherwise."""
    declared = os.environ.get("COLUMNS", "")
    if declared.isdigit() and int(declared) > 0:
        return int(declared)
    try:
        return os.get_terminal_size(sys.stdout.fileno()).columns
    except (OSError, ValueError, AttributeError):
        # OSError for a stdout that is not a terminal; the others for a stdout
        # replaced by something with no file descriptor at all.
        return PIPED_WIDTH


def first_clause(text: str) -> str:
    """The text up to its first clause boundary. What an operator watching a
    stream needs of an answer is which way it went, not why."""
    return _CLAUSE_END.split(text, maxsplit=1)[0]


__all__ = ["PIPED_WIDTH", "first_clause", "terminal_width"]
