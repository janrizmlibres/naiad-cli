"""The agent's side of the Protocol: announcing the State it is in.

Announcing is a command rather than a file edit (ADR 0001). Read-modify-write
bookkeeping across a Cleared context is exactly the clerical work a model slips
on, and a slip would be silently inert. The command allocates the ordering,
writes atomically, and rejects a State the Workflow does not declare — with the
valid names in the error, so the agent can correct a typo itself rather than
stalling.
"""

from __future__ import annotations

from naiad.cli.ask import unanswered_question
from naiad.domain.announcement import Announcement
from naiad.domain.prompt import BRANCH_PLACEHOLDER, SUBJECT_PLACEHOLDER
from naiad.domain.protocol import ANNOUNCE_SUBCOMMAND
from naiad.domain.transitions import UnknownState, start_state as resolve_start_state
from naiad.domain.workflow import Workflow, load_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.answers import AnswerLog
from naiad.runtime.log import RunLog
from naiad.runtime.run import Run


class AnnounceError(Exception):
    """An Announcement the agent must see and correct."""


def announce_state(state: str, *, run: Run, subject: str | None = None) -> Announcement:
    """Rejects an Announcement the Prompt cannot be rendered from, for the same
    reason it rejects an undeclared State: both are clerical slips the agent can
    correct inside its own turn, and both would otherwise be silently inert.

    Which States require a Subject is not Naiad's to know — the Workflow says so
    by using the placeholder, which keeps the requirement in the file where the
    rest of that Workflow's meaning lives (ADR 0009).

    The reverse is deliberately not an error. A Subject a Prompt has no slot for
    is still part of what the agent said, and the Run log reads it: a Gate
    State's Subject is substituted nowhere and is what tells the human which
    item they have been handed.
    """
    workflow = load_workflow(run.workflow_path)
    declared = workflow.state(state)
    if declared is None:
        valid = ", ".join(known.name for known in workflow.states)
        raise AnnounceError(f"unknown state '{state}'; this workflow declares: {valid}")
    # Falsy rather than None: a blank Subject renders exactly as an absent one
    # and reaches the session just as unrecoverably, so the guard is on what the
    # Prompt would say rather than on whether the flag was typed.
    if not subject and declared.prompt and SUBJECT_PLACEHOLDER in declared.prompt:
        raise AnnounceError(
            f"state '{state}' needs a subject saying what this announcement is about; "
            f"announce it as: naiad {ANNOUNCE_SUBCOMMAND} {state} --subject <value>"
        )
    # Forgetting to declare a Derived branch is loud, not silent (ADR 0022): a
    # branchless Run that was handed a Prompt asking for one is refused here,
    # in a turn that can still repair it, rather than surfacing later as a
    # silently empty Predecessor. The missing-Subject refusal's shape, on a
    # different clerical slip.
    if run.working_branch is None and _branch_prompt_delivered(run, workflow):
        raise AnnounceError(
            "this run has no working branch, and the prompt asking you to derive one "
            "has already been delivered; declare the working branch you created first "
            "(`git branch --show-current` names the checked-out one) as: "
            "naiad branch <name>, then announce again"
        )
    # Announcing over an unanswered Question abandons it — permitted, because
    # the agent owns workflow progress (ADR 0001), but recorded: a log holding
    # only the Questions that were settled would show an unattended Run as
    # tidier than it was. Read before the announce that writes over it, logged
    # after, so a refused Announcement abandons nothing.
    abandoning = unanswered_question(run)
    announcement = Announcements(run.root).announce(state, subject=subject)
    if abandoning is not None and abandoning.question is not None:
        AnswerLog(run.root).record(
            question=abandoning.question,
            answer=f"abandoned unanswered; the agent announced '{state}' and moved on",
            abandoned=True,
        )
    return announcement


def _branch_prompt_delivered(run: Run, workflow: Workflow) -> bool:
    """Whether a Prompt carrying the branch placeholder has gone out, derived
    from the Workflow file and the delivery history rather than stored: the
    State the Run began at had its Prompt delivered at kickoff, and every
    delivery after that is a 'delivered' line in the Run log.

    A delivered State the Workflow no longer declares is skipped rather than
    guessed at: the file may have been edited since, and a guard that cannot
    read what was sent has no business refusing over it.
    """
    try:
        delivered = [resolve_start_state(workflow, run.start_state).name]
    except UnknownState:
        delivered = []
    delivered += RunLog(run.root).delivered_states()
    states = (workflow.state(name) for name in delivered)
    return any(state and state.prompt and BRANCH_PLACEHOLDER in state.prompt for state in states)


__all__ = ["AnnounceError", "announce_state"]
