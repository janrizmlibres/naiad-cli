"""The settings document that installs Naiad's hooks.

Pure: a settings document in, a settings document out. Whoever writes the file
decides where it goes — hooks are installed independently of any Run, and never
into the target repository (PRD, 'Storage').

Naiad's entire coupling to Claude Code is a few documented surfaces (ADR 0002),
most of them these hooks: a SessionStart injecting the Protocol, a Stop
reporting that a turn ended, and a UserPromptSubmit confirming that a typed
Prompt reached the Session whole (ADR 0053).
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
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
SUBMITTED_SUBCOMMAND = "submitted"

Settings = dict[str, Any]

# What counts as Naiad's own entry, whichever naiad installed it. Matching the
# subcommand rather than the full path is what lets a naiad that has moved —
# a rebuilt virtualenv, a different machine — replace its predecessor instead
# of running alongside it.
_NAIAD_HOOK_COMMAND = re.compile(rf"(^|/)naiad\s+({PROTOCOL_SUBCOMMAND}|{STOPPED_SUBCOMMAND}|{SUBMITTED_SUBCOMMAND})\b")


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

    # Nor does UserPromptSubmit: every submitted prompt is judged, and one Naiad
    # did not type is let through untouched.
    hooks["UserPromptSubmit"] = _without_ours(hooks.get("UserPromptSubmit", [])) + [
        {"hooks": [_command(naiad, SUBMITTED_SUBCOMMAND)]}
    ]
    return merged


# Every hook `with_naiad_hooks` installs, as (event, matcher, subcommand), for
# `installed_hooks` to look for. Kept in step by hand: a hook added there and not
# here is one the doctor would never miss.
NAIAD_HOOKS = (
    *(("SessionStart", matcher, PROTOCOL_SUBCOMMAND) for matcher in SESSION_START_MATCHERS),
    ("Stop", None, STOPPED_SUBCOMMAND),
    ("UserPromptSubmit", None, SUBMITTED_SUBCOMMAND),
)


@dataclass(frozen=True)
class InstalledHooks:
    """What a settings document holds of Naiad's hooks, judged against the naiad
    that is asking.

    `missing` names each hook not there at all, as `Event` or `Event(matcher)`.
    `elsewhere` holds the commands naming another naiad — a rebuilt virtualenv
    or a moved checkout — which run the wrong program or none.
    """

    missing: tuple[str, ...]
    elsewhere: tuple[str, ...]


def installed_hooks(settings: Settings, *, naiad: str) -> InstalledHooks:
    """The read-only twin of `with_naiad_hooks`: which of its hooks are present,
    and whether they name `naiad`. Judges the document as it stands."""
    hooks = settings.get("hooks")
    hooks = hooks if isinstance(hooks, dict) else {}
    missing: list[str] = []
    elsewhere: list[str] = []
    for event, matcher, subcommand in NAIAD_HOOKS:
        commands = [
            str(hook.get("command", ""))
            for entry in _dicts(hooks.get(event))
            if entry.get("matcher") == matcher
            for hook in _dicts(entry.get("hooks"))
            if _is_ours(hook) and str(hook.get("command", "")).split()[-1:] == [subcommand]
        ]
        if not commands:
            missing.append(event if matcher is None else f"{event}({matcher})")
        elsewhere += [
            command
            for command in commands
            if command != f"{naiad} {subcommand}" and command not in elsewhere
        ]
    return InstalledHooks(missing=tuple(missing), elsewhere=tuple(elsewhere))


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


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


__all__ = [
    "InstalledHooks",
    "NAIAD_HOOKS",
    "SESSION_START_MATCHERS",
    "Settings",
    "installed_hooks",
    "with_naiad_hooks",
]
