"""The file-level key table that `naiad workflow set` and `unset` read.

What is asserted is the table's contract: which keys it names, what it accepts
for each, and what it says when it refuses one, since every refusal here comes
before a byte is written.
"""

import pytest

from naiad.domain.key_table import (
    FILE_KEYS_TABLE,
    STATE_KEYS_TABLE,
    file_key_help,
    file_value,
    state_key_help,
    state_row,
    state_value,
)
from naiad.domain.workflow import WorkflowError

KEYS = ["model", "effort", "autocompact", "answerer.model", "answerer.effort", "answerer.fallback"]


def test_the_table_names_the_six_file_level_keys_in_order():
    assert [key.name for key in FILE_KEYS_TABLE] == KEYS


@pytest.mark.parametrize("key", KEYS)
def test_every_key_takes_a_string_as_given(key):
    assert file_value(key, "opus") == "opus"


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_value_is_refused_pointing_at_unset(value):
    with pytest.raises(WorkflowError) as refused:
        file_value("model", value)

    assert "unset" in str(refused.value)


def test_name_is_refused_naming_rename():
    with pytest.raises(WorkflowError) as refused:
        file_value("name", "other")

    assert "naiad workflow rename" in str(refused.value)


def test_an_unknown_key_is_refused_listing_the_keys():
    with pytest.raises(WorkflowError) as refused:
        file_value("modle", "opus")

    message = str(refused.value)
    assert "unknown key 'modle'" in message
    assert all(key in message for key in KEYS)


def test_the_help_prints_each_key_with_its_value_shape():
    printed = file_key_help().splitlines()

    assert len(printed) == len(KEYS)
    for line, key in zip(printed, FILE_KEYS_TABLE):
        assert line.split()[0] == key.name
        assert key.shape in line


def test_a_value_of_several_lines_is_refused():
    with pytest.raises(WorkflowError) as refused:
        file_value("model", "opus\nsonnet")

    assert "one line" in str(refused.value)


STATE_KEYS = ["model", "effort", "clear", "terminal", "questions", "report"]


def test_the_state_table_names_the_six_state_keys_in_order():
    assert [key.name for key in STATE_KEYS_TABLE] == STATE_KEYS


@pytest.mark.parametrize("key", ["model", "effort"])
def test_a_state_model_and_effort_are_taken_as_given(key):
    assert state_value(key, "opus") == "opus"


@pytest.mark.parametrize("key", ["clear", "terminal", "report"])
@pytest.mark.parametrize(("text", "value"), [("true", True), ("false", False)])
def test_a_state_flag_is_a_boolean(key, text, value):
    assert state_value(key, text) is value


@pytest.mark.parametrize("key", ["clear", "terminal", "report"])
def test_a_state_flag_refuses_anything_but_true_or_false(key):
    with pytest.raises(WorkflowError) as refused:
        state_value(key, "yes")

    assert "true|false" in str(refused.value)


@pytest.mark.parametrize("text", ["answerer", "human"])
def test_questions_takes_answerer_or_human(text):
    assert state_value("questions", text) == text


def test_questions_refuses_anything_else_naming_both():
    with pytest.raises(WorkflowError) as refused:
        state_value("questions", "robot")

    assert "answerer|human" in str(refused.value)


@pytest.mark.parametrize(
    ("key", "verb"),
    [
        ("name", "naiad state rename"),
        ("prompt", "naiad state set-prompt"),
        ("next", "naiad state next"),
    ],
)
def test_a_key_a_verb_owns_is_refused_naming_the_verb(key, verb):
    with pytest.raises(WorkflowError) as refused:
        state_value(key, "x")

    assert verb in str(refused.value)


def test_a_state_key_the_table_lacks_is_refused_listing_the_keys():
    with pytest.raises(WorkflowError) as refused:
        state_value("modle", "opus")

    message = str(refused.value)
    assert "unknown key 'modle'" in message
    assert all(key in message for key in STATE_KEYS)


def test_a_blank_state_value_is_refused_pointing_at_unset():
    with pytest.raises(WorkflowError) as refused:
        state_value("model", " ")

    assert "naiad state unset" in str(refused.value)


def test_unset_reaches_the_same_rows_and_refuses_the_same_owned_keys():
    assert state_row("terminal").name == "terminal"
    with pytest.raises(WorkflowError) as refused:
        state_row("prompt")

    assert "naiad state set-prompt" in str(refused.value)


def test_the_state_help_prints_each_key_with_its_value_shape():
    printed = state_key_help().splitlines()

    assert len(printed) == len(STATE_KEYS)
    for line, key in zip(printed, STATE_KEYS_TABLE):
        assert line.split()[0] == key.name
        assert key.shape in line
