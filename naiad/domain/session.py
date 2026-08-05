"""What a Run's session is, as data.

The rules about a session — that it runs in bypass permissions mode, that its
Claude session id is pinned rather than discovered, that it is named after its
Run, and what it is first asked to do — are decided here, over plain data. The
adapter turns this into a command and holds no rules of its own (ADR 0004).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

BYPASS_PERMISSIONS = "bypassPermissions"
SESSION_PREFIX = "naiad-"


def session_name(run_id: str) -> str:
    return f"{SESSION_PREFIX}{run_id}"


@dataclass(frozen=True)
class SessionSpec:
    """A session to be opened for a Run.

    initial_prompt is the first State's Prompt, carried into the session as it
    starts rather than typed in afterwards. Typing into a session that has only
    just been created means knowing when it is ready to be typed into, and the
    only honest way to know that is a supported signal — which Naiad does not
    have until the hooks arrive. Handing the Prompt over at spawn needs no such
    signal.

    model and effort are the first State's, riding at launch as flags for the
    same reason the first Prompt does: a Switch precedes Prompt delivery, and at
    spawn delivery happens on the command line (ADR 0026). Kickoff is therefore
    the one entrance that spends no Tick on them and cannot lose one — the flags
    are read as the process starts, where a session in mid-conversation drops
    what arrives while it is handling a slash command (ADR 0038).

    None when the delivering State has neither key — a Gate State first among
    them, which delivers nothing and so carries nothing.
    """

    name: str
    cwd: Path
    claude_session_id: str
    initial_prompt: str | None = None
    model: str | None = None
    effort: str | None = None
    permission_mode: str = BYPASS_PERMISSIONS
    environ: Mapping[str, str] = field(default_factory=dict)
