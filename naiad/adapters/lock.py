"""Whether a Supervisor is running, asked of the kernel.

An advisory file lock held for the Supervisor's whole life. The kernel releases
it when the process dies, so an interrupt or a crash leaves nothing stale to
reconcile — which a recorded process id would not, since a record outlives the
process that wrote it and a later reader cannot tell a live Supervisor from a
number the machine has since handed to something else.

It is an adapter and holds no rules. It answers one question — is anyone else
supervising — and what each command makes of the answer is the command's
(ADR 0014). Verified by manual smoke rather than by tests, which is the deal for
anything holding no logic; what the tests pin is the behaviour that depends on
the answer.
"""

from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class SupervisorLock:
    """The one Supervisor's claim on the Queue.

    Constructed with its path rather than reading one, so that a test and a
    second machine's home each get their own.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @contextmanager
    def taken(self) -> Iterator[bool]:
        """Hold the lock for the block, and say whether it is ours.

        True when this process now holds it and False when another does — the
        two halves of adopt-or-become — rather than a refusal, because a lock
        somebody else holds is the ordinary case for `naiad run` and only the
        caller knows whether it is an error.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Opened rather than created exclusively: the file is a handle to lock
        # against rather than a record of anything, so one left behind by a
        # Supervisor that died is reused rather than reconciled.
        handle = self.path.open("a")
        try:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                # Refused because another Supervisor holds it, or because the
                # filesystem will not lock at all. Both are read the same way,
                # and deliberately: a home that cannot answer the question must
                # not be a home where two Supervisors both start.
                yield False
                return
            yield True
        finally:
            # Closing releases the lock, so the release is the same line
            # whether the block ended, raised, or was interrupted.
            handle.close()

    def held(self) -> bool:
        """Whether somebody else is supervising, asked without becoming one.

        Answered by trying to take it: a lock that can be taken is a lock
        nobody holds. It is let go again immediately, so asking is not a claim.

        Asking is not free, though: for the instant of the question the lock is
        this process's, so a Supervisor starting at exactly that moment is told
        one is already running and enqueues instead of becoming one. The cost of
        losing that race is an Entry that waits rather than a Run that is
        started twice, and the operator is told which happened — so it is
        accepted rather than closed. A shared lock would not close it either:
        holding one for the same instant refuses the exclusive lock a starting
        Supervisor takes, which is the same race with the roles swapped.
        """
        with self.taken() as mine:
            return not mine


__all__ = ["SupervisorLock"]
