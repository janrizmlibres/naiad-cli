"""Which State comes next, and which State a Run begins at.

Pure: a Workflow and a State name in, a State out. The Workflow file is the
single source of truth for ordering, so a Prompt names its successor by
interpolation rather than by hand.

Both operator options that bend the ordering live here. Neither writes the
State file — Naiad only ever interpolates a different value, which is what
keeps the agent its single writer (ADR 0001).
"""

from __future__ import annotations

from naiad.domain.workflow import State, Workflow


class UnknownState(Exception):
    """A State name the Workflow does not declare, rejected before a Run
    exists. Carries the valid names so the operator can correct a typo."""


def next_state(workflow: Workflow, current: str, *, skip_gates: bool = False) -> State | None:
    """The State the agent is expected to announce after `current`.

    None when there is nothing after it, and also when `current` is not
    declared — the agent may have been sent somewhere by a human, and having no
    expectation of it is more honest than inventing one.
    """
    for candidate in _after(workflow, current):
        if skip_gates and candidate.is_gate_state and not candidate.terminal:
            continue
        return candidate
    return None


def start_state(workflow: Workflow, named: str | None) -> State:
    """Where a Run begins: the first State, or the one the operator named."""
    if named is None:
        return workflow.states[0]

    found = workflow.state(named)
    if found is None:
        valid = ", ".join(state.name for state in workflow.states)
        raise UnknownState(f"unknown start state '{named}'; this workflow declares: {valid}")
    return found


def standing_state(workflow: Workflow, *, announced: str | None, started_at: str | None) -> str:
    """Where the agent stands: its latest Announcement, or — before it has made
    one — the State the Run began at, whose Prompt it was handed at kickoff.

    One resolver rather than two, because it is asked from both ends: the
    Protocol tells the agent what it owes from here, and a Deviation is
    measured from here. Two copies would drift, and the Workflow file is the
    single source of truth for ordering.
    """
    return announced if announced is not None else start_state(workflow, started_at).name


def expected_next_state(
    workflow: Workflow,
    *,
    announced: str | None,
    started_at: str | None,
    skip_gates: bool = False,
) -> State | None:
    """What the agent owes next, told to it by the Protocol."""
    standing = standing_state(workflow, announced=announced, started_at=started_at)
    return next_state(workflow, standing, skip_gates=skip_gates)


def deviation(
    workflow: Workflow,
    *,
    announced: str,
    previous_state: str | None,
    started_at: str | None = None,
    skip_gates: bool = False,
) -> str | None:
    """The State that was expected instead, when this Announcement was not it.

    A Deviation is permitted and delivered — any State the Workflow declares is
    a legal target, backward ones included, because the human may have
    redirected the agent and refusing would deadlock exactly that intervention.
    It is recorded rather than acted on, which is why this classifies an
    Announcement instead of deciding an Action.

    Measured with the same resolution the agent was given: the Prompt it was
    working from named its successor, so an unattended Run obeying a Prompt
    that skipped a Gate must not be read as having left the path.

    Two Announcements are not Deviations. Re-announcing the State the agent is
    already standing in is the implement loop — one State, announced once per
    ticket — and an expectation of None is a State with nothing after it, where
    inventing an expectation to deviate from would be worse than having none.
    """
    try:
        standing = standing_state(workflow, announced=previous_state, started_at=started_at)
    except UnknownState:
        # A Workflow edited mid-Run that no longer declares the State this one
        # began at. That costs the expectation, not the Run: the same choice is
        # made where the Protocol is rendered (naiad.cli.protocol).
        return None

    if announced == standing:
        return None
    expected = next_state(workflow, standing, skip_gates=skip_gates)
    if expected is None or expected.name == announced:
        return None
    return expected.name


def _after(workflow: Workflow, current: str) -> tuple[State, ...]:
    for index, state in enumerate(workflow.states):
        if state.name == current:
            return workflow.states[index + 1 :]
    return ()


__all__ = [
    "UnknownState",
    "deviation",
    "expected_next_state",
    "next_state",
    "standing_state",
    "start_state",
]
