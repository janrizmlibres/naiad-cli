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


def expected_next_state(
    workflow: Workflow,
    *,
    announced: str | None,
    started_at: str | None,
    skip_gates: bool = False,
) -> State | None:
    """What the agent owes next, told to it by the Protocol.

    Where it stands is its latest Announcement, or — before it has made one —
    the State the Run began at, whose Prompt it was handed at kickoff.
    """
    standing = announced if announced is not None else start_state(workflow, started_at).name
    return next_state(workflow, standing, skip_gates=skip_gates)


def _after(workflow: Workflow, current: str) -> tuple[State, ...]:
    for index, state in enumerate(workflow.states):
        if state.name == current:
            return workflow.states[index + 1 :]
    return ()


__all__ = ["UnknownState", "expected_next_state", "next_state", "start_state"]
