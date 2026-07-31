"""Naiad's own records — kept apart from the State file, which only the agent writes."""

import pytest

from naiad.domain.announcement import Announcement
from naiad.runtime.records import Handled, Turns


@pytest.fixture
def turns(tmp_path):
    return Turns(tmp_path)


@pytest.fixture
def handled(tmp_path):
    return Handled(tmp_path)


def test_no_turn_has_ended_before_the_stop_hook_fires(turns):
    assert turns.ended_since(Announcement(seq=1, state="grill")) is False


def test_a_turn_ending_after_an_announcement_counts_as_stopped(turns):
    turns.record_end(latest_seq=3)

    assert turns.ended_since(Announcement(seq=3, state="implement")) is True


def test_a_turn_that_ended_before_the_announcement_does_not_count(turns):
    """The agent announced and kept working; the last turn end predates it."""
    turns.record_end(latest_seq=2)

    assert turns.ended_since(Announcement(seq=3, state="implement")) is False


def test_a_turn_ending_with_nothing_announced_counts_for_no_announcement(turns):
    turns.record_end(latest_seq=None)

    assert turns.ended_since(Announcement(seq=1, state="grill")) is False


def test_a_turn_ending_with_nothing_announced_is_not_stopped_since_anything(turns):
    turns.record_end(latest_seq=None)

    assert turns.ended_since(None) is False


def test_nothing_has_been_acted_on_before_the_first_delivery(handled):
    assert handled.seq() is None


def test_recording_a_delivery_is_visible_to_a_fresh_reader(handled, tmp_path):
    handled.record(4)

    assert Handled(tmp_path).seq() == 4


def test_the_records_do_not_share_a_file_with_the_state_file(turns, handled, tmp_path):
    """The agent is the State file's only writer (ADR 0001)."""
    turns.record_end(latest_seq=1)
    handled.record(1)

    assert turns.path != handled.path
    assert "state.json" not in {turns.path.name, handled.path.name}
