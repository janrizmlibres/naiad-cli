"""The Protocol, as text.

Asserted on what the agent must be able to read out of it — the two commands,
the instruction not to ask a human, and which State to announce next — rather
than on exact wording, which is prose and will be tuned.
"""

from naiad.domain.decide import NUDGE_LIMIT
from naiad.domain.protocol import render_nudge, render_protocol


def test_names_the_command_that_announces_a_state():
    assert "naiad state" in render_protocol(next_state="spec")


def test_names_the_command_that_asks_a_question():
    assert "naiad ask" in render_protocol(next_state="spec")


def test_instructs_the_agent_never_to_ask_a_human_directly():
    protocol = render_protocol(next_state="spec").lower()

    assert "never" in protocol
    assert "ask" in protocol and "human" in protocol


def test_names_the_expected_next_state():
    assert "spec" in render_protocol(next_state="spec")


def test_the_commands_are_named_as_the_agent_must_actually_invoke_them():
    """A session's PATH is whatever tmux inherited, which need not hold the
    naiad that is driving the Run. Naming a command the agent cannot run costs
    it the ability to participate at all."""
    protocol = render_protocol(next_state="spec", naiad="/opt/naiad/bin/naiad")

    assert "/opt/naiad/bin/naiad state" in protocol
    assert "/opt/naiad/bin/naiad ask" in protocol


def test_a_run_with_no_next_state_is_told_so_rather_than_left_a_placeholder():
    protocol = render_protocol(next_state=None)

    assert "{" not in protocol
    assert "None" not in protocol


def test_a_nudge_tells_the_agent_what_to_run_to_get_the_run_moving():
    assert "naiad state" in render_nudge(attempt=1)


def test_a_nudge_names_the_command_as_the_agent_must_invoke_it():
    assert "/opt/naiad/bin/naiad state" in render_nudge(attempt=1, naiad="/opt/naiad/bin/naiad")


def test_the_second_nudge_is_worded_more_firmly_than_the_first():
    """A second reminder identical to the first is a reminder the agent has
    already ignored once; it says instead that a human is about to be called."""
    first = render_nudge(attempt=1)
    second = render_nudge(attempt=2)

    assert first != second
    assert "human" in second and "human" not in first


def test_no_nudge_is_left_holding_a_placeholder():
    assert "{" not in render_nudge(attempt=1) and "{" not in render_nudge(attempt=2)


def test_there_is_a_wording_for_every_nudge_naiad_is_willing_to_send():
    """The bound lives in the decision function and the words live here; if
    they drift apart, a nudged agent gets a traceback instead of a reminder."""
    for attempt in range(1, NUDGE_LIMIT + 1):
        assert render_nudge(attempt=attempt)
