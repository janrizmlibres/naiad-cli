"""Which of the two things Naiad tells its operator about.

Service-neutral on purpose. A phone service grades its pushes on a scale of
its own — ntfy runs 1 to 5, another will run something else — and the loop must
not learn any of those scales to say which telling it is making. It says which,
and each adapter maps that onto whatever its service understands.

Two members and no more, because Naiad interrupts a human for exactly two
reasons: the Run needs them, or the Run is over.
"""

from __future__ import annotations

from enum import Enum


class Notification(Enum):
    """What one telling is: a human is needed, or the work is done."""

    NOTIFY = "notify"
    FINISH = "finish"


__all__ = ["Notification"]
