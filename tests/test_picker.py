"""The numbered prompt `naiad state next` opens when given no States.

What is asserted is what the author sees listed, which
answers are taken, and that a bad answer is asked again rather than guessed at.
"""

from fake_terminal import styles_of
from naiad.cli.picker import pick_states

STATES = ["plan", "build", "done"]


def pick(answers, marked=("done",), states=STATES):
    """The choice made, and everything the author was shown."""
    shown = []
    replies = iter(answers)

    def read(prompt=""):
        shown.append(prompt)
        try:
            return next(replies)
        except StopIteration:
            raise EOFError from None

    chosen = pick_states("plan", states, marked, read=read, write=shown.append)
    return chosen, "\n".join(shown)


def test_the_states_are_listed_numbered_with_the_current_successors_marked():
    _, shown = pick(["1"], marked=("build", "done"))

    lines = shown.splitlines()
    assert lines[1].split()[:2] == ["1", "plan"]
    assert "*" not in lines[1]
    assert "*" in lines[2] and lines[2].split()[:2] == ["2", "build"]
    assert "*" in lines[3] and lines[3].split()[:2] == ["3", "done"]


def test_the_numbers_typed_are_the_successors_in_the_order_typed():
    chosen, _ = pick(["3 2"])

    assert chosen == ["done", "build"]


def test_commas_separate_numbers_too():
    chosen, _ = pick(["2,3"])

    assert chosen == ["build", "done"]


def test_an_empty_answer_keeps_the_current_successors():
    chosen, _ = pick([""])

    assert chosen is None


def test_an_answer_that_is_not_a_choice_is_asked_again_and_says_why():
    chosen, shown = pick(["7", "two", "2 2", "2"])

    assert chosen == ["build"]
    assert shown.count("not a choice") == 3


def test_the_end_of_input_keeps_the_current_successors():
    chosen, _ = pick([])

    assert chosen is None


def test_the_states_are_styled_as_states_and_the_words_are_unchanged():
    shown = []

    pick_states("plan", STATES, ("build",), read=lambda prompt="": "1", write=shown.append)

    assert shown[0] == "Successors of plan (* marks the current ones):"
    assert styles_of(shown[0]) == {"plan": "state"}
    assert styles_of(shown[2]) == {"build": "state"}
