"""What still addresses a Workflow file, asked before the file is removed or
moved.

An Entry stores the path it was queued with, and a Run the path it started
from, so a file taken from under either is one the Queue can no longer read
(ADR 0023, 0049). Paths are compared after resolving, so a library link and the
file behind it are one file: an Entry queued by either spelling addresses both.
"""

from __future__ import annotations

from pathlib import Path

from naiad.runtime.log import RunLog
from naiad.runtime.queue import DONE, Queue, status_of
from naiad.runtime.run import RunStore


def addressing(path: Path, *, queue: Queue, runs: RunStore) -> list[str]:
    """Each Entry that is not done and each live Run that addresses `path`, as
    the line to name it by.

    A live Run is named through its Entry when it has one, and by itself only
    when it has none, so nothing is named twice.
    """
    file = path.resolve()
    users: list[str] = []
    named: set[str] = set()

    for entry in queue.all():
        status = status_of(entry, runs)
        if status == DONE or entry.workflow_path.resolve() != file:
            continue
        users.append(f"entry {entry.id} ({status})")
        if entry.run_id is not None:
            named.add(entry.run_id)

    for run in runs.all():
        if run.id in named or run.workflow_path.resolve() != file:
            continue
        if not RunLog(run.root).ended():
            users.append(f"run {run.id}")

    return users
