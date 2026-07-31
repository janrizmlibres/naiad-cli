"""Adding one Entry to the Queue.

Never supervises. This is the command an agent inside a session uses, so it
records the Entry and returns; a tool call that became a process blocking for
hours is the failure the Queue exists to avoid.

The Entry is validated before it exists, so that everything which used to fail
at kickoff fails while the operator is still standing at the terminal.
"""

from __future__ import annotations

from pathlib import Path

from naiad.cli.refusals import check_start
from naiad.runtime.home import real_path
from naiad.runtime.queue import Entry, Queue

# The line an operator can retype, quoted back at them by every refusal below.
COMMAND = "naiad queue add <workflow> <task>"


class BranchAlreadyClaimed(Exception):
    """Another Entry for the same repository already names this Working branch.

    The subtle refusal. Without it two Entries silently share a branch, and
    because checking out a branch that already exists is idempotent, the second
    Entry's work stacks into the first's invisibly — and the symptom is a pull
    request carrying somebody else's commits.

    A claim is a fact recorded on the Entry rather than a question about its
    Run, so every Entry in the Queue holds its branch until it is removed. That
    keeps the refusal from depending on what became of a Run (ADR 0013), and
    removing the Entry is what frees the branch.
    """


def enqueue(
    *,
    workflow_path: Path,
    task: str,
    target_repo: Path,
    # Required rather than defaulted, so that a second caller cannot forget it
    # and quietly queue work with no branch to do it on.
    working_branch: str | None,
    queue: Queue,
    entry_id: str,
    created_at: str,
    pinned_base: str | None = None,
    start_state: str | None = None,
    subject: str | None = None,
    skip_gates: bool = False,
) -> Entry:
    checked = check_start(
        workflow_path=workflow_path,
        start_state=start_state,
        subject=subject,
        working_branch=working_branch,
        how=COMMAND,
    )
    # Settled to one spelling before anything compares it, as a Run's target
    # repository already is: the branch claim is per repository, so `.` and
    # `../repo` reaching one checkout must not read as two.
    target_repo = real_path(target_repo)
    _refuse_a_claimed_branch(
        queue, target_repo=target_repo, working_branch=checked.working_branch
    )

    return queue.add(
        Entry(
            id=entry_id,
            workflow_path=workflow_path,
            task=task,
            target_repo=target_repo,
            working_branch=checked.working_branch,
            created_at=created_at,
            pinned_base=pinned_base,
            start_state=start_state,
            subject=subject,
            skip_gates=skip_gates,
        )
    )


def _refuse_a_claimed_branch(queue: Queue, *, target_repo: Path, working_branch: str) -> None:
    """Checked per repository, because a branch name from another repository is
    not a fact about this one: two projects may each have a `main` and each
    have an Entry working on it."""
    for held in queue.all():
        if held.target_repo == target_repo and held.working_branch == working_branch:
            raise BranchAlreadyClaimed(
                f"entry '{held.id}' already works on '{working_branch}' in {target_repo}; "
                f"two entries on one branch would stack one's work into the other's, "
                f"so name another branch or remove that entry"
            )


__all__ = ["BranchAlreadyClaimed", "enqueue"]
