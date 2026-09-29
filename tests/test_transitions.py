"""Next-State resolution, as data in and State out.

This is where two operator options live — running with Gates skipped, and
starting at a named State — so it is tested over plain Workflows rather than
through a Run.
"""

import pytest

from naiad.domain.transitions import (
    UnknownState,
    deviation,
    expected_next_states,
    next_states,
    parks_on,
    standing_state,
    start_state,
)
from naiad.domain.workflow import parse_workflow

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "review"

[[states]]
name = "spec"
prompt = "/to-spec"

[[states]]
name = "done"
terminal = true
"""

CONSECUTIVE_GATES = """
name = "gated"

[[states]]
name = "grill"
prompt = "/grill"

[[states]]
name = "review-the-grill"

[[states]]
name = "review-again"

[[states]]
name = "spec"
prompt = "/to-spec"

[[states]]
name = "done"
prompt = "/finish"
terminal = true
"""

BRANCHING = """
name = "branching"

[[states]]
name = "classify"
prompt = "/classify"
next = ["diagnose", "grill"]

[[states]]
name = "diagnose"
prompt = "/diagnose"
next = ["no-repro", "done"]

[[states]]
name = "no-repro"

[[states]]
name = "grill"
prompt = "/grill"

[[states]]
name = "done"
prompt = "/finish"
terminal = true
"""

# Both kinds of Gate State in one file: `review` sits in the declared order and
# `no-repro` is named as a candidate. The pair is the whole of ADR 0007, so it
# is asserted over one Workflow rather than two.
BOTH_KINDS_OF_GATE = """
name = "both"

[[states]]
name = "grill"
prompt = "/grill"

[[states]]
name = "review"

[[states]]
name = "diagnose"
prompt = "/diagnose"
next = ["no-repro", "done"]

[[states]]
name = "no-repro"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def workflow():
    return parse_workflow(WORKFLOW)


@pytest.fixture
def branching():
    return parse_workflow(BRANCHING)


def test_the_next_state_is_the_one_declared_after_it(workflow):
    assert next_states(workflow, "grill") == ("review",)


def test_the_last_state_has_no_next_state(workflow):
    assert next_states(workflow, "done") == ()


def test_a_state_the_workflow_does_not_declare_has_no_next_state(workflow):
    assert next_states(workflow, "grrill") == ()


def test_gates_are_kept_unless_they_are_being_skipped(workflow):
    assert next_states(workflow, "grill", skip_gates=True) == ("spec",)


def test_skipping_gates_skips_any_number_of_consecutive_gate_states():
    workflow = parse_workflow(CONSECUTIVE_GATES)

    assert next_states(workflow, "grill", skip_gates=True) == ("spec",)


