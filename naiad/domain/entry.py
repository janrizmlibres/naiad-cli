"""An Entry: a Run that does not exist yet.

Plain data, in the domain layer beside the Announcement, because the Queue's
rules are decided over Entries and those rules are pure. The Queue
that keeps them on disk lives in naiad.runtime.queue, which is the same split
an Announcement and the Announcements that hold it already make.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from naiad.domain.settings import StateSetting


@dataclass(frozen=True)
class Attachment:
    """The live Session an Adoption's Run joins instead of one being opened for
    it.

    The pane is the whole of what delivery needs and is why an Adoption is tmux
    only: a session Naiad cannot type into is one it cannot drive. The Claude
    session id is a second key for the resolution seam and optional in value,
    because it may be unknowable from inside the tool call that adopts —
    whichever keys can be gathered are recorded, and the pane is the reliable
    one.
    """

    tmux_pane: str
    claude_session_id: str | None = None


@dataclass(frozen=True)
class Entry:
    """One piece of work waiting to be run.

    Carries everything kickoff would otherwise be told, and one field recording
    what became of it. No status and no position: the id is a
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
    # Given verbatim or absent, never invented: Naiad derives no branch name
    # from a repository's conventions. Absent means the agent at the
    # head of the Run derives one there and declares it on the Run, so the
    # Entry's own record stays as the work was described.
    working_branch: str | None
    created_at: str
    # Optional and opaque: recorded and passed on without being read.
    pinned_base: str | None = None
    start_state: str | None = None
    subject: str | None = None
    skip_gates: bool = False
    # Which Session this Entry's Run attaches to, absent for the ordinary Entry
    # whose Run is spawned one of its own. Nothing else about the Entry changes
    # for being marked: it takes its place in the Lane, is claim-checked, listed
    # and removed exactly as any other.
    attachment: Attachment | None = None
    # The Model and Effort it names for States of its Workflow, each beating
    # what the Workflow file declares for that State. Empty for work that
    # leaves every setting to the Workflow.
    settings: tuple[StateSetting, ...] = ()
    # The Run that spawned it, when it is a Child, and absent otherwise. Nothing
    # about where it runs changes for having one: its working tree is its own,
    # so it is a Lane of its own and is claim-checked, listed and removed like
    # any other Entry.
    parent: str | None = None
    # How many of its Children may be live at once, absent for no limit of its
    # own. Never set on a Child, which can have no Children.
    child_limit: int | None = None
    # What became of it: absent until the Entry starts, and the only field that
    # says anything about the Run. Everything else is asked of the Run itself.
    run_id: str | None = None


__all__ = ["Attachment", "Entry"]
