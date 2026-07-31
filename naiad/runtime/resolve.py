"""The single seam through which a Run is identified.

Naiad sets an environment variable on the session it spawns, but that is a
shortcut rather than the mechanism: a variable cannot be injected into a
process that already exists, so adopting a running session later must remain
possible. Every caller — hooks, agent-facing commands, the wiring layer — asks
here, and here alone, which Run it belongs to.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

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
        there is no Run to act on."""
        run_id = self._environ.get(RUN_ID_VARIABLE)
        if run_id:
            run = self._store.load(run_id)
            if run is not None:
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
            if predicate(run):
                return run
        return None
