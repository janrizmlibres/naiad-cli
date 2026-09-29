"""Which of the three things Naiad tells its operator about.

Service-neutral on purpose. A phone service grades its pushes on a scale of
its own — ntfy runs 1 to 5, another will run something else — and the loop must
not learn any of those scales to say which telling it is making. It says which,
and each adapter maps that onto whatever its service understands.

Three members and no more: two reasons to interrupt a human, and one to inform
them. The Run needs them, or the Run is over; or a State the Workflow marked
has been entered and nobody is needed.
"""

from __future__ import annotations

from enum import Enum


class Notification(Enum):
    """What one telling is: a human is needed, the work is done, or a State the
    Workflow marked was entered."""

    NOTIFY = "notify"
    FINISH = "finish"
    REPORT = "report"


def render_answered(count: int, *, reference: str) -> str:
    """The line that tells the operator the Answerer answered for them, and
    which verb reads what it said. reference is what that verb is given: the
    Entry, or the Run where the Run has none."""
    return f"{count} answered by the Answerer — naiad queue answers {reference}"


__all__ = ["Notification", "render_answered"]
