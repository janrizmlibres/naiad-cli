"""The Protocol, as text.

Asserted on what the agent must be able to read out of it — the two commands,
the instruction not to ask a human, and which State to announce next — rather
than on exact wording, which is prose and will be tuned.
"""

from naiad.domain.protocol import render_protocol


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
