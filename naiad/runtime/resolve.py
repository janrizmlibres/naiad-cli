"""The single seam through which a Run is identified.

Naiad sets an environment variable on the session it spawns, but that is a
shortcut rather than the mechanism: a variable cannot be injected into a
process that already exists, so adopting a running session later must remain
possible. Every caller — hooks, agent-facing commands, the wiring layer — asks
here, and here alone, which Run it belongs to.

And when it belongs to none. A Run that has ended releases its Session
(ADR 0035): it stops being answered for here, which is the whole of the
release, because everything reached through this seam already has a
no-Run-attached path. The hooks print and record nothing, the Protocol verbs
refuse with 'no run is attached to this session', and the pane is free for the
Run that adopts the Session next.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from naiad.domain.decide import terminal_state
from naiad.domain.workflow import WorkflowError, load_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.log import RunLog
from naiad.runtime.run import Run, RunStore

RUN_ID_VARIABLE = "NAIAD_RUN_ID"


class NoRunError(Exception):
    """No Run is attached to this session. Ordinary for a hook, which is
    installed independently of any Run; fatal for a command that needs one."""


class RunResolver:
    def __init__(self, store: RunStore, environ: Mapping[str, str]) -> None:
        self._store = store
        self._environ = environ

    def resolve(
        self,
        *,
        tmux_pane: str | None = None,
        claude_session_id: str | None = None,
    ) -> Run | None:
        """The Run this caller belongs to, or None when none is attached —
        hooks are installed independently of any Run and must do nothing when
        there is no Run to act on.

        A Run that has ended is one of those Nones. The environment variable
        falls through to the session rather than short-circuiting on it, for
        the reason it already falls through when it names a Run that is not
        there: the variable is a shortcut, and a stale shortcut must not hide
        the Run this session actually belongs to. That fall-through is what
        lets an Adoption into a released Session resolve at all, the variable
        naming the finished Run being unsettable in a live process.
        """
        run_id = self._environ.get(RUN_ID_VARIABLE)
        if run_id:
            run = self._store.load(run_id)
            if run is not None and not _ended(run):
                return run

        if tmux_pane:
            found = self._matching(lambda run: run.tmux_pane == tmux_pane)
            if found is not None:
                return found

        if claude_session_id:
            return self._matching(lambda run: run.claude_session_id == claude_session_id)

        return None

    def _matching(self, predicate: Callable[[Run], bool]) -> Run | None:
        for run in self._store.all():
            if predicate(run) and not _ended(run):
                return run
        return None


def _ended(run: Run) -> bool:
    """Whether this Run is over, and so no longer answers for its Session.

    Read from the agent's own last Announcement, because the agent owns
    workflow progress (ADR 0001): the Session is released the moment the agent
    says the work is over, not the moment Naiad notices. Naiad's own record
    lags by a tick, and never arrives at all when nothing was watching.

    Terminal is asked of naiad.domain.decide rather than answered here, so that
    'an Announcement carrying a Question is not an ending' has one home. That
    clause is the whole difference between a Run that ended and a Run standing
    in its last State waiting to be answered, and a second copy would drift.

    A Workflow that cannot be read costs the answer its source, not its
    answer: which State is Terminal is unknowable, so the log line Naiad wrote
    when it carried out the Finish answers instead. One question with a
    degraded source rather than two ways to be true — and the same choice made
    where the Protocol is rendered (naiad.cli.protocol), which degrades rather
    than raising for the same file.
    """
    try:
        workflow = load_workflow(run.workflow_path)
    except WorkflowError:
        return RunLog(run.root).finished()
    return terminal_state(workflow, Announcements(run.root).latest()) is not None
