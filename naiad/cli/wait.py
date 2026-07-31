"""The agent's third side of the Protocol: declaring that its silence is a Wait.

A command rather than a convention because Naiad reads no Claude Code
internals (ADR 0002): a wait Naiad was not told about is indistinguishable
from a forgotten announcement, and is Nudged into the very interruption it
meant to avoid (ADR 0021).

The refusals leave the agent a move. A Wait past the spent budget is refused
toward announcing or asking, because a wait-looping agent stalling its Lane
with no human told is exactly what the budget exists to stop.
"""

from __future__ import annotations

from naiad.runtime.announcements import Announcements
from naiad.runtime.records import Waits
from naiad.runtime.run import Run


class WaitError(Exception):
    """A Wait the agent must see and correct."""


def declare_wait(
    reason: str, *, run: Run, now: float, seconds: float | None = None
) -> tuple[float, float]:
    """Declare a Wait against the Run's current Announcement, returning what
    it was granted and what remains of the budget.

    The reason is required for the same cause a Question's options are: the
    operator reading the Run log — or the Nudge that follows an expiry — must
    see what the agent was waiting on, and Naiad cannot see it unless told.
    """
    if not reason.strip():
        raise WaitError(
            "a wait needs to say what it is waiting on; "
            'declare it as: naiad wait "<what for>" --seconds <n>'
        )
    if seconds is not None and seconds <= 0:
        raise WaitError("a wait needs a positive number of seconds, or no --seconds for the default")

    announcement = Announcements(run.root).latest()
    waits = Waits(run.root)
    # Under a second left is spent in all but arithmetic: a sub-second Wait
    # would be granted, expire before the agent's turn ends, and read back as
    # "waiting on X for 0s" — a refusal the agent can act on is worth more.
    if waits.remaining(announcement, now=now) < 1.0:
        raise WaitError(
            "this announcement's wait budget is spent, so no further wait can be "
            "declared. If the phase is finished, announce with `naiad state <name>`; "
            "if you are stuck on a decision you cannot make alone, ask with "
            '`naiad ask "<question>" --option "<one>" --option "<another>"`'
        )
    granted = waits.record(announcement, reason=reason, now=now, seconds=seconds)
    return granted, waits.remaining(announcement, now=now)


__all__ = ["WaitError", "declare_wait"]
