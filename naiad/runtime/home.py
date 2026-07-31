"""Where Naiad may keep what it owns, and the refusal when asked to keep it
somewhere else.

One directory, one override, and one place that reads it. The Runs live under
it and so does the Queue, so an operator who moves the home moves everything
Naiad holds rather than discovering that half of it stayed behind.

Nowhere Naiad writes is ever inside a target repository, for the reason a Run's
directory is not: what Naiad writes must not turn up in a pull request, and the
record must outlive the working copy. Both stores refuse that with one guard
here rather than a copy of the reason each.
"""

from __future__ import annotations

import os
from pathlib import Path

HOME_VARIABLE = "NAIAD_HOME"


class StorageError(Exception):
    """Something Naiad owns cannot be written where it was asked for.

    Shared by the Run store and the Queue, because an operator reading the
    message cares which path was refused rather than which store refused it.
    """


def naiad_home() -> Path:
    """The directory Naiad owns, unless the operator says otherwise."""
    override = os.environ.get(HOME_VARIABLE)
    return Path(override) if override else Path.home() / ".naiad"


def default_runs_root() -> Path:
    """Where Runs live."""
    return naiad_home() / "runs"


def default_queue_root() -> Path:
    """Where Entries live: beside the Runs, under the same home."""
    return naiad_home() / "queue"


def default_lock_path() -> Path:
    """What the one Supervisor holds while it drives the Queue.

    Under the same home as the Queue it guards, so that an operator who moves
    the home moves the lock with it — two homes are two Queues, and a lock left
    behind in the first would refuse a Supervisor for the second.
    """
    return naiad_home() / "supervisor.lock"


def refuse_inside_repository(root: Path, target_repo: Path, *, what: str) -> None:
    """Nothing Naiad owns may lie inside a target repository, so that what
    Naiad writes cannot turn up in the pull request the work produces and the
    record outlives the working copy.

    One guard for both stores: a Queue rooted inside a repository is refused
    for exactly the reason a Run's directory is, and two copies of the reason
    would let the two drift apart.
    """
    real_root = real_path(root)
    real_repo = real_path(target_repo)
    if real_root == real_repo or real_repo in real_root.parents:
        raise StorageError(
            f"{what} {root} lies inside the target repository {real_repo}; "
            f"naiad never writes into the target repository"
        )


def real_path(path: Path) -> Path:
    """Absolute, symlinks resolved as far as they exist. A containment check
    must compare real locations, and the directory being checked for may not
    exist yet."""
    return Path(os.path.realpath(path))


__all__ = [
    "HOME_VARIABLE",
    "StorageError",
    "default_lock_path",
    "default_queue_root",
    "default_runs_root",
    "naiad_home",
    "real_path",
    "refuse_inside_repository",
]
