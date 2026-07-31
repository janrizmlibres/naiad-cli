"""Adding an Entry to the Queue.

Supervises nothing itself. `naiad queue add` returns here and stops, which is
what an agent inside a session needs — a tool call that became a process
blocking for hours is the failure the Queue exists to avoid — and `naiad run`
goes on to adopt or become a Supervisor afterwards (ADR 0014).

The Entry is validated before it exists, so that everything which used to fail
at kickoff fails while whoever typed it is still standing at the terminal.
Validating and writing are separate steps rather than one, because a batch file
is rejected whole (naiad.cli.batch): every Entry it declares has to be found
sound while none of them is on disk yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from naiad.cli.refusals import MissingSubject, MissingWorkingBranch, Remedy, check_start
from naiad.domain.entry import Entry
from naiad.domain.transitions import UnknownState
from naiad.domain.workflow import WorkflowError
from naiad.runtime.home import real_path
from naiad.runtime.queue import Queue


@dataclass(frozen=True)
class Work:
    """One piece of work as it was described, before it is an Entry.

    Everything the flags of `naiad run` and `naiad queue add` set, which is
    everything a line of a batch file sets: the two describe the same thing in
    two vocabularies, and giving that thing a name is what lets a batch reach
    the single-Entry path rather than a parallel one that could drift from it.

    The Working branch is still optional here because it is refused rather than
    defaulted (ADR 0015): work described without one exists long enough to be
    turned away.
    """

    workflow_path: Path
    task: str
    target_repo: Path
    working_branch: str | None
    pinned_base: str | None = None
    start_state: str | None = None
    subject: str | None = None
    skip_gates: bool = False


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


# Everything preparing an Entry can be refused for: the four checks both
# entrances share, and the Queue's own. Named once so that a caller adding
# something to the message — which file, which position — does not have to
# list them again and cannot come to list one fewer.
REFUSALS = (
    BranchAlreadyClaimed,
    MissingSubject,
    MissingWorkingBranch,
    UnknownState,
    WorkflowError,
)


def enqueue(
    work: Work,
    *,
    queue: Queue,
    entry_id: str,
    created_at: str,
    # Which remedy a refusal quotes back. Required rather than defaulted,
    # because every entrance lands here and work described one way must not be
    # told to fix itself in another's vocabulary.
    remedy: Remedy,
) -> Entry:
    """One Entry, validated and on disk.

    The whole of adding one piece of work, kept as one call rather than left to
    each caller to prepare and then add: an Entry that was checked and never
    written, or written having been checked against a Queue read too early, are
    both things a second entrance could quietly do.
    """
    return queue.add(
        prepare(
            work,
            claimed=queue.all(),
            entry_id=entry_id,
            created_at=created_at,
            remedy=remedy,
        )
    )


def prepare(
    work: Work,
    *,
    # Every Entry holding a branch this one may not take. The Queue's contents,
    # and — for a batch validated whole before any of it is written — the
    # Entries the same file has already declared.
    claimed: Sequence[Entry],
    entry_id: str,
    created_at: str,
    remedy: Remedy,
) -> Entry:
    """The Entry this work describes, validated and not yet on disk.

    Separate from writing it, because a batch file is rejected whole: an Entry
    that cannot exist has to be discovered while the ones before it are still
    only in hand.
    """
    checked = check_start(
        workflow_path=work.workflow_path,
        start_state=work.start_state,
        subject=work.subject,
        working_branch=work.working_branch,
        remedy=remedy,
    )
    # Settled to one spelling before anything compares it, as a Run's target
    # repository already is: the branch claim is per repository, so `.` and
    # `../repo` reaching one checkout must not read as two.
    target_repo = real_path(work.target_repo)
    _refuse_a_claimed_branch(
        claimed, target_repo=target_repo, working_branch=checked.working_branch
    )

    return Entry(
        id=entry_id,
        workflow_path=work.workflow_path,
        task=work.task,
        target_repo=target_repo,
        working_branch=checked.working_branch,
        created_at=created_at,
        pinned_base=work.pinned_base,
        start_state=work.start_state,
        subject=work.subject,
        skip_gates=work.skip_gates,
    )


def _refuse_a_claimed_branch(
    claimed: Sequence[Entry], *, target_repo: Path, working_branch: str
) -> None:
    """Checked per repository, because a branch name from another repository is
    not a fact about this one: two projects may each have a `main` and each
    have an Entry working on it."""
    for held in claimed:
        if held.target_repo == target_repo and held.working_branch == working_branch:
            raise BranchAlreadyClaimed(
                f"entry '{held.id}' already works on '{working_branch}' in {target_repo}; "
                f"two entries on one branch would stack one's work into the other's, "
                f"so name another branch or remove that entry"
            )


__all__ = ["REFUSALS", "BranchAlreadyClaimed", "Work", "enqueue", "prepare"]
