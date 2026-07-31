"""What describing a piece of work is refused for, before the work exists.

Four checks — a Workflow that cannot be run, a start State the Workflow does
not declare, a start State whose Prompt names a Subject with none given, and a
missing Working branch — made both by kickoff and by enqueue, for the same
reason: whoever asked is standing right there and pays the error message only.
An Entry makes them when it is queued rather than when it starts, so that a
night's backlog cannot fail at three in the morning on a typo.

One copy of these four rather than one per caller, so that neither can quietly
stop making one of them. Not every refusal is here: the Queue's own —
a Working branch another Entry has claimed — needs the Queue's contents and
lives with the enqueue, and the announce command's missing-Subject check is a
different guard on a different actor, refusing what the agent said rather than
what an operator typed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from naiad.domain.prompt import SUBJECT_PLACEHOLDER
from naiad.domain.transitions import start_state as resolve_start_state
from naiad.domain.workflow import State, Workflow, load_workflow

@dataclass(frozen=True)
class Remedy:
    """How to supply what was missing, spelled the way whoever described the
    work wrote it.

    A command line and a batch file describe the same work in two vocabularies
    — `--branch B` against `branch = "B"` — so a refusal quoting flags at
    somebody editing a file tells them to type something the file has no room
    for. That is the same mistake as naming one command in the other's refusal,
    which is why the remedy travels with the caller rather than being fixed
    here.
    """

    branch: str
    # Names {state}, because which State wanted a Subject is not known until
    # the Workflow has been read.
    subject: str

    def for_subject(self, state: str) -> str:
        return self.subject.format(state=state)


def _typed(how: str) -> Remedy:
    """The remedy for work described in shell arguments: the line the operator
    typed, with the missing option added — something they can retype rather
    than a rule they have to translate."""
    return Remedy(
        branch=f"try: {how} --branch <branch>",
        subject=f"try: {how} --at {{state}} --subject <value>",
    )


# The remedies a refusal quotes back, named for where the work was described
# rather than for what they say. They live beside the checks rather than with
# either command, because the checks are what quote them and a caller's only
# job is to name where its reader wrote.
RUN_COMMAND = _typed("naiad run <workflow> <task>")
ADD_COMMAND = _typed("naiad queue add <workflow> <task>")
# Work described in a batch file. The refusal names the file and the Entry's
# position, so what is left to say is which key that Entry is missing.
BATCH_ENTRY = Remedy(
    branch='try: giving that entry a `branch = "<branch>"`',
    subject='try: giving that entry a `subject = "<value>"`',
)


@dataclass(frozen=True)
class Start:
    """What survived the checks: the Workflow, the State the work begins at,
    and the Working branch — no longer optional, because a caller holding one
    of these has already been refused if it was missing."""

    workflow: Workflow
    state: State
    working_branch: str


class MissingSubject(Exception):
    """Work to begin at a State whose Prompt names a Subject, with none given.

    Nothing is announced at either entrance, so the announce command's guard
    does not reach them. Without this the first Prompt arrives with the
    placeholder rendered empty, into a session with no memory of what it was
    meant to say (ADR 0009).
    """


class MissingWorkingBranch(Exception):
    """Work with no Working branch.

    Naiad attempts no derivation, and none is possible: a correct branch name
    needs the affected application and an issue number, which are conventions
    of the target repository, and Naiad knows no repository's conventions
    (ADR 0015). So it is supplied or the work does not start.

    The alternative — accepting it anyway and letting {branch} render empty —
    surfaces at review time, on commits already made to whatever branch
    happened to be checked out.
    """


def check_start(
    *,
    workflow_path: Path,
    start_state: str | None,
    subject: str | None,
    working_branch: str | None,
    remedy: Remedy,
) -> Start:
    """The Workflow and the State this work begins at, or the refusal.

    `remedy` is how whoever described this work would supply what is missing,
    so that every message ends in something they can act on rather than a rule
    they have to translate.

    The Working branch is checked first because it needs nothing else: it is a
    fact about the work rather than about the Workflow, so nothing has to be
    read to know it is missing.
    """
    if not working_branch:
        raise MissingWorkingBranch(
            "no working branch was given to do the work on, and naiad cannot "
            f"derive one from your repository's conventions; {remedy.branch}"
        )

    workflow = load_workflow(workflow_path)
    first = resolve_start_state(workflow, start_state)
    if not subject and first.prompt and SUBJECT_PLACEHOLDER in first.prompt:
        raise MissingSubject(
            f"state '{first.name}' needs a subject saying what it is to start on; "
            f"{remedy.for_subject(first.name)}"
        )
    return Start(workflow=workflow, state=first, working_branch=working_branch)


__all__ = [
    "ADD_COMMAND",
    "BATCH_ENTRY",
    "RUN_COMMAND",
    "MissingSubject",
    "MissingWorkingBranch",
    "Remedy",
    "Start",
    "check_start",
]
