"""What describing a piece of work is refused for, before the work exists.

Three checks — a Workflow that cannot be run, a start State the Workflow does
not declare, and a start State whose Prompt names a Subject with none given —
made both by kickoff and by enqueue, for the same
reason: whoever asked is standing right there and pays the error message only.
An Entry makes them when it is queued rather than when it starts, so that a
night's backlog cannot fail at three in the morning on a typo.

One copy of these checks rather than one per caller, so that neither can quietly
stop making one of them. Not every refusal is here: the Queue's own —
a Working branch another Entry has claimed — needs the Queue's contents and
lives with the enqueue, as does the missing-task refusal, which only
the entrances can fail — an Entry's task is total by the time kickoff sees it.
The announce command's missing-Subject check is a different guard on a
different actor, refusing what the agent said rather than what an operator
typed. This module still holds their exceptions and remedies, so that every
refusal about describing work speaks with one voice.
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

    # Names {state}, because which State wanted a Subject is not known until
    # the Workflow has been read.
    subject: str
    # How to say what the work is when neither a task nor a Subject did. No
    # {state}: the refusal is about describing work at all.
    task: str

    def for_subject(self, state: str) -> str:
        return self.subject.format(state=state)


def _typed(command: str) -> Remedy:
    """The remedy for work described in shell arguments: the line the operator
    typed, with the missing option added — something they can retype rather
    than a rule they have to translate. Takes the command alone and spells the
    positionals itself, because the task remedy needs the line both with
    `<task>` and without it."""
    described = f"{command} <workflow>"
    return Remedy(
        subject=f"try: {described} <task> --at {{state}} --subject <value>",
        task=f"try: {described} <task>, or {described} --subject <value>",
    )


# The remedies a refusal quotes back, named for where the work was described
# rather than for what they say. They live beside the checks rather than with
# either command, because the checks are what quote them and a caller's only
# job is to name where its reader wrote.
RUN_COMMAND = _typed("naiad run")
ADD_COMMAND = _typed("naiad queue add")
# Work described at the session being handed over. Spelled out rather than made
# by `_typed`, because an Adoption names its work in flags: there is no Subject
# to stand in for a Task, so the Task is required and the line reads
# differently from either operator command's.
ADOPT_COMMAND = Remedy(
    subject="try: naiad adopt <workflow> --at {state} --task <task> --subject <value>",
    # Unreachable, `--task` being required — worded anyway, so that a Remedy is
    # never a field holding nothing and a later relaxation cannot find one.
    task="try: naiad adopt <workflow> --at <state> --task <task>",
)
# Work described in a batch file. The refusal names the file and the Entry's
# position, so what is left to say is which key that Entry is missing.
BATCH_ENTRY = Remedy(
    subject='try: giving that entry a `subject = "<value>"`',
    task='try: giving that entry a `task = "<value>"` or a `subject = "<value>"`',
)


@dataclass(frozen=True)
class Start:
    """What survived the checks: the Workflow, the State the work begins at,
    and the Working branch — still optional, because omitting one is intent:
    the agent at the head of the Run derives a name there."""

    workflow: Workflow
    state: State
    working_branch: str | None


class MissingTask(Exception):
    """Work described with neither a task nor a Subject to stand in for one.
    With both absent nothing says what the work is — not to the Queue listing,
    not to the Answerer, not to a Prompt naming {task}."""


class MissingSubject(Exception):
    """Work to begin at a State whose Prompt names a Subject, with none given.

    Nothing is announced at either entrance, so the announce command's guard
    does not reach them. Without this the first Prompt arrives with the
    placeholder rendered empty, into a session with no memory of what it was
    meant to say.
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

    The Working branch is not among the checks: given, it is carried verbatim,
    and absent, the agent at the head of the Run derives one.
    """
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
    "ADOPT_COMMAND",
    "BATCH_ENTRY",
    "RUN_COMMAND",
    "MissingSubject",
    "MissingTask",
    "Remedy",
    "Start",
    "check_start",
]
