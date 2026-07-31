"""Starting a Run: read the Workflow, open a session, deliver the first Prompt.

Reached only by the Supervisor taking an Entry off the Queue, since that is the
one entrance to starting Runs (ADR 0014).

The checks are made again here even so. Everything a Run can be refused for was
already refused at enqueue — that is where an operator who mistyped pays the
error message, standing at the terminal rather than at three in the morning —
but an Entry queued last night is started now, and the Workflow file it names
may have been edited in between. One copy of the four in naiad.cli.refusals, so
that the two moments cannot come to disagree about what is startable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from naiad.cli.refusals import ADD_COMMAND, check_start
from naiad.domain.prompt import render_prompt
from naiad.domain.session import SessionSpec, session_name
from naiad.domain.transitions import next_states
from naiad.runtime.resolve import RUN_ID_VARIABLE
from naiad.runtime.run import Run, RunStore


class Sessions(Protocol):
    def spawn(self, spec: SessionSpec) -> str: ...


def start_run(
    *,
    workflow_path: Path,
    task: str,
    target_repo: Path,
    # Required rather than defaulted, so that a caller cannot forget it and
    # quietly leave the Run without one. Still typed as optional, because what
    # arrives is what an Entry was queued with and being handed nothing is the
    # case the refusal exists for.
    working_branch: str | None,
    store: RunStore,
    sessions: Sessions,
    run_id: str,
    claude_session_id: str,
    created_at: str,
    start_state: str | None = None,
    skip_gates: bool = False,
    subject: str | None = None,
    # Optional, and opaque: recorded and substituted without being read, and
    # absent for work that stands on nothing (ADR 0015).
    predecessor: str | None = None,
) -> Run:
    # Every refusal first, so that a mistyped State or a missing branch costs
    # the operator nothing but the error message: no Run directory, no session.
    checked = check_start(
        workflow_path=workflow_path,
        start_state=start_state,
        subject=subject,
        working_branch=working_branch,
        # Work refused here already has an Entry, so the line quoted back is the
        # one that queues it again — once the stale Entry has been removed —
        # rather than `naiad run`, which would queue a second Entry for work the
        # Queue is already holding and start supervising on top of it.
        how=ADD_COMMAND,
    )
    first = checked.state
    successors = next_states(checked.workflow, first.name, skip_gates=skip_gates)

    run = store.create(
        run_id=run_id,
        workflow_path=workflow_path,
        task=task,
        target_repo=target_repo,
        created_at=created_at,
        working_branch=working_branch,
        predecessor=predecessor,
        skip_gates=skip_gates,
        start_state=start_state,
    )

    # The first State's Clear flag is deliberately not acted on: the session is
    # about to be created, so there is no context to discard. Clearing belongs
    # to delivery into a session that is already running.
    #
    # A Gate State has no Prompt: Naiad delivers nothing and the human types.
    opening_prompt = (
        None
        if first.is_gate_state
        else render_prompt(
            first.prompt or "",
            # The three Run-level facts are read back off the Run just written,
            # as the tick loop reads them, so both entrances to delivery draw
            # on one source. The Subject is not among them: it belongs to an
            # Announcement, and kickoff announces nothing (ADR 0009).
            task=run.task,
            branch=run.working_branch,
            predecessor=run.predecessor,
            next_states=successors,
            subject=subject,
        )
    )

    name = session_name(run_id)
    pane = sessions.spawn(
        SessionSpec(
            name=name,
            cwd=target_repo,
            claude_session_id=claude_session_id,
            initial_prompt=opening_prompt,
            environ={RUN_ID_VARIABLE: run_id},
        )
    )
    run.attach_session(
        tmux_session=name,
        tmux_pane=pane,
        claude_session_id=claude_session_id,
    )
    return run
