"""How an Answer log is shown at a terminal: the words `naiad queue answers`
prints everywhere, with whose outcome each was told apart by its style.

The words and the wrapping are pinned through the command in
tests/test_queue_command.py; what is pinned here is what each piece is styled
as, which only a terminal is shown.
"""

from fake_terminal import styles_of
from naiad.cli.answers import render_answers
from naiad.runtime.answers import Answer

RETRIES = Answer(
    question="Which module owns retries?",
    options=("the client", "the caller"),
    answer="the client",
    state="implement",
)


def test_a_block_styles_its_number_and_state_and_dims_the_options_heading():
    styles = styles_of(render_answers("a-run", [RETRIES], width=80))

    assert styles["1"] == "header"
    assert styles["implement"] == "state"
    assert styles["options:"] == "secondary"
    assert "Which module owns retries?" not in styles
    assert "the client" not in styles


def test_whose_outcome_it_was_is_told_apart_by_its_style():
    yours = Answer(question="Q?", options=("a",), answer="not mine", escalated=True)
    abandoned = Answer(question="Q?", options=("a",), answer="moved on", abandoned=True)

    styles = styles_of(render_answers("a-run", [RETRIES, yours, abandoned], width=80))

    assert styles["→ answerer:"] == "answer.answerer"
    assert styles["→ yours:"] == "answer.yours"
    assert styles["→ abandoned:"] == "answer.abandoned"


def test_a_run_asked_nothing_names_it_as_a_run():
    shown = render_answers("a-run", [], width=80)

    assert shown == "no questions were asked in a-run"
    assert styles_of(shown) == {"no questions were asked in ": "secondary", "a-run": "id"}
