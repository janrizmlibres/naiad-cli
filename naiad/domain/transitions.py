"""Which States may come next, and which State a Run begins at.

Pure: a Workflow and a State name in, States out. The Workflow file is the
single source of truth for ordering, so a Prompt names its successors by
interpolation rather than by hand.

What comes next is plural throughout — usually a set of one, and every
candidate at a Branching State. One resolver with a plural return rather than a
singular and a plural accessor side by side: two would drift, and the caller
reaching for the singular one would silently drop a branch.

Both operator options that bend the ordering live here. Neither writes the
State file — Naiad only ever interpolates a different value, which is what
keeps the agent its single writer (ADR 0001).
"""

from __future__ import annotations

from naiad.domain.workflow import State, Workflow


class UnknownState(Exception):
    """A State name the Workflow does not declare, rejected before a Run
    exists. Carries the valid names so the operator can correct a typo."""


def next_states(workflow: Workflow, current: str, *, skip_gates: bool = False) -> tuple[str, ...]:
    """The States the agent may announce after `current`, by name.

    A Branching State resolves to its declared candidates verbatim; any other
    State resolves to the single successor the declared order supplies.

    Empty when there is nothing after it, and also when `current` is not
    declared — the agent may have been sent somewhere by a human, and having no
    expectation of it is more honest than inventing one.

    Names rather than States because a successor is only ever spoken: it is
    interpolated into a Prompt, named in the Protocol, and compared against
    what the agent announced. Nothing asks a successor what it is, so handing
    back States would leave every caller unwrapping them the same way.

    Gate-skipping applies to the declared order alone (ADR 0007). A Gate State
    named as a candidate is a destination the agent chose rather than a routine
    checkpoint, and deleting it would overrule the judgment ADR 0001 gives away.
    """
    state = workflow.state(current)
    if state is not None and state.next_candidates:
        return state.next_candidates

    for candidate in _after(workflow, current):
        if skip_gates and candidate.is_gate_state and not candidate.terminal:
            continue
        return (candidate.name,)
    return ()


def start_state(workflow: Workflow, named: str | None) -> State:
    """Where a Run begins: the first State, or the one the operator named."""
    if named is None:
        return workflow.states[0]

    found = workflow.state(named)
    if found is None:
        valid = ", ".join(state.name for state in workflow.states)
        raise UnknownState(f"unknown start state '{named}'; this workflow declares: {valid}")
    return found


def standing_state(*, announced: str | None, started_at: str | None) -> str | None:
    """Where the agent stands: its latest Announcement, or — before it has made
    one — the State the Run began at, whose Prompt it was handed at kickoff.

    Read from what the Run recorded rather than from the Workflow, so that a
    Workflow edited under a live Run changes no answer. One resolver rather
    than several, because it is asked from every end: the Protocol tells the
    agent what it owes from here, a Deviation is measured from here, a
    Compaction reminds the agent of it, and the Queue shows it. None when the
    Run has announced nothing and recorded no start, as a Run written before
    kickoff recorded one has: guessing the Workflow's first State instead
    would be an answer the Run never gave.
    """
    return announced if announced is not None else started_at


def expected_next_states(
    workflow: Workflow,
    *,
    announced: str | None,
    started_at: str | None,
    skip_gates: bool = False,
) -> tuple[str, ...]:
    """What the agent owes next, told to it by the Protocol."""
    standing = standing_state(announced=announced, started_at=started_at)
    if standing is None:
        return ()
    return next_states(workflow, standing, skip_gates=skip_gates)


def deviation(
    workflow: Workflow,
    *,
    announced: str,
    previous_state: str | None,
    started_at: str | None = None,
    skip_gates: bool = False,
) -> tuple[str, ...]:
    """The States that were expected instead, when this Announcement was none
    of them. Empty when the Announcement was expected.

    Plural because a Branching State expects several: announcing any declared
    candidate is on the path, so choosing correctly at a fork is not recorded
    as a mistake.

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
    ticket — and an empty expectation is a State with nothing after it, where
    inventing an expectation to deviate from would be worse than having none.
    """
    standing = standing_state(announced=previous_state, started_at=started_at)
    if standing is None or announced == standing:
        return ()
    expected = next_states(workflow, standing, skip_gates=skip_gates)
    return () if announced in expected else expected


def _after(workflow: Workflow, current: str) -> tuple[State, ...]:
    for index, state in enumerate(workflow.states):
        if state.name == current:
            return workflow.states[index + 1 :]
    return ()


__all__ = [
    "UnknownState",
    "deviation",
    "expected_next_states",
    "next_states",
    "standing_state",
    "start_state",
]
