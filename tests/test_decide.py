"""Every rule, as data in and Action out. No tmux, no subprocess, no clock."""

import pytest

from naiad.domain.announcement import Announcement
from naiad.domain.decide import NOTHING, Deliver, Signals, decide
from naiad.domain.workflow import parse_workflow

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "review"

[[states]]
name = "implement"
prompt = "/implement the next ticket, then announce {next_state}"
clear = true

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def workflow():
    return parse_workflow(WORKFLOW)


def signals(state, *, seq=1, handled_seq=None, stopped=True):
    return Signals(
        announcement=Announcement(seq=seq, state=state),
        handled_seq=handled_seq,
        stopped=stopped,
    )


def test_an_unhandled_announcement_with_a_turn_ended_delivers_that_states_prompt(workflow):
    action = decide(workflow, signals("grill"))

    assert action == Deliver(
        state="grill",
        prompt="/grill-with-docs {task}",
        clear=False,
        next_state="review",
    )


def test_an_unhandled_announcement_with_no_turn_ended_takes_no_action(workflow):
    assert decide(workflow, signals("grill", stopped=False)) is NOTHING


def test_an_announcement_already_acted_on_takes_no_action_however_often_asked(workflow):
    handled = signals("grill", seq=7, handled_seq=7)

    assert decide(workflow, handled) is NOTHING
    assert decide(workflow, handled) is NOTHING
    assert decide(workflow, handled) is NOTHING


def test_the_same_state_announced_twice_delivers_twice(workflow):
    """Naiad acts once per Announcement, not once per change of value: the
    agent's fifth implement iteration must be delivered like the fourth."""
    fourth = decide(workflow, signals("implement", seq=4, handled_seq=3))
    fifth = decide(workflow, signals("implement", seq=5, handled_seq=4))

    assert isinstance(fourth, Deliver)
    assert isinstance(fifth, Deliver)
    assert fifth.state == fourth.state == "implement"


def test_a_state_declaring_clear_has_its_context_cleared_before_delivery(workflow):
    assert decide(workflow, signals("implement")).clear is True


def test_a_state_not_declaring_clear_keeps_its_context(workflow):
    assert decide(workflow, signals("grill")).clear is False


def test_nothing_announced_yet_takes_no_action(workflow):
    assert decide(workflow, Signals(announcement=None, handled_seq=None, stopped=True)) is NOTHING


def test_a_state_with_no_prompt_is_not_delivered(workflow):
    """A Gate State: Naiad has nothing to send. Notifying is another ticket."""
    assert decide(workflow, signals("review")) is NOTHING


def test_delivery_names_the_next_state_in_declared_order(workflow):
    assert decide(workflow, signals("implement")).next_state == "done"


def test_with_gates_skipped_delivery_names_the_next_state_that_has_a_prompt(workflow):
    assert decide(workflow, signals("grill"), skip_gates=True).next_state == "implement"


def test_with_gates_skipped_delivery_is_otherwise_unchanged(workflow):
    """Skipping Gates is a resolution-time filter and nothing more: the same
    Prompt is delivered, of the same State, Clearing or not as declared."""
    kept = decide(workflow, signals("grill"))
    skipped = decide(workflow, signals("grill"), skip_gates=True)

    assert (skipped.state, skipped.prompt, skipped.clear) == (kept.state, kept.prompt, kept.clear)
