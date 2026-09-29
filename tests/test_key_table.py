"""The file-level key table that `naiad workflow set` and `unset` read.

What is asserted is the table's contract: which keys it names, what it accepts
for each, and what it says when it refuses one, since every refusal here comes
before a byte is written.
"""

import pytest

from naiad.domain.key_table import FILE_KEYS_TABLE, file_key_help, file_value
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
