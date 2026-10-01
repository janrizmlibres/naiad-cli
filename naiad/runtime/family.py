"""A Run's Children as its Join State is decided over: which are unfinished,
and which finished ones it has not been told of.

Read from the Parent's Children record and from each Child's own Run, never
from the Queue's listing of Entries: a Child stays findable after a
Cancellation or a Prune takes its Entry. The Queue is asked one thing only,
whether an unstarted Child's Entry is still there, because an Entry removed
before it ever started is a Child called off.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from naiad.domain.announcement import Announcement
from naiad.domain.decide import held
from naiad.domain.join import FinishedChild, Join, Outcome
from naiad.domain.workflow import WorkflowError, load_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.log import RunLog
from naiad.runtime.records import Child, Children, Handled, Joins
from naiad.runtime.run import Run, RunStore

# Whether an Entry is still in the Queue, by its id.
Entered = Callable[[str], bool]


def every_entry(entry_id: str) -> bool:
    """Every Entry taken to be in the Queue, for a reading made without one:
    an unstarted Child then reads as unfinished, which never releases a Join
    early."""
    return True


def read_join(
    parent_root: Path,
    announcement: Announcement | None,
    *,
    runs: RunStore,
    entered: Entered = every_entry,
) -> Join:
    """The Join signals of this Announcement.

    Once a set is recorded against it, that set is what it names, however
    the Children have moved since. Before then it names every finished Child
    no other Announcement named.

    entered defaults to every Entry being there.
    """
    readings = [_finished(child, runs=runs, entered=entered) for child in Children(parent_root).all()]
    unfinished = sum(1 for reading in readings if reading is None)
    joins = Joins(parent_root)
    recorded = joins.named(announcement)
    if recorded is not None:
        return Join(unfinished=unfinished, named=recorded, recorded=True)
    told = joins.told(announcement)
    return Join(
        unfinished=unfinished,
        named=tuple(
            reading
            for reading in readings
            if reading is not None and reading.entry_id not in told
        ),
    )


def unfinished_children(parent_root: Path, *, runs: RunStore, entered: Entered) -> list[Child]:
    """The Run's Children that have not finished, in the order they were
    spawned: not started while their Entry waits, running, or parked."""
    return [
        child
        for child in Children(parent_root).all()
        if _finished(child, runs=runs, entered=entered) is None
    ]


def untold_children(parent_root: Path) -> list[Child]:
    """The Run's Children no Join delivery has named yet, in the order they
    were spawned. A Child once named was handed to the Parent's Workflow."""
    told = Joins(parent_root).every_told()
    return [child for child in Children(parent_root).all() if child.entry_id not in told]


def joining(root: Path, *, runs: RunStore, entered: Entered = every_entry) -> bool:
    """Whether the Run in this directory is held at a Join State: the Prompt
    it is owed belongs to one and the Join is not released. The Prompt owed is
    the one its latest Announcement names until that is acted on, or, for an
    adopted Run that has announced nothing, the one of the State it was
    adopted at until that goes out.

    Asked by the status reading, through the rule the tick holds by, so that
    the listing and the tick cannot disagree. A Run whose Workflow can no
    longer be read is not joining: nothing says it is, and the tick will say
    what is wrong with the file.
    """
    run = runs.load(root.name)
    if run is None:
        return False
    latest = Announcements(root).latest()
    handled = Handled(root).seq()
    if latest is None:
        owed = run.start_state if run.adopted and not RunLog(root).opened() else None
    elif latest.question is None and (handled is None or latest.seq > handled):
        owed = latest.state
    else:
        owed = None
    if owed is None:
        return False
    try:
        workflow = load_workflow(run.workflow_path)
    except WorkflowError:
        return False
    return held(workflow, owed, read_join(root, latest, runs=runs, entered=entered))


def sessions_to_close(
    parent_root: Path, named: tuple[FinishedChild, ...], *, runs: RunStore
) -> list[Run]:
    """The Runs of the Children named whose Sessions are to close: those that
    completed and are not closed already. A cancelled Child keeps its Session
    for the person who stepped in, and a Child whose Run is gone, or that
    records no pane, has none to close."""
    completed = {child.entry_id for child in named if child.outcome == "completed"}
    closing = []
    for child in Children(parent_root).all():
        if child.entry_id not in completed or child.run_id is None:
            continue
        run = runs.load(child.run_id)
        if run is not None and run.tmux_pane and not RunLog(run.root).closed():
            closing.append(run)
    return closing


def _finished(child: Child, *, runs: RunStore, entered: Entered) -> FinishedChild | None:
    """The Child as its Parent is told of it, or None while it is unfinished.

    A Child's outcome comes from its Run log: completed once it records
    reaching a Terminal State, cancelled once it records a Cancellation. A
    Child that never started is unfinished while its Entry waits, and
    cancelled once the Entry is gone. A parked Child records no ending, so it
    is unfinished.

    The branch is the one it was given, or else the one its Run declared."""
    outcome: Outcome
    if child.run_id is None:
        if entered(child.entry_id):
            return None
        outcome = "cancelled"
    else:
        ending = RunLog(runs.root_for(child.run_id)).ending()
        if ending is None:
            return None
        outcome = "completed" if ending == "finished" else "cancelled"
    run = None if child.run_id is None else runs.load(child.run_id)
    return FinishedChild(
        entry_id=child.entry_id,
        subject=child.subject or (run.start_subject if run is not None else None),
        branch=child.branch or (run.working_branch if run is not None else None),
        worktree=child.worktree or (str(run.target_repo) if run is not None else "-"),
        outcome=outcome,
    )


__all__ = ["Entered", "every_entry", "joining", "read_join", "sessions_to_close", "unfinished_children", "untold_children"]
