"""Starting a Run: read the Workflow, open a session, deliver the first Prompt.

The order matters. The Workflow is validated before anything exists, so an
invalid Workflow costs the operator nothing but the error message.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from naiad.domain.prompt import render_prompt
from naiad.domain.session import SessionSpec, session_name
from naiad.domain.transitions import next_states
from naiad.domain.transitions import start_state as resolve_start_state
from naiad.domain.workflow import load_workflow
from naiad.runtime.resolve import RUN_ID_VARIABLE
from naiad.runtime.run import Run, RunStore


SUBJECT_PLACEHOLDER = "{subject}"


class MissingSubject(Exception):
    """A Run started at a State whose Prompt names a Subject, with none given.

    Kickoff is the second entrance to delivery and the announce command's guard
    does not reach it, because nothing is announced here. Without this the Run's
    first Prompt arrives with the placeholder rendered empty, into a session
    with no memory of what it was meant to say (ADR 0009).

    Refused before the Run directory or the session exists, as a malformed
    Workflow and an unknown start State already are: the operator is standing
    right there and pays the error message only.
    """


class MissingWorkingBranch(Exception):
    """A Run started with no Working branch.

    Naiad attempts no derivation, and none is possible: a correct branch name
    needs the affected application and an issue number, which are conventions
    of the target repository, and Naiad knows no repository's conventions
    (ADR 0015). So the operator supplies it or the Run does not start.

    Refused before the Run directory or the session exists, on the trade the
    missing-Subject refusal already makes: whoever started the Run is standing
    right there and pays the error message only. The alternative — starting
    anyway and letting {branch} render empty — surfaces at review time, on
    commits already made to whatever branch happened to be checked out.
    """


class Sessions(Protocol):
    def spawn(self, spec: SessionSpec) -> str: ...


def start_run(
    *,
    workflow_path: Path,
    task: str,
    target_repo: Path,
    # Required rather than defaulted, so that a second entrance to starting a
    # Run cannot forget it and quietly leave the Run without one.
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
    # Checked first because it needs nothing else: the Working branch is a fact
    # about the work rather than about the Workflow, so nothing has to be read
    # to know it is missing.
    if not working_branch:
        raise MissingWorkingBranch(
            "a run needs the working branch its commits belong on, which naiad "
            "cannot derive from your repository's conventions; "
            "start it as: naiad run <workflow> <task> --branch <branch>"
        )

    # Both the Workflow and the State to begin at are resolved before anything
    # exists, so a bad file or a mistyped State costs the operator nothing but
    # the error message. The Subject is checked in the same breath and for the
    # same reason.
    workflow = load_workflow(workflow_path)
    first = resolve_start_state(workflow, start_state)
    if not subject and first.prompt and SUBJECT_PLACEHOLDER in first.prompt:
        raise MissingSubject(
            f"state '{first.name}' needs a subject saying what the Run is to start on; "
            f"start it as: naiad run <workflow> <task> --at {first.name} --subject <value>"
        )
    successors = next_states(workflow, first.name, skip_gates=skip_gates)

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
