"""Naiad's own records — kept apart from the State file, which only the agent writes."""

import pytest

from naiad.domain.announcement import Announcement
from naiad.domain.decide import WAIT_BUDGET_SECONDS, WAIT_DEFAULT_SECONDS
from naiad.runtime.records import (
    ClearAttempts,
    Clears,
    Deliveries,
    EntryTurns,
    Handled,
    Holds,
    Notices,
    Submissions,
    Turns,
    Waits,
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


@pytest.fixture
def waits(tmp_path):
    return Waits(tmp_path)


def test_no_wait_is_in_force_before_one_is_declared(waits):
    assert waits.waiting(GRILL, now=0.0) is False
    assert waits.reason(GRILL) is None
    assert waits.count(GRILL) == 0


def test_a_declared_wait_is_in_force_until_its_deadline(waits):
    waits.record(GRILL, reason="2 review agents", now=100.0, seconds=60.0)

    assert waits.waiting(GRILL, now=100.0 + 59.0) is True
    assert waits.waiting(GRILL, now=100.0 + 60.0) is False
    assert waits.reason(GRILL) == "2 review agents"


def test_a_wait_names_no_duration_and_gets_the_default(waits):
    waits.record(GRILL, reason="a check", now=0.0)

    assert waits.waiting(GRILL, now=WAIT_DEFAULT_SECONDS - 1) is True
    assert waits.waiting(GRILL, now=WAIT_DEFAULT_SECONDS) is False


def test_a_wait_is_kept_against_its_announcement(waits):
    """The next Announcement re-arms it, like every per-Announcement fact."""
    waits.record(GRILL, reason="a check", now=0.0, seconds=600.0)

    assert waits.waiting(IMPLEMENT, now=1.0) is False
    assert waits.reason(IMPLEMENT) is None
    assert waits.count(IMPLEMENT) == 0


def test_a_new_wait_replaces_the_last_and_is_counted(waits):
    waits.record(GRILL, reason="first agent", now=0.0, seconds=600.0)
    waits.record(GRILL, reason="second agent", now=120.0, seconds=600.0)

    assert waits.reason(GRILL) == "second agent"
    assert waits.count(GRILL) == 2
    assert waits.waiting(GRILL, now=120.0 + 599.0) is True


def test_the_budget_is_charged_for_time_waited_rather_than_time_claimed(waits):
    """An agent woken early and re-declaring — several background tasks
    finishing at different moments — is the honest pattern the verb exists
    for, and charging each full claim would exhaust it in a few wakes
    (ADR 0021)."""
    waits.record(GRILL, reason="first", now=0.0, seconds=600.0)
    waits.record(GRILL, reason="second", now=120.0, seconds=600.0)

    assert waits.remaining(GRILL, now=120.0) == pytest.approx(WAIT_BUDGET_SECONDS - 120.0)


def test_an_expired_wait_charges_no_more_than_it_claimed(waits):
    """Silence past the deadline is the silence rule's to spend, not the
    budget's."""
    waits.record(GRILL, reason="a check", now=0.0, seconds=60.0)

    assert waits.remaining(GRILL, now=1000.0) == pytest.approx(WAIT_BUDGET_SECONDS - 60.0)


def test_a_claim_past_the_remaining_budget_is_clamped_to_it(waits):
    waits.record(GRILL, reason="a check", now=0.0, seconds=WAIT_BUDGET_SECONDS * 2)

    assert waits.waiting(GRILL, now=WAIT_BUDGET_SECONDS - 1) is True
    assert waits.waiting(GRILL, now=WAIT_BUDGET_SECONDS) is False
    assert waits.remaining(GRILL, now=WAIT_BUDGET_SECONDS) == pytest.approx(0.0)


def test_the_budget_belongs_to_the_announcement(waits):
    waits.record(GRILL, reason="a check", now=0.0, seconds=600.0)

    assert waits.remaining(IMPLEMENT, now=600.0) == pytest.approx(WAIT_BUDGET_SECONDS)


def test_a_wait_re_arms_the_nudge_count(notices, waits):
    """A re-declared Wait after a wake is the honest signal, not an evasion:
    the silence it answers is new, so the allowance is too (ADR 0021)."""
    notices.record_nudge(GRILL)
    notices.record_nudge(GRILL, wait_count=1)

    assert notices.of(GRILL, wait_count=1) == (False, 1)
    assert notices.of(GRILL, wait_count=2) == (False, 0)


def test_a_declared_wait_counts_as_a_signal_of_life(tmp_path, waits):
    """The wait's own declaration resets idleness, so its expiry is measured
    from it rather than from whatever signal happened before."""
    (tmp_path / "run.json").write_text("{}")
    waits.record(GRILL, reason="a check", now=0.0, seconds=60.0)

    assert idle_seconds(tmp_path, now=_mtime(waits.path)) == pytest.approx(0, abs=0.01)


@pytest.fixture
def holds(tmp_path):
    return Holds(tmp_path)


def test_no_hold_is_in_force_before_one_is_declared(holds):
    assert holds.holding(GRILL) is False
    assert holds.reason(GRILL) is None


def test_a_declared_hold_stands_and_names_its_reason(holds):
    """No deadline to read against: a Hold has no clock (ADR 0025)."""
    holds.record(GRILL, reason="user typed 'pause'")

    assert holds.holding(GRILL) is True
    assert holds.reason(GRILL) == "user typed 'pause'"


def test_a_hold_is_kept_against_its_announcement(holds):
    """The agent signalling again is what ends a Hold: the next Announcement
    re-arms it, like every per-Announcement fact (ADR 0025)."""
    holds.record(GRILL, reason="user typed 'pause'")

    assert holds.holding(IMPLEMENT) is False
    assert holds.reason(IMPLEMENT) is None


def test_releasing_a_hold_lifts_it(holds):
    """A fresh Wait supersedes a Hold (ADR 0025), which the wait command does
    by releasing it — only the held flag drops, so nothing reads as held."""
    holds.record(GRILL, reason="user typed 'pause'")
    holds.release(GRILL)

    assert holds.holding(GRILL) is False


def test_releasing_a_hold_that_was_never_declared_is_harmless(holds):
    holds.release(GRILL)

    assert holds.holding(GRILL) is False


def test_a_hold_re_arms_the_notified_flag(notices, holds):
    """The likeliest Hold arrives after a notification: silence, two Nudges,
    the operator told, and only then the human's 'pause' relayed. Gated on the
    shared flag, that Hold would notify nobody and the Run would park silently
    — the exact failure ADR 0025 calls the notification load-bearing to
    prevent. A declared Hold is a fresh signal, so it re-arms the record the
    way a fresh Wait does (ADR 0021)."""
    notices.record_notified(GRILL)

    assert notices.of(GRILL, hold_count=1) == (False, 0)


def test_a_declared_hold_is_counted(holds):
    holds.record(GRILL, reason="user typed 'pause'")

    assert holds.count(GRILL) == 1
    assert holds.count(IMPLEMENT) == 0


def test_releasing_a_hold_keeps_its_count(holds):
    """The count keys the Notices record; a release that zeroed it would hand
    the next silence a re-armed notification it never earned."""
    holds.record(GRILL, reason="user typed 'pause'")
    holds.release(GRILL)

    assert holds.count(GRILL) == 1


def test_a_declared_hold_counts_as_a_signal_of_life(tmp_path, holds):
    (tmp_path / "run.json").write_text("{}")
    holds.record(GRILL, reason="user typed 'pause'")

    assert idle_seconds(tmp_path, now=_mtime(holds.path)) == pytest.approx(0, abs=0.01)


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


def test_no_turn_has_ended_while_an_entry_waits_to_become_a_run(tmp_path):
    assert EntryTurns(tmp_path, "20260808-adopt-1").count() == 0


def test_a_turn_ending_in_the_gap_is_counted_against_the_entry(tmp_path):
    """The adopting turn ends before the Supervisor's pass creates the Run, so
    the ending is recorded against the Entry that will become it (ADR 0042)."""
    EntryTurns(tmp_path, "20260808-adopt-1").record_end()

    assert EntryTurns(tmp_path, "20260808-adopt-1").count() == 1


def test_relocation_seeds_the_runs_turns_and_takes_the_sidecar(tmp_path):
    queue_root = tmp_path / "queue"
    run_root = tmp_path / "runs" / "r1"
    run_root.mkdir(parents=True)
    sidecar = EntryTurns(queue_root, "20260808-adopt-1")
    sidecar.record_end()
    sidecar.record_end()

    sidecar.relocate_into(run_root)

    assert Turns(run_root).count() == 2
    assert Turns(run_root).ended_since(None) is True
    assert not sidecar.path.exists()


def test_relocation_never_overwrites_what_the_run_already_heard(tmp_path):
    """A Stop that fired after the Run was created wrote a fresher record into
    the run root; the sidecar is then deleted unread (ADR 0042)."""
    queue_root = tmp_path / "queue"
    run_root = tmp_path / "runs" / "r1"
    run_root.mkdir(parents=True)
    Turns(run_root).record_end(latest_seq=None)
    sidecar = EntryTurns(queue_root, "20260808-adopt-1")
    sidecar.record_end()
    sidecar.record_end()
    sidecar.record_end()

    sidecar.relocate_into(run_root)

    assert Turns(run_root).count() == 1
    assert not sidecar.path.exists()


def test_relocating_an_absent_sidecar_seeds_nothing(tmp_path):
    """An ordinary Adoption whose turn had not yet ended: the Run's opening
    waits for the Stop hook, exactly as before."""
    queue_root = tmp_path / "queue"
    run_root = tmp_path / "runs" / "r1"
    run_root.mkdir(parents=True)

    EntryTurns(queue_root, "20260808-adopt-1").relocate_into(run_root)

    assert Turns(run_root).ended_since(None) is False


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


def test_no_prompt_has_been_typed_before_the_loop_types_one(tmp_path):
    deliveries = Deliveries(tmp_path)

    assert deliveries.attempts(GRILL) == 0
    assert deliveries.latest() is None


def test_a_typed_prompt_is_kept_with_what_the_hook_judges_it_against(tmp_path):
    """The hook runs in the Session's process and knows no Announcement: the
    latest attempt carries everything it needs (ADR 0053)."""
    Deliveries(tmp_path).record_attempt(GRILL, prompt="/grill add dark mode", turns=3, at=100.0)

    latest = Deliveries(tmp_path).latest()

    assert latest is not None
    assert (latest.seq, latest.attempt, latest.prompt, latest.at) == (1, 1, "/grill add dark mode", 100.0)
    assert Deliveries(tmp_path).attempts(GRILL) == 1
    assert Deliveries(tmp_path).turns(GRILL) == 3


def test_prompt_attempts_accumulate_within_one_announcement(tmp_path):
    deliveries = Deliveries(tmp_path)
    deliveries.record_attempt(GRILL, prompt="p", turns=3, at=100.0)
    deliveries.record_attempt(GRILL, prompt="p", turns=3, at=110.0)

    assert deliveries.attempts(GRILL) == 2
    assert deliveries.latest().attempt == 2


def test_the_next_announcement_types_its_prompt_from_the_first_attempt(tmp_path):
    deliveries = Deliveries(tmp_path)
    deliveries.record_attempt(GRILL, prompt="p", turns=3, at=100.0)
    deliveries.record_attempt(IMPLEMENT, prompt="q", turns=4, at=200.0)

    assert deliveries.attempts(GRILL) == 0
    assert deliveries.attempts(IMPLEMENT) == 1


def test_an_adoptions_opening_prompt_is_kept_against_no_announcement(tmp_path):
    deliveries = Deliveries(tmp_path)
    deliveries.record_attempt(None, prompt="p", turns=1, at=100.0)

    assert deliveries.attempts(None) == 1
    assert deliveries.latest().seq is None


def test_the_hook_has_said_nothing_about_an_attempt_it_has_not_seen(tmp_path):
    assert Submissions(tmp_path).of(GRILL, attempt=1) is None


def test_the_hooks_verdict_answers_the_attempt_it_was_given_for(tmp_path):
    Submissions(tmp_path).record(seq=1, attempt=1, verdict="rejected")

    assert Submissions(tmp_path).of(GRILL, attempt=1) == "rejected"


def test_a_verdict_on_an_earlier_attempt_says_nothing_about_the_retry(tmp_path):
    """The retry is typed after the first was turned away; that rejection must
    not be read as the retry's, or it would be typed a third time at once."""
    Submissions(tmp_path).record(seq=1, attempt=1, verdict="rejected")

    assert Submissions(tmp_path).of(GRILL, attempt=2) is None


def test_a_verdict_on_another_announcement_says_nothing_about_this_one(tmp_path):
    Submissions(tmp_path).record(seq=1, attempt=1, verdict="landed")

    assert Submissions(tmp_path).of(IMPLEMENT, attempt=1) is None


def test_typing_a_prompt_and_the_hooks_verdict_are_signs_of_life(tmp_path):
    Deliveries(tmp_path).record_attempt(GRILL, prompt="p", turns=0, at=0.0)
    typed = (tmp_path / "deliveries.json").stat().st_mtime
    assert idle_seconds(tmp_path, now=typed + 5) == pytest.approx(5, abs=1)

    Submissions(tmp_path).record(seq=1, attempt=1, verdict="landed")
    judged = (tmp_path / "submissions.json").stat().st_mtime
    assert idle_seconds(tmp_path, now=judged + 2) == pytest.approx(2, abs=1)
