"""The settings document that installs Naiad's hooks.

Pure: a settings document in, a settings document out. Whoever writes the file
decides where it goes — hooks are installed independently of any Run, and never
into the target repository (PRD, 'Storage').

Naiad's entire coupling to Claude Code is three documented surfaces (ADR 0002),
two of which are these hooks: a SessionStart injecting the Protocol, and a Stop
reporting that a turn ended.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

# The three moments a context is created or destroyed. `resume` is deliberately
# absent: a resumed session is handed its old context back, Protocol included.
#
# Each is its own entry rather than one alternation. Alternation is documented
# for tool-name matchers, not for SessionStart sources, and Naiad depends only
# on documented surfaces.
SESSION_START_MATCHERS = ("startup", "clear", "compact")

PROTOCOL_SUBCOMMAND = "protocol"
STOPPED_SUBCOMMAND = "stopped"

Settings = dict[str, Any]

# What counts as Naiad's own entry, whichever naiad installed it. Matching the
# subcommand rather than the full path is what lets a naiad that has moved —
# a rebuilt virtualenv, a different machine — replace its predecessor instead
# of running alongside it.
_NAIAD_HOOK_COMMAND = re.compile(rf"(^|/)naiad\s+({PROTOCOL_SUBCOMMAND}|{STOPPED_SUBCOMMAND})\b")


def with_naiad_hooks(settings: Settings, *, naiad: str) -> Settings:
    """The operator's settings with Naiad's hooks installed, replacing any
    Naiad installed earlier and leaving everything else exactly as it was.

    Idempotent, because installing is something an operator will do again
    without thinking — and two naiads answering one hook would deliver two
    Protocols and record every turn twice.
    """
    merged = deepcopy(settings)
    hooks = merged.setdefault("hooks", {})

    session_start = _without_ours(hooks.get("SessionStart", []))
    hooks["SessionStart"] = session_start + [
        {"matcher": matcher, "hooks": [_command(naiad, PROTOCOL_SUBCOMMAND)]}
        for matcher in SESSION_START_MATCHERS
    ]

    # Stop takes no matcher: it fires whenever the agent finishes a turn.
    hooks["Stop"] = _without_ours(hooks.get("Stop", [])) + [
        {"hooks": [_command(naiad, STOPPED_SUBCOMMAND)]}
    ]
    return merged


def _command(naiad: str, subcommand: str) -> dict[str, str]:
    return {"type": "command", "command": f"{naiad} {subcommand}"}


def _without_ours(entries: list[Any]) -> list[Any]:
    """Entries belonging to somebody else. An entry mixing their hooks with
    ours keeps theirs, so uninstalling Naiad never removes another tool's."""
    kept = []
    for entry in entries:
        theirs = [hook for hook in entry.get("hooks", []) if not _is_ours(hook)]
        if theirs:
            kept.append({**entry, "hooks": theirs})
    return kept


def _is_ours(hook: dict[str, Any]) -> bool:
    return bool(_NAIAD_HOOK_COMMAND.search(str(hook.get("command", ""))))


__all__ = ["SESSION_START_MATCHERS", "Settings", "with_naiad_hooks"]
