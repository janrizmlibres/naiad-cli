"""An Entry: a Run that does not exist yet.

Plain data, in the domain layer beside the Announcement, because the Queue's
rules are decided over Entries and those rules are pure (ADR 0004). The Queue
that keeps them on disk lives in naiad.runtime.queue, which is the same split
an Announcement and the Announcements that hold it already make.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    """One piece of work waiting to be run.

    Carries everything kickoff would otherwise be told, and one field recording
    what became of it. No status (ADR 0013) and no position: the id is a
    sortable timestamp, so sorting by id *is* Queue order.

    Frozen, because everything it carries was decided when it was made. The one
    thing that changes about an Entry — which Run it became — is recorded by
    writing the Entry again rather than by mutating it in place, so that what is
    on disk and what is in hand never differ.
    """

    id: str
    workflow_path: Path
    task: str
    target_repo: Path
    # Required of every Entry and refused before one exists, because Naiad
    # derives no branch name from a repository's conventions (ADR 0015).
    working_branch: str
    created_at: str
    # Optional and opaque: recorded and passed on without being read.
    pinned_base: str | None = None
    start_state: str | None = None
    subject: str | None = None
    skip_gates: bool = False
    # What became of it: absent until the Entry starts, and the only field that
    # says anything about the Run. Everything else is asked of the Run itself.
    run_id: str | None = None


__all__ = ["Entry"]