def test_a_terminal_state_is_never_skipped_however_it_is_declared():
    """A Terminal State ends the Run rather than holding it for a human, so
    skipping one for having no Prompt would leave the Run unable to finish."""
    workflow = parse_workflow(
        'name = "w"\n'
        "[[states]]\nname = 'spec'\nprompt = '/to-spec'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )

    assert next_states(workflow, "spec", skip_gates=True) == ("done",)


def test_skipping_gates_past_the_end_of_the_workflow_resolves_to_nothing():
    workflow = parse_workflow(
        'name = "w"\n'
        "[[states]]\nname = 'done'\nterminal = true\nprompt = '/finish'\n"
        "[[states]]\nname = 'review'\n"
    )

    assert next_states(workflow, "done", skip_gates=True) == ()


def test_a_branching_state_resolves_to_its_declared_candidates(branching):
    """Declared candidates replace the declared order rather than adding to
    it, so the State after a Branching State in the file is not an exit."""
    assert next_states(branching, "classify") == ("diagnose", "grill")


def test_a_candidate_may_name_a_state_the_declared_order_puts_earlier(branching):
    """A branch rejoins a shared tail, and the tail is wherever the author put
    it — the candidate is a name, not an offset."""
    assert next_states(branching, "diagnose") == ("no-repro", "done")


def test_a_state_between_branching_ones_keeps_its_implicit_successor(branching):
    """Every non-branching State keeps the declared order, so expressing a
    branch does not mean annotating the whole file."""
    assert next_states(branching, "grill") == ("done",)


def test_a_gate_state_named_as_a_candidate_is_never_skipped(branching):
    """ADR 0007: skipping applies to the declared order alone. A Gate State the
    agent may choose is a destination rather than a routine checkpoint, and
    deleting it would tell an agent that could not reproduce a bug to finish."""
    assert next_states(branching, "diagnose", skip_gates=True) == ("no-repro", "done")


def test_gate_skipping_tells_the_two_kinds_of_gate_state_apart():
    """ADR 0007, both halves at once. `review` is a routine checkpoint an
    unattended Run may decline; `no-repro` is a destination the agent chose, and
    deleting it would overrule the judgment ADR 0001 gives away. One Workflow
    holds both, because it is the pair that carries the distinction.
    """
    workflow = parse_workflow(BOTH_KINDS_OF_GATE)

    assert next_states(workflow, "grill", skip_gates=True) == ("diagnose",)
    assert next_states(workflow, "diagnose", skip_gates=True) == ("no-repro", "done")


def test_a_run_starts_at_the_first_state_unless_one_is_named(workflow):
    assert start_state(workflow, None).name == "grill"


def test_a_run_can_start_at_a_named_state(workflow):
    assert start_state(workflow, "spec").name == "spec"


def test_before_anything_is_announced_the_expectation_follows_the_starting_state(workflow):
    """At kickoff the agent has been given the first State's Prompt but has not
    announced anything, so what it owes next is that State's successor."""
    assert expected_next_states(workflow, announced=None, started_at="grill") == ("review",)


def test_a_run_with_no_recorded_start_and_no_announcement_expects_nothing(workflow):
    """The record is the only source of where a Run began: the Workflow's first
    State is not a substitute, since it may have been renamed since."""
    assert expected_next_states(workflow, announced=None, started_at=None) == ()


def test_the_standing_state_is_the_announced_one_else_the_recorded_start():
    assert standing_state(announced="spec", started_at="grill") == "spec"
    assert standing_state(announced=None, started_at="grill") == "grill"
    assert standing_state(announced=None, started_at=None) is None


def test_before_anything_is_announced_a_named_starting_state_is_followed(workflow):
    assert expected_next_states(workflow, announced=None, started_at="review") == ("spec",)


def test_once_a_state_is_announced_the_expectation_follows_that_state(workflow):
    assert expected_next_states(workflow, announced="review", started_at=None) == ("spec",)


def test_the_expectation_honours_skipped_gates(workflow):
    expected = expected_next_states(workflow, announced="grill", started_at=None, skip_gates=True)

    assert expected == ("spec",)


def test_the_expectation_at_a_fork_is_every_candidate(branching):
    """All the agent has to go on after a Clear, so naming one of two would
    bias it toward whichever the author happened to list first (ADR 0001)."""
    expected = expected_next_states(branching, announced="classify", started_at=None)

    assert expected == ("diagnose", "grill")


def test_there_is_no_expectation_after_the_last_state(workflow):
    assert expected_next_states(workflow, announced="done", started_at=None) == ()


def test_a_start_state_the_workflow_does_not_declare_is_rejected(workflow):
    with pytest.raises(UnknownState) as caught:
        start_state(workflow, "spek")

    assert "spek" in str(caught.value)
    for name in ("grill", "review", "spec", "done"):
        assert name in str(caught.value)


def test_announcing_the_expected_next_state_is_not_a_deviation(workflow):
    """The ordinary case: the Run is where the Workflow says it should be."""
    assert deviation(workflow, announced="spec", previous_state="review") == ()


def test_a_deviation_names_the_state_that_was_expected_instead(workflow):
    """Recorded because it is more often a confused agent than a decision, and
    the operator reading it later needs to know what was owed."""
    assert deviation(workflow, announced="grill", previous_state="review") == ("spec",)


def test_announcing_any_declared_candidate_is_not_a_deviation(branching):
    """Choosing at a fork is the judgment the Branching State exists to ask
    for, so choosing correctly must not be recorded as a mistake."""
    assert deviation(branching, announced="diagnose", previous_state="classify") == ()
    assert deviation(branching, announced="grill", previous_state="classify") == ()


def test_announcing_outside_the_candidates_deviates_from_all_of_them(branching):
    """A human may have redirected the agent, so it is recorded rather than
    refused — and the record has to say what the whole fork expected."""
    deviated = deviation(branching, announced="no-repro", previous_state="classify")

    assert deviated == ("diagnose", "grill")


def test_before_any_announcement_the_run_stands_where_it_began(workflow):
    """The Run's first State was delivered at kickoff without an Announcement,
    so with nothing announced yet the expectation is that State's successor."""
    assert deviation(workflow, announced="spec", previous_state=None, started_at="grill") == (
        "review",
    )


def test_a_run_started_partway_expects_from_the_state_it_started_at(workflow):
    partway = deviation(workflow, announced="grill", previous_state=None, started_at="review")

    assert partway == ("spec",)


def test_announcing_the_same_state_again_is_not_a_deviation(workflow):
    """The implement loop is one State announced once per ticket. Treating a
    repeat as a departure would fill the log with a Run doing exactly what its
    Workflow asks of it."""
    assert deviation(workflow, announced="spec", previous_state="spec") == ()


def test_with_gates_skipped_the_expected_state_skips_them_too(workflow):
    """The expectation and the Prompt's interpolated successor are the same
    expectation, so an unattended Run must not deviate by obeying the Prompt
    it was given."""
    assert deviation(workflow, announced="spec", previous_state="grill", skip_gates=True) == ()


def test_a_state_with_nothing_after_it_expects_nothing(workflow):
    """Inventing an expectation to deviate from would be worse than having
    none: at the end of a Workflow there is nothing the agent owes."""
    assert deviation(workflow, announced="grill", previous_state="done") == ()


def test_a_run_that_began_at_a_state_the_workflow_no_longer_declares_expects_nothing(workflow):
    """A Workflow edited mid-Run costs the expectation, not the Run."""
    assert deviation(workflow, announced="grill", previous_state=None, started_at="gone") == ()


FORK_TO_A_GATE = """
name = "bug"

[[states]]
name = "diagnose"
prompt = "/diagnosing-bugs"
next = ["no-repro", "done"]

[[states]]
name = "no-repro"

[[states]]
name = "done"
terminal = true
"""


def test_naiad_parks_on_a_gate_state():
    assert parks_on(parse_workflow(WORKFLOW), "review")


@pytest.mark.parametrize("name", ["grill", "done", "nowhere"])
def test_naiad_does_not_park_on_a_prompt_a_terminal_or_an_undeclared_state(name):
    assert not parks_on(parse_workflow(WORKFLOW), name)


def test_naiad_does_not_park_on_a_routine_gate_when_gates_are_skipped():
    assert not parks_on(parse_workflow(WORKFLOW), "review", skip_gates=True)


def test_naiad_still_parks_on_a_gate_named_as_a_candidate_when_gates_are_skipped():
    """ADR 0007: a destination the agent chose is not a checkpoint to decline."""
    assert parks_on(parse_workflow(FORK_TO_A_GATE), "no-repro", skip_gates=True)
