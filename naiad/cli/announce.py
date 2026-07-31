"""The agent's side of the Protocol: announcing the State it is in.

Announcing is a command rather than a file edit (ADR 0001). Read-modify-write
bookkeeping across a Cleared context is exactly the clerical work a model slips
on, and a slip would be silently inert. The command allocates the ordering,
writes atomically, and rejects a State the Workflow does not declare — with the
valid names in the error, so the agent can correct a typo itself rather than
stalling.
"""

from __future__ import annotations

from naiad.domain.announcement import Announcement
from naiad.domain.workflow import load_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.run import Run


class AnnounceError(Exception):
    """An Announcement the agent must see and correct."""


def announce_state(state: str, *, run: Run) -> Announcement:
    workflow = load_workflow(run.workflow_path)
    if workflow.state(state) is None:
        valid = ", ".join(known.name for known in workflow.states)
        raise AnnounceError(f"unknown state '{state}'; this workflow declares: {valid}")
    return Announcements(run.root).announce(state)


__all__ = ["AnnounceError", "announce_state"]
