"""What a Join State is decided from and what its Prompt names.

A Join State holds its Prompt while the Run's Children are working. Two facts
about them are enough to decide it: how many are unfinished, and which have
finished without the Run having been told. What makes a Child finished, and
where its Subject and branch are read from, is the runtime's to gather; here
is only the shape it is handed in, and the one line each Child is told as.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

# How a Child's Run ended. Completed when it reached a Terminal State, and
# cancelled when the operator called it off, or removed its Entry before it
# ever started.
Outcome = Literal["completed", "cancelled"]


@dataclass(frozen=True)
class FinishedChild:
    """One finished Child as its Parent is told of it.

    The working tree is carried beside the branch so that the Parent can clean
    up after it without deriving a path. Subject and branch are None where none
    was given or declared.
    """

    entry_id: str
    subject: str | None
    branch: str | None
    worktree: str
    outcome: Outcome


@dataclass(frozen=True)
class Join:
    """The Join signals of one Announcement.

    unfinished is how many of the Run's Children have not finished; a parked
    Child is one of them. named is the finished Children this Announcement's
    Prompt names. recorded says that set was already written down against
    this Announcement, so that a redelivery names what the first delivery
    named rather than reading afresh.

    The default is a Run with no Children, which a Join State delivers to at
    once.
    """

    unfinished: int = 0
    named: tuple[FinishedChild, ...] = ()
    recorded: bool = False

    @property
    def released(self) -> bool:
        """Whether a Join State's Prompt may go out: a set is already recorded,
        a finished Child is untold, or no Child is left to wait on."""
        return self.recorded or bool(self.named) or self.unfinished == 0


def render_children(children: Sequence[FinishedChild]) -> str:
    """The `{children}` slot: one line per Child, nothing when none is named."""
    return "\n".join(
        f"- {child.subject or '-'}: {child.outcome}, branch {child.branch or '-'}, "
        f"working tree {child.worktree}"
        for child in children
    )


__all__ = ["FinishedChild", "Join", "Outcome", "render_children"]
