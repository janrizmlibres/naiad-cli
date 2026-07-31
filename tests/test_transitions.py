"""Next-State resolution, as data in and State out.

This is where two operator options live — running with Gates skipped, and
starting at a named State — so it is tested over plain Workflows rather than
through a Run.
"""

import pytest

from naiad.domain.transitions import (
    UnknownState,
    expected_next_state,
    next_state,
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


@pytest.fixture
def workflow():
    return parse_workflow(WORKFLOW)


def test_the_next_state_is_the_one_declared_after_it(workflow):
    assert next_state(workflow, "grill").name == "review"


def test_the_last_state_has_no_next_state(workflow):
    assert next_state(workflow, "done") is None


def test_a_state_the_workflow_does_not_declare_has_no_next_state(workflow):
    assert next_state(workflow, "grrill") is None


def test_gates_are_kept_unless_they_are_being_skipped(workflow):
    assert next_state(workflow, "grill", skip_gates=True).name == "spec"


def test_skipping_gates_skips_any_number_of_consecutive_gate_states():
    workflow = parse_workflow(CONSECUTIVE_GATES)

    assert next_state(workflow, "grill", skip_gates=True).name == "spec"


def test_a_terminal_state_is_never_skipped_however_it_is_declared():
    """A Terminal State ends the Run rather than holding it for a human, so
    skipping one for having no Prompt would leave the Run unable to finish."""
    workflow = parse_workflow(
        'name = "w"\n'
        "[[states]]\nname = 'spec'\nprompt = '/to-spec'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )

    assert next_state(workflow, "spec", skip_gates=True).name == "done"


def test_skipping_gates_past_the_end_of_the_workflow_resolves_to_nothing():
    workflow = parse_workflow(
        'name = "w"\n'
        "[[states]]\nname = 'done'\nterminal = true\nprompt = '/finish'\n"
        "[[states]]\nname = 'review'\n"
    )

    assert next_state(workflow, "done", skip_gates=True) is None


def test_a_run_starts_at_the_first_state_unless_one_is_named(workflow):
    assert start_state(workflow, None).name == "grill"


def test_a_run_can_start_at_a_named_state(workflow):
    assert start_state(workflow, "spec").name == "spec"


def test_before_anything_is_announced_the_expectation_follows_the_starting_state(workflow):
    """At kickoff the agent has been given the first State's Prompt but has not
    announced anything, so what it owes next is that State's successor."""
    assert expected_next_state(workflow, announced=None, started_at=None).name == "review"


def test_before_anything_is_announced_a_named_starting_state_is_followed(workflow):
    assert expected_next_state(workflow, announced=None, started_at="review").name == "spec"


def test_once_a_state_is_announced_the_expectation_follows_that_state(workflow):
    assert expected_next_state(workflow, announced="review", started_at=None).name == "spec"


def test_the_expectation_honours_skipped_gates(workflow):
    expected = expected_next_state(workflow, announced="grill", started_at=None, skip_gates=True)

    assert expected.name == "spec"


def test_there_is_no_expectation_after_the_last_state(workflow):
    assert expected_next_state(workflow, announced="done", started_at=None) is None


def test_a_start_state_the_workflow_does_not_declare_is_rejected(workflow):
    with pytest.raises(UnknownState) as caught:
        start_state(workflow, "spek")

    assert "spek" in str(caught.value)
    for name in ("grill", "review", "spec", "done"):
        assert name in str(caught.value)
