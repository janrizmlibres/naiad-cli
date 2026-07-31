"""Naiad's own records — kept apart from the State file, which only the agent writes."""

import pytest

from naiad.domain.announcement import Announcement
from naiad.runtime.records import (
    ClearAttempts,
    Clears,
    Handled,
    Notices,
    Turns,
    idle_seconds,
)


@pytest.fixture
def turns(tmp_path):
    return Turns(tmp_path)


@pytest.fixture
def notices(tmp_path):
    return Notices(tmp_path)


GRILL = Announcement(seq=1, state="grill")
IMPLEMENT = Announcement(seq=2, state="implement")


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


def test_a_turn_ending_with_nothing_announced_still_counts_as_stopped(turns):
    """With nothing announced there is no Announcement for the turn end to be
    stale against, and an agent that ended a turn having announced nothing is
    exactly what a Nudge is for — most often at kickoff, before the agent has
    announced anything at all."""
    turns.record_end(latest_seq=None)

    assert turns.ended_since(None) is True


def test_no_turn_ending_at_all_is_not_stopped(turns):
    assert turns.ended_since(None) is False


def test_nothing_has_been_acted_on_before_the_first_delivery(handled):
    assert handled.seq() is None


def test_recording_a_delivery_is_visible_to_a_fresh_reader(handled, tmp_path):
    handled.record(4)

    assert Handled(tmp_path).seq() == 4


def test_nobody_has_been_notified_about_a_fresh_announcement(notices):
    assert notices.of(GRILL) == (False, 0)


def test_a_notification_is_remembered_for_the_announcement_it_was_about(notices, tmp_path):
    notices.record_notified(GRILL)

    assert Notices(tmp_path).of(GRILL) == (True, 0)


def test_a_new_announcement_re_arms_notification(notices):
    """Otherwise a Run notifies its operator once and then never again."""
    notices.record_notified(GRILL)

    assert notices.of(IMPLEMENT) == (False, 0)


def test_nudges_accumulate_within_one_announcement(notices):
    notices.record_nudge(GRILL)
    notices.record_nudge(GRILL)

    assert notices.of(GRILL) == (False, 2)


def test_nudges_are_counted_per_announcement(notices):
    """An agent that recovers and later stalls again gets a fresh allowance."""
    notices.record_nudge(GRILL)
    notices.record_nudge(GRILL)

    assert notices.of(IMPLEMENT) == (False, 0)


def test_notices_are_kept_before_anything_has_been_announced(notices):
    """A session can fall silent at kickoff, having announced nothing at all."""
    notices.record_nudge(None)

    assert notices.of(None) == (False, 1)
    assert notices.of(GRILL) == (False, 0)


def test_a_run_that_has_only_just_started_is_not_already_idle(tmp_path):
    """Idleness is measured from the last signal, and a Run with no signals yet
    has its own creation to measure from — otherwise every Run is born hung."""
    (tmp_path / "run.json").write_text("{}")

    assert idle_seconds(tmp_path, now=_mtime(tmp_path / "run.json") + 5) == pytest.approx(5)


def test_the_latest_signal_of_any_kind_is_what_idleness_is_measured_from(tmp_path, turns):
    (tmp_path / "run.json").write_text("{}")
    turns.record_end(latest_seq=1)

    assert idle_seconds(tmp_path, now=_mtime(turns.path)) == pytest.approx(0, abs=0.01)


def test_a_nudge_counts_as_a_signal_so_the_next_one_is_a_full_period_later(tmp_path, notices):
    """Without this the second Nudge follows the first on the very next tick."""
    (tmp_path / "run.json").write_text("{}")
    notices.record_nudge(GRILL)

    assert idle_seconds(tmp_path, now=_mtime(notices.path)) == pytest.approx(0, abs=0.01)


def test_no_clear_has_landed_before_the_hook_fires(tmp_path):
    assert Clears(tmp_path).count() == 0


def test_a_clear_landing_is_counted_and_visible_to_a_fresh_reader(tmp_path):
    Clears(tmp_path).record_landing()

    assert Clears(tmp_path).count() == 1


def test_clear_landings_accumulate(tmp_path):
    """A count rather than a flag, for the reason Turns keeps one: this State's
    Clear is told from the last State's by a baseline, not by a boolean."""
    clears = Clears(tmp_path)
    clears.record_landing()
    clears.record_landing()

    assert clears.count() == 2


