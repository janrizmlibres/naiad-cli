"""Which naiad this is.

Asked by two callers that must agree: the hook installer, writing the command
Claude Code will run, and the Protocol, naming the command the agent must type.
Neither can assume a bare `naiad` resolves — a hook runs with the operator's
environment and a session's PATH is whatever tmux inherited, so the absolute
path of the naiad actually driving the Run is the only honest answer.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def naiad_command() -> str:
    candidate = sys.argv[0]
    resolved = Path(candidate)
    if resolved.name and not resolved.is_absolute():
        found = shutil.which(candidate)
        if found:
            resolved = Path(found)
    return str(resolved.resolve())


__all__ = ["naiad_command"]
