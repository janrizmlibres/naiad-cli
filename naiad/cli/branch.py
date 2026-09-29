"""The agent's declaration of the Derived branch it just created.

A command rather than a file edit, for the reason announcing is:
the command checks and refuses where the agent can still correct itself, in
the same turn the branch was created.

Two refusals. Write-once, because the next Entry's Predecessor stands on the
declared name and a branch that moves mid-Run is the silent stacking failure
the Predecessor rule guards against. And a name another Entry in the same
repository holds — the two-Entries-one-branch refusal relocated to declaration time,
naming the holder so the agent derives another name and retries.
"""

from __future__ import annotations

from naiad.cli.enqueue import claimed_branch_message
from naiad.runtime.log import RunLog
from naiad.runtime.queue import Queue, branch_of
from naiad.runtime.run import Run, RunStore


class BranchError(Exception):
    """A declaration the agent must see and correct."""


def declare_branch(name: str, *, run: Run, queue: Queue, runs: RunStore) -> None:
    """Record the name as the Run's Working branch, and log where it came from.

    The claim check reads every held Entry's branch through `branch_of`, so a
    name another agent declared on its own Run is found here too — and the
    Entry this Run came from resolves to nothing, since this Run holds no
    branch until this very write.
    """
    if not name.strip():
        raise BranchError(
            "a declaration needs the branch's name; declare it as: naiad branch <name>"
        )
    if run.working_branch is not None:
        raise BranchError(
            f"this run's working branch is already '{run.working_branch}', and it is "
            f"write-once: the next entry's predecessor stands on it, so a branch that "
            f"moved mid-run would silently mis-stack the work behind it"
        )
    for held in queue.all():
        if held.target_repo == run.target_repo and branch_of(held, runs) == name:
            raise BranchError(
                claimed_branch_message(
                    held,
                    working_branch=name,
                    target_repo=run.target_repo,
                    remedy="derive another name and declare that instead",
                )
            )

    run.working_branch = name
    run.save()
    RunLog(run.root).record_branch(name)


__all__ = ["BranchError", "declare_branch"]
