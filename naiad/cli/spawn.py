"""The agent's fifth Protocol verb: enqueueing an Entry as its own Child.

A command the agent types from inside its Session, like `naiad branch`, so
that a refusal reaches it as a message within its own turn and it can correct
the call there and then.

It supervises nothing. The Child is an Entry like any other, and the
Supervisor starts it in its turn: its working tree is its own, so it is a Lane
of its own and runs beside its Parent.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from naiad.cli.enqueue import Work, prepare
from naiad.cli.refusals import SPAWN_COMMAND
from naiad.domain.entry import Entry
from naiad.domain.settings import StateSetting
from naiad.runtime.home import real_path
from naiad.runtime.queue import Queue
from naiad.runtime.records import Children
from naiad.runtime.run import Run, RunStore

class SpawnError(Exception):
    """A Spawn the agent must see and correct."""


def spawn_child(
    *,
    run: Run,
    task: str | None,
    target_repo: Path,
    working_branch: str | None,
    pinned_base: str | None,
    start_state: str | None,
    subject: str | None,
    skip_gates: bool,
    settings: Sequence[StateSetting],
    queue: Queue,
    runs: RunStore,
    entry_id: str,
    created_at: str,
) -> Entry:
    """The Child, on disk in the Queue and on its Parent's Children record.

    It takes the Parent's Workflow file, settings and Gates-skipped, and its
    task, unless the command names its own: a Child behaves like the rest of
    the Run that spawned it. They are read off the Parent's Run, which carries
    them over from its Entry as they were queued.

    Checked by the same `prepare` every entrance uses, so that a Child cannot
    be queued where `naiad queue add` would have refused it.
    """
    entry = queue.entry_of(run.id)
    if entry is not None and entry.parent is not None:
        raise SpawnError(
            f"this run is itself a child of run '{entry.parent}', and a child cannot "
            f"spawn children of its own; do this work in this run instead"
        )
    if real_path(target_repo) == run.target_repo:
        raise SpawnError(
            f"{run.target_repo} is this run's own working tree, where a child would wait "
            f"behind this run in the same lane forever; give the child a working tree "
            f"of its own (git worktree add <path>) and pass that path as --repo"
        )

    child = prepare(
        Work(
            workflow_path=run.workflow_path,
            task=task if task is not None else run.task,
            target_repo=target_repo,
            working_branch=working_branch,
            pinned_base=pinned_base,
            start_state=start_state,
            subject=subject,
            skip_gates=skip_gates or run.skip_gates,
            settings=_overridden(run.settings, by=settings),
            parent=run.id,
        ),
        claimed=queue.all(),
        runs=runs,
        entry_id=entry_id,
        created_at=created_at,
        remedy=SPAWN_COMMAND,
    )

    # Recorded on the Parent before the Entry reaches the Queue: once it is
    # there the Supervisor may start it at once and record its Run, and a
    # record written after that would write the Run back out of it.
    children = Children(run.root)
    children.record_spawn(
        child.id,
        subject=child.subject,
        branch=child.working_branch,
        worktree=child.target_repo,
    )
    try:
        return queue.add(child)
    except BaseException:
        children.forget(child.id)
        raise


def _overridden(
    inherited: Sequence[StateSetting], *, by: Sequence[StateSetting]
) -> tuple[StateSetting, ...]:
    """The Parent's settings, with each one the command named for the same
    State replaced rather than added beside it."""
    named = {(setting.state, setting.setting) for setting in by}
    kept = tuple(
        setting for setting in inherited if (setting.state, setting.setting) not in named
    )
    return (*kept, *by)


__all__ = ["SpawnError", "spawn_child"]
