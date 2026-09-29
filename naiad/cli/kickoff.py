"""Starting a Run: read the Workflow, meet a session, deliver the first Prompt.

Reached only by the Supervisor taking an Entry off the Queue, since that is the
one entrance to starting Runs.

A Run meets its session one of two ways. Ordinarily one is opened for it and
handed its first Prompt as it launches. An Adoption's Run instead joins a
session that has been running all along — the human's own, full of the
conversation the early States built — and is handed nothing yet: its first
Prompt waits for a Turn to end and goes out from the tick loop. What
the two share is everything before the session: the same refusals, the same Run
directory, the same record of what the work is.

The checks are made again here even so. Everything a Run can be refused for was
already refused at enqueue — that is where an operator who mistyped pays the
error message, standing at the terminal rather than at three in the morning —
but an Entry queued last night is started now, and the Workflow file it names
may have been edited in between. One copy of the checks in naiad.cli.refusals, so
that the two moments cannot come to disagree about what is startable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from naiad.cli.refusals import ADD_COMMAND, ADOPT_COMMAND, check_start
from naiad.domain.entry import Attachment, Entry
from naiad.domain.prompt import render_prompt
from naiad.domain.session import SessionSpec, session_name
from naiad.domain.transitions import next_states
from naiad.runtime.log import RunLog
from naiad.runtime.records import EntryTurns
from naiad.runtime.resolve import RUN_ID_VARIABLE
from naiad.runtime.run import Run, RunStore


class Sessions(Protocol):
    """The tmux adapter, as starting a Run needs it: a session opened for a Run
    that spawns one, and an attachment to the pane an adopted Run joins.

    Attaching answers with the name of the tmux session holding that pane —
    the human's own, since Naiad did not name it — which is what the operator
    is later told to attach to. It is also the one moment a pane that has gone
    is noticed, and noticing it is worth more than guessing a name.
    """

    def spawn(self, spec: SessionSpec) -> str: ...
    def attach(self, pane: str) -> str: ...


def start_entry(
    entry: Entry,
    *,
    predecessor: str | None,
    store: RunStore,
    sessions: Sessions,
    # Where the Entry came from, so a Turn end the Stop hook left beside it
    # through an Adoption's gap moves into the Run being made.
    queue_root: Path,
    run_id: str,
    claude_session_id: str,
    created_at: str,
) -> Run:
    """Turn one Entry into the Run it always described, whichever way that Run
    meets its session.

    The choice is the Entry's attachment mark and nothing else: an Entry so
    marked names a session that already exists, and every other Entry wants one
    opened. It is made here rather than in the wiring above, beside
    the two functions it chooses between, so that neither entrance can be
    reached without passing this one.

    claude_session_id is the id a spawned session is opened with. An Adoption
    joins a session whose id is whatever it already had — recorded on the
    attachment when it could be gathered — so it is unused there.

    The Predecessor comes from the Action rather than from the Entry, since what
    an Entry stands on is resolved when it starts.
    """
    if entry.attachment is not None:
        run = attach_run(
            workflow_path=entry.workflow_path,
            task=entry.task,
            target_repo=entry.target_repo,
            working_branch=entry.working_branch,
            attachment=entry.attachment,
            predecessor=predecessor,
            store=store,
            sessions=sessions,
            run_id=run_id,
            created_at=created_at,
            start_state=entry.start_state,
            skip_gates=entry.skip_gates,
            subject=entry.subject,
        )
        # After the session is joined rather than before the Run exists, so a
        # Stop firing during this pass finds the Run by its pane and the move
        # below finds the fresher record already there.
        EntryTurns(queue_root, entry.id).relocate_into(run.root)
        return run
    return start_run(
        workflow_path=entry.workflow_path,
        task=entry.task,
        target_repo=entry.target_repo,
        working_branch=entry.working_branch,
        predecessor=predecessor,
        store=store,
        sessions=sessions,
        run_id=run_id,
        claude_session_id=claude_session_id,
        created_at=created_at,
        start_state=entry.start_state,
        skip_gates=entry.skip_gates,
        subject=entry.subject,
    )


def start_run(
    *,
    workflow_path: Path,
    task: str,
    target_repo: Path,
    # Required rather than defaulted, so that a caller cannot forget it and
    # quietly leave the Run without one. Optional in value: an Entry queued
    # without a branch starts a Run with none, and the agent at its head
    # derives and declares a name there.
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
    # absent for work that stands on nothing.
    predecessor: str | None = None,
) -> Run:
    # Every refusal first, so that a mistyped State or a missing Subject costs
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
        remedy=ADD_COMMAND,
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
        start_state=first.name,
        start_subject=subject,
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
            # Announcement, and kickoff announces nothing.
            task=run.task,
            branch=run.working_branch,
            predecessor=run.predecessor,
            next_states=successors,
            subject=subject,
        )
    )

    name = session_name(run_id)
    # Named rather than built inline, because what the launch actually carried
    # is what the log records below — one source for the flags and for the
    # belief they seed, so the two cannot come to disagree.
    spec = SessionSpec(
        name=name,
        cwd=target_repo,
        claude_session_id=claude_session_id,
        initial_prompt=opening_prompt,
        # A Switch precedes Prompt delivery, so a Gate State first — which
        # delivers nothing — launches without them.
        model=None if opening_prompt is None else first.model,
        effort=None if opening_prompt is None else first.effort,
        # The Workflow's rather than the State's, and carried whichever State
        # comes first: where the Session summarises itself precedes no Prompt,
        # so a Gate State first does not lose it.
        autocompact=checked.workflow.autocompact,
        environ={RUN_ID_VARIABLE: run_id},
    )
    pane = sessions.spawn(spec)
    run.attach_session(
        tmux_session=name,
        tmux_pane=pane,
        claude_session_id=claude_session_id,
    )
    # Read off the spawn rather than off the State, so that what is written down
    # is what the launch actually carried. An adopted Run has no
    # counterpart and needs none: Naiad did not open that Session and knows
    # nothing of its settings, so its belief starts empty.
    RunLog(run.root).record_launch(
        state=first.name, model=spec.model, effort=spec.effort, autocompact=spec.autocompact
    )
    return run


def attach_run(
    *,
    workflow_path: Path,
    task: str,
    target_repo: Path,
    working_branch: str | None,
    # Where the session is. Required and not optional in value: an Adoption
    # that named no pane was refused at the terminal, because a session Naiad
    # cannot type into is one it can never drive.
    attachment: Attachment,
    store: RunStore,
    sessions: Sessions,
    run_id: str,
    created_at: str,
    start_state: str | None = None,
    skip_gates: bool = False,
    subject: str | None = None,
    predecessor: str | None = None,
) -> Run:
    """Join the session an Adoption named, and deliver nothing yet.

    Joining it is the whole of what happens here. The start State's Prompt is
    held back because the agent in an adopted session is most likely mid-turn
    when the Supervisor reaches its Entry, and typing into a working session
    types over the work; the tick loop delivers it once a Turn end has been
    reported, the same rule an Answer follows.

    No environment variable is set, because none can be: a variable cannot be
    injected into a process that already exists. That shortcut is simply absent
    for an adopted Run, and the hooks and the agent's own commands resolve it
    through the seam's other keys — the pane, then the Claude session id
    (naiad.runtime.resolve).
    """
    # Every refusal first, as at kickoff and for the same reason: an Entry
    # queued at the session is taken hours later, and its Workflow file may
    # have been edited in between. The line quoted back is the one that queues
    # this work again — from the session, which is the only place an Adoption
    # can be described.
    checked = check_start(
        workflow_path=workflow_path,
        start_state=start_state,
        subject=subject,
        working_branch=working_branch,
        remedy=ADOPT_COMMAND,
    )

    run = store.create(
        run_id=run_id,
        workflow_path=workflow_path,
        task=task,
        target_repo=target_repo,
        created_at=created_at,
        working_branch=working_branch,
        predecessor=predecessor,
        skip_gates=skip_gates,
        start_state=checked.state.name,
        # Read back by the delivery that follows, in a later tick and possibly
        # a later process: what an adopted Run's first Prompt renders from
        # cannot be held in the hand that attached it.
        start_subject=subject,
        adopted=True,
    )

    run.attach_session(
        tmux_session=sessions.attach(attachment.tmux_pane),
        tmux_pane=attachment.tmux_pane,
        # Whichever keys the adopt command could gather; absent is the expected
        # answer rather than an unlucky one, and the pane is the reliable key.
        claude_session_id=attachment.claude_session_id,
    )
    # The first line of this Run's narrative. A spawned Run's log begins at its
    # first Announcement, but an adopted Run's session came from somewhere, and
    # where it came from is what a human reads the log to find out.
    RunLog(run.root).record_adoption(pane=attachment.tmux_pane)
    return run
