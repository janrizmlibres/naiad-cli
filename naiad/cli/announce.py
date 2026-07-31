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


SUBJECT_PLACEHOLDER = "{subject}"


def announce_state(state: str, *, run: Run, subject: str | None = None) -> Announcement:
    """Rejects an Announcement the Prompt cannot be rendered from, for the same
    reason it rejects an undeclared State: both are clerical slips the agent can
    correct inside its own turn, and both would otherwise be silently inert.

    Which States require a Subject is not Naiad's to know — the Workflow says so
    by using the placeholder, which keeps the requirement in the file where the
    rest of that Workflow's meaning lives (ADR 0009).

    The reverse is deliberately not an error. A Subject a Prompt has no slot for
    is still part of what the agent said, and the Run log reads it: a Gate
    State's Subject is substituted nowhere and is what tells the human which
    item they have been handed.
    """
    workflow = load_workflow(run.workflow_path)
    declared = workflow.state(state)
    if declared is None:
        valid = ", ".join(known.name for known in workflow.states)
        raise AnnounceError(f"unknown state '{state}'; this workflow declares: {valid}")
    # Falsy rather than None: a blank Subject renders exactly as an absent one
    # and reaches the session just as unrecoverably, so the guard is on what the
    # Prompt would say rather than on whether the flag was typed.
    if not subject and declared.prompt and SUBJECT_PLACEHOLDER in declared.prompt:
        raise AnnounceError(
            f"state '{state}' needs a subject saying what this announcement is about; "
            f"announce it as: naiad state {state} --subject <value>"
        )
    return Announcements(run.root).announce(state, subject=subject)


__all__ = ["AnnounceError", "announce_state"]
