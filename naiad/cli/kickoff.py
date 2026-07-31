"""Starting a Run: read the Workflow, open a session, deliver the first Prompt.

The order matters. The Workflow is validated before anything exists, so an
invalid Workflow costs the operator nothing but the error message.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from naiad.domain.prompt import render_prompt
from naiad.domain.session import SessionSpec, session_name
from naiad.domain.workflow import load_workflow
from naiad.runtime.resolve import RUN_ID_VARIABLE
from naiad.runtime.run import Run, RunStore


class Sessions(Protocol):
    def spawn(self, spec: SessionSpec) -> str: ...


def start_run(
    *,
    workflow_path: Path,
    task: str,
    target_repo: Path,
    store: RunStore,
    sessions: Sessions,
    run_id: str,
    claude_session_id: str,
    created_at: str,
) -> Run:
    workflow = load_workflow(workflow_path)
    first = workflow.states[0]
    successor = workflow.successor(first.name)

    run = store.create(
        run_id=run_id,
        workflow_path=workflow_path,
        task=task,
        target_repo=target_repo,
        created_at=created_at,
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
            task=task,
            next_state=successor.name if successor else None,
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
