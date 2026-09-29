"""The agent's fourth side of the Protocol: relaying the human's pause as a Hold.

A command rather than a convention for the same reason a Wait is:
Naiad cannot see the human type "pause" into the session, so the agent is the
only possible relay — and a pause Naiad was not told about is nudged into the
very interruption the human ordered against.

No duration and no budget, deliberately. A Hold waits on a person, and what
bounds it is visibility rather than a clock: declaring one notifies the
operator, so a Hold nobody asked for is seen rather than timed out.
"""

from __future__ import annotations

from naiad.runtime.announcements import Announcements
from naiad.runtime.records import Holds
from naiad.runtime.run import Run


class HoldError(Exception):
    """A Hold the agent must see and correct."""


def declare_hold(reason: str, *, run: Run) -> None:
    """Declare a Hold against the Run's current Announcement.

    The reason is required for the same cause a Wait's is: the notification
    and the Run log are read by an operator who must see what the Hold was
    for — and the agent relaying the human's words is what later tells an
    honest Hold from a confused one.
    """
    if not reason.strip():
        raise HoldError(
            "a hold needs to say why the human asked for it; "
            'declare it as: naiad hold "<why>"'
        )
    Holds(run.root).record(Announcements(run.root).latest(), reason=reason)


__all__ = ["HoldError", "declare_hold"]