def test_a_clear_is_unconfirmed_until_it_lands(tmp_path):
    clears = Clears(tmp_path)
    attempts = ClearAttempts(tmp_path)
    attempts.record_attempt(GRILL, landed=clears.count())

    assert attempts.confirmed(GRILL, clears) is False

    clears.record_landing()
    assert attempts.confirmed(GRILL, clears) is True


def test_no_attempt_means_no_confirmation_however_many_clears_have_landed(tmp_path):
    """A landing with no attempt of ours behind it is a Clear for some other
    Announcement — the delivery has not asked for this one's yet."""
    clears = Clears(tmp_path)
    clears.record_landing()
    attempts = ClearAttempts(tmp_path)

    assert attempts.attempts(GRILL) == 0
    assert attempts.confirmed(GRILL, clears) is False


def test_a_landing_before_the_attempt_does_not_confirm_it(tmp_path):
    """The whole reason a count is kept and not a flag: a Clear that landed for
    an earlier State must not read as this State's."""
    clears = Clears(tmp_path)
    attempts = ClearAttempts(tmp_path)
    clears.record_landing()  # an earlier State's Clear
    attempts.record_attempt(IMPLEMENT, landed=clears.count())

    assert attempts.confirmed(IMPLEMENT, clears) is False

    clears.record_landing()  # this State's Clear
    assert attempts.confirmed(IMPLEMENT, clears) is True


def test_clear_attempts_accumulate_within_one_announcement(tmp_path):
    clears = Clears(tmp_path)
    attempts = ClearAttempts(tmp_path)
    attempts.record_attempt(GRILL, landed=clears.count())
    attempts.record_attempt(GRILL, landed=clears.count())

    assert attempts.attempts(GRILL) == 2


def test_a_retry_keeps_the_first_attempts_baseline(tmp_path):
    """A slow /clear that lands only after a retry still confirms: the baseline
    is the first attempt's, so any landing since counts and the goalposts do
    not move under a Clear already on its way."""
    clears = Clears(tmp_path)
    attempts = ClearAttempts(tmp_path)
    attempts.record_attempt(GRILL, landed=clears.count())  # baseline 0
    clears.record_landing()  # count 1
    attempts.record_attempt(GRILL, landed=clears.count())  # landed 1, baseline still 0

    assert attempts.confirmed(GRILL, clears) is True


def test_clear_attempts_are_counted_per_announcement(tmp_path):
    """The next Announcement re-arms it, so a Run whose Clear was dropped once
    delivers the State after it cleanly."""
    clears = Clears(tmp_path)
    attempts = ClearAttempts(tmp_path)
    attempts.record_attempt(GRILL, landed=clears.count())

    assert attempts.attempts(IMPLEMENT) == 0
    assert attempts.confirmed(IMPLEMENT, clears) is False


def test_a_clear_landing_counts_as_a_signal_of_life(tmp_path):
    """A landed Clear is the session answering, so idleness is measured from it
    like any other signal — otherwise a Run waiting on its first Clear reads as
    hung."""
    (tmp_path / "run.json").write_text("{}")
    Clears(tmp_path).record_landing()

    assert idle_seconds(tmp_path, now=_mtime(Clears(tmp_path).path)) == pytest.approx(0, abs=0.01)


def test_a_clear_attempt_counts_as_a_signal_so_the_confirm_wait_starts_from_it(tmp_path):
    """Typing /clear is Naiad acting, so the wait for the marker is measured
    from the attempt — without this the confirm timeout would run from whatever
    happened before the Clear."""
    (tmp_path / "run.json").write_text("{}")
    ClearAttempts(tmp_path).record_attempt(GRILL, landed=0)

    assert idle_seconds(
        tmp_path, now=_mtime(ClearAttempts(tmp_path).path)
    ) == pytest.approx(0, abs=0.01)


def _mtime(path):
    return path.stat().st_mtime


def test_the_records_do_not_share_a_file_with_the_state_file(turns, handled, tmp_path):
    """The agent is the State file's only writer (ADR 0001)."""
    turns.record_end(latest_seq=1)
    handled.record(1)

    assert turns.path != handled.path
    assert "state.json" not in {turns.path.name, handled.path.name}
