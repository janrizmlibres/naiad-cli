"""The Run log: what it records, and what it can be read back for.

Its whole purpose is being read after the fact, so what is asserted here is
what a reader gets out of it — the order, the two things that must not blur
into one another, and the Deviation naming both States.
"""

import pytest

from naiad.domain.announcement import Announcement
from naiad.domain.decide import (
    NOTHING,
    Clear,
    Consult,
    Deliver,
    Finish,
    Notify,
    Nudge,
    Respond,
    Switch,
)
from naiad.domain.question import Question
from naiad.runtime.log import RunLog

QUESTION = Question(text="Which module owns retries?", options=("the client", "the caller"))


@pytest.fixture
def log(tmp_path):
    return RunLog(tmp_path)


def announcement(seq=1, state="implement", question=None, subject=None):
    return Announcement(seq=seq, state=state, question=question, subject=subject)


def kinds(log):
    return [entry.kind for entry in log.entries()]


def test_a_run_that_has_done_nothing_has_an_empty_log(log):
    assert log.entries() == []


def test_every_announcement_and_every_action_is_recorded_in_order(log):
    """One narrative, read top to bottom. Out of order it is not a
    reconstruction of anything."""
    log.record_announcement(announcement(seq=1, state="grill"))
    log.record(Deliver(state="grill", prompt="/grill", next_states=("review",)), seq=1)
    log.record_announcement(announcement(seq=2, state="review"))
    log.record(Notify(reason="state 'review' is a Gate State"), seq=2)

    assert kinds(log) == ["announced", "delivered", "announced", "notified"]


def test_delivering_a_prompt_and_answering_a_question_are_told_apart(log):
    """Both type into the same session, and a log that showed them alike would
    leave the operator unable to tell an answered Question from a phase that
    started twice."""
    delivered = Deliver(state="implement", prompt="/implement", next_states=("pr",))
    log.record(delivered, seq=1)
    log.record(Respond(question=QUESTION, answer="the client"), seq=2)

    assert kinds(log) == ["delivered", "answered"]


def test_a_clear_is_recorded_as_its_own_line_before_the_delivery(log):
    """The Clear splits off from delivery (ADR 0019), so the narrative shows the
    context discarded and then the Prompt sent — two lines, not one."""
    log.record(Clear(state="implement", attempt=1), seq=1)
    log.record(Deliver(state="implement", prompt="/implement", next_states=("pr",)), seq=1)

    assert [(e.kind, e.state) for e in log.entries()] == [
        ("cleared", "implement"),
        ("delivered", "implement"),
    ]


def test_each_switch_is_its_own_line_before_the_delivery(log):
    """A Switch is never confirmed (ADR 0026), so the log is the only record
    that it was typed at all — and the only place a State that ran at the wrong
    price can be diagnosed from (ADR 0038)."""
    log.record(Switch(state="grill", setting="model", value="opus"), seq=1)
    log.record(Switch(state="grill", setting="effort", value="high"), seq=1)
    log.record(Deliver(state="grill", prompt="/grill", next_states=("spec",)), seq=1)

    assert [(e.kind, e.setting, e.detail) for e in log.entries()] == [
        ("switched", "model", "opus"),
        ("switched", "effort", "high"),
        ("delivered", None, "next: spec"),
    ]


def test_the_belief_read_back_is_the_last_settings_typed(log):
    """What Naiad believes the Session holds is what Naiad last typed into it,
    and the log is where that is already written down (ADR 0039)."""
    log.record(Switch(state="grill", setting="model", value="opus"), seq=1)
    log.record(Switch(state="grill", setting="effort", value="high"), seq=1)

    assert log.belief(announcement(seq=2)) == ({"model": "opus", "effort": "high"}, False)


def test_a_later_switch_replaces_an_earlier_one(log):
    """The belief is the last value typed for a setting, not every value it has
    ever held."""
    log.record(Switch(state="grill", setting="model", value="opus"), seq=1)
    log.record(Switch(state="spec", setting="model", value="sonnet"), seq=2)

    settings, _ = log.belief(announcement(seq=3))
    assert settings == {"model": "sonnet"}


def test_a_notification_reads_as_a_hand_off_to_a_human(log):
    """A Notify is Naiad telling a human it needs them, and a human at the
    keyboard may type a /model of their own. What Naiad typed is then evidence
    of nothing, which is the fact reported here (ADR 0039)."""
    log.record(Switch(state="grill", setting="model", value="opus"), seq=1)
    log.record(Notify(reason="state 'review' is a Gate State"), seq=2)

    assert log.belief(announcement(seq=3)) == ({"model": "opus"}, True)


def test_a_switch_after_a_notification_answers_the_hand_off(log):
    """The hand-off is answered by the next Switch typed, not carried for the
    rest of the Run: what went in after the human had the keyboard is evidence
    again."""
    log.record(Notify(reason="state 'review' is a Gate State"), seq=1)
    log.record(Switch(state="spec", setting="model", value="sonnet"), seq=2)

    assert log.belief(announcement(seq=3)) == ({"model": "sonnet"}, False)


def test_an_announcement_between_the_notification_and_the_delivery_keeps_it(log):
    """Measured from the last Switch rather than from the previous
    Announcement. Were it the latter, an Announcement arriving between the
    Notify and the delivery would swallow the hand-off, and the settings a
    human may have changed would stand for the rest of the Run."""
    log.record(Switch(state="grill", setting="model", value="opus"), seq=1)
    log.record(Notify(reason="state 'review' is a Gate State"), seq=2)
    log.record_announcement(announcement(seq=3, state="spec"))

    _, handed_over = log.belief(announcement(seq=4))
    assert handed_over is True


def test_a_hand_off_within_this_announcement_still_counts(log):
    """A Notify and a delivery share an Announcement when a Clear looks dropped
    and the human clears by hand: Naiad notifies at that seq and delivers at it
    too. Only this Announcement's Switches are excluded, never its Notify, so
    the delivery that follows still types the settings again."""
    log.record(Switch(state="grill", setting="model", value="opus"), seq=4)
    log.record_announcement(announcement(seq=5))
    log.record(Notify(reason="the clear was not confirmed after 3 tries"), seq=5)

    assert log.belief(announcement(seq=5)) == ({"model": "opus"}, True)


def test_this_announcements_own_switches_are_not_read_back(log):
    """The belief is what the Session held when the Announcement arrived. Were
    a Switch just typed to count, the sequence would cut itself short — the
    second setting would read as already held, and never be typed."""
    log.record(Switch(state="grill", setting="model", value="opus"), seq=2)

    assert log.belief(announcement(seq=2)) == ({}, False)


def test_an_adopted_runs_first_delivery_believes_nothing(log):
    """It answers no Announcement and so is kept against no seq, like its Clear
    (ADR 0028). Its own Switches are its own to exclude, and there are none
    before them: Naiad did not open this Session and knows nothing of it."""
    log.record(Switch(state="spec", setting="model", value="sonnet"), seq=None)

    assert log.belief(None) == ({}, False)


def test_the_launch_flags_are_recorded_as_the_switches_they_are(log):
    """A flag read as the process starts sets the Session as surely as a
    /model typed into a running one (ADR 0039). How that is spelled in the
    narrative is this module's business, not the kickoff's."""
    log.record_launch(state="grill", model="opus", effort="high")

    assert [(e.kind, e.state, e.setting, e.detail) for e in log.entries()] == [
        ("switched", "grill", "model", "opus"),
        ("switched", "grill", "effort", "high"),
    ]


def test_a_launch_that_carried_no_flags_records_nothing(log):
    """A Gate State first delivers nothing, so it launches with neither flag
    and is believed to hold neither."""
    log.record_launch(state="review", model=None, effort=None)

    assert log.entries() == []


def test_a_retyped_clear_reads_apart_from_the_first_in_the_log(log):
    """A dropped Clear that had to be typed again is the notable event; the
    attempt number is what tells a retry from an ordinary first try."""
    log.record(Clear(state="implement", attempt=2), seq=1)

    assert "attempt 2" in log.entries()[-1].detail


def test_an_announcement_records_the_state_it_named(log):
    log.record_announcement(announcement(seq=3, state="implement"))

    entry = log.entries()[-1]
    assert entry.state == "implement"
    assert entry.seq == 3


def test_an_announcement_records_the_subject_it_carried(log):
    """The Run log is the Subject's other reader. A Gate State substitutes it
    nowhere, so without this the log says a Gate was reached and leaves the
    operator to read the session to find out which item (ADR 0009)."""
    log.record_announcement(announcement(seq=3, state="handover", subject="05-y.md"))

    assert "05-y.md" in log.entries()[-1].detail


def test_an_announcement_with_no_subject_records_no_detail(log):
    log.record_announcement(announcement(seq=3, state="grill"))

    assert log.entries()[-1].detail is None


def test_a_question_is_recorded_apart_from_a_state_announcement(log):
    """A Question is an Announcement, but the agent asking one has not moved:
    a log reading them alike shows a State entered that never was."""
    log.record_announcement(announcement(seq=4, state="implement", question=QUESTION))

    entry = log.entries()[-1]
    assert entry.kind == "asked"
    assert entry.state == "implement"
    assert QUESTION.text in entry.detail


def test_the_same_announcement_is_not_recorded_twice(log):
    """The tick loop looks at every Announcement on every tick — several times
    a minute — and only acts on it once."""
    log.record_announcement(announcement(seq=1, state="grill"))
    log.record_announcement(announcement(seq=1, state="grill"))

    assert kinds(log) == ["announced"]


def test_a_notification_records_why_the_operator_was_wanted(log):
    """The Action alone does not explain itself: 'notified' at 3am is only
    useful beside the reason it happened."""
    log.record(Notify(reason="the agent went silent"), seq=2)

    assert "went silent" in log.entries()[-1].detail


def test_a_nudge_records_which_attempt_it_was(log):
    log.record(Nudge(attempt=2), seq=2)

    assert "2" in log.entries()[-1].detail


def test_a_nudge_after_an_expired_wait_records_what_was_waited_on(log):
    """'nudged' overnight only reads beside what the agent said it was
    waiting on (ADR 0021)."""
    log.record(Nudge(attempt=1, expired_wait="2 review agents"), seq=2)

    assert "2 review agents" in log.entries()[-1].detail


def test_a_consultation_records_the_question_put_to_the_answerer(log):
    log.record(Consult(question=QUESTION), seq=2)

    assert QUESTION.text in log.entries()[-1].detail


def test_finishing_records_the_state_the_run_ended_at(log):
    log.record(Finish(state="done"), seq=9)

    entry = log.entries()[-1]
    assert entry.kind == "finished"
    assert entry.state == "done"


def test_a_tick_that_did_nothing_is_not_recorded(log):
    """Nothing is what most ticks decide. Logging it would bury the Run's few
    real events under thousands of lines of an agent working normally."""
    log.record(NOTHING, seq=1)

    assert log.entries() == []


def test_a_deviating_announcement_names_both_the_expected_state_and_the_announced_one(log):
    log.record_announcement(announcement(seq=5, state="grill"), deviated_from=("implement",))

    deviated = log.deviations()[-1]
    assert deviated.state == "grill"
    assert deviated.expected == "implement"


def test_a_deviation_from_a_fork_records_every_candidate_in_one_string(log):
    """Plural in the domain, joined for the record. The persisted shape is a
    human-readable diagnostic and deviations() only tests for presence, so
    widening it would strand existing Run logs for no gain."""
    log.record_announcement(
        announcement(seq=5, state="grill"), deviated_from=("no-repro", "pull-request")
    )

    assert log.deviations()[-1].expected == "no-repro or pull-request"


def test_a_run_log_written_before_forks_existed_still_parses(log):
    """The field was a single State name and still is one, so an existing log
    is read back unchanged rather than migrated."""
    log.path.write_text(
        '[{"kind": "announced", "seq": 1, "state": "grill", '
        '"detail": null, "expected": "implement"}]\n'
    )

    assert [entry.expected for entry in log.deviations()] == ["implement"]


def test_an_announcement_on_the_expected_path_is_not_a_deviation(log):
    log.record_announcement(announcement(seq=5, state="review"))

    assert log.deviations() == []


def test_an_announcement_that_is_never_delivered_can_still_deviate(log):
    """A jump straight to the end, or to a Gate out of order, is the Deviation
    most worth seeing — and Naiad delivers nothing for either."""
    log.record_announcement(announcement(seq=6, state="done"), deviated_from=("implement",))
    log.record(Finish(state="done"), seq=6)

    assert [entry.expected for entry in log.deviations()] == ["implement"]


def test_a_run_still_under_way_has_not_ended(log):
    log.record_announcement(announcement(seq=1, state="grill"))

    assert log.ended() is False


def test_a_run_whose_log_holds_its_finish_has_ended(log):
    """What makes finishing final: it is read back rather than remembered, so
    a watch started again over a Run that ended finds nothing to do."""
    log.record(Finish(state="done"), seq=6)

    assert log.ended() is True


def test_a_cancelled_run_has_ended(log):
    """The third witness of an ending, beside the Terminal Announcement and the
    Finish (ADR 0036). Every reader asks the one question — has this Run ended
    — so the Session releases and the next Prune takes the orphan."""
    log.record_cancellation(state="implement")

    assert log.ended() is True


def test_a_cancellation_is_its_own_line_saying_where_the_run_stood(log):
    """Not a 'finished' line: the log must not claim a Finish Naiad never
    carried out, and a reader six weeks later must be able to tell a Run that
    completed from one the operator called off."""
    log.record_announcement(announcement(seq=1, state="implement"))
    log.record_cancellation(state="implement")

    (_announced, cancelled) = log.entries()
    assert kinds(log) == ["announced", "cancelled"]
    assert cancelled.state == "implement"
    assert "entry" in cancelled.detail


def test_a_run_cancelled_before_it_announced_anything_names_no_state(log):
    """An Entry removed between the session opening and the first Announcement.
    None rather than a guess, as `previous_state` answers None."""
    log.record_cancellation(state=None)

    (cancelled,) = log.entries()
    assert cancelled.state is None
    assert log.ended() is True


def test_where_the_agent_stood_before_an_announcement_is_the_one_before_it(log):
    """What a Deviation is measured from. It is read back from the log because
    only the latest Announcement is kept anywhere else."""
    log.record_announcement(announcement(seq=1, state="grill"))
    log.record_announcement(announcement(seq=2, state="review"))

    assert log.previous_state(announcement(seq=3, state="implement")) == "review"


def test_before_anything_has_been_announced_the_agent_stands_nowhere(log):
    """None rather than a guess: where the Run began is the Run's business,
    and inventing it here would put the same rule in two places."""
    assert log.previous_state(announcement(seq=1, state="grill")) is None


def test_a_question_counts_as_where_the_agent_stood(log):
    """It carries the State the agent is standing in, so a Question raised
    mid-phase must not lose the Run its place."""
    log.record_announcement(announcement(seq=1, state="implement"))
    log.record_announcement(announcement(seq=2, state="implement", question=QUESTION))

    assert log.previous_state(announcement(seq=3, state="pr")) == "implement"


def test_the_log_survives_being_written_by_one_process_and_read_by_another(tmp_path):
    """Every record is a separate process's work in the end — the tick loop's,
    and one day a reader's — so the log is a file rather than an object."""
    RunLog(tmp_path).record_announcement(announcement(seq=1, state="grill"))

    assert kinds(RunLog(tmp_path)) == ["announced"]


def test_the_compaction_point_a_launch_carried_is_its_own_line_and_no_switch(log):
    """A `launched` line rather than a `switched` one: no State ever compares
    its settings against the point, so a Switch line would lie about what it
    is for, and the belief must not learn it (ADR 0047)."""
    log.record_launch(state="grill", model="opus", effort="high", autocompact="200k")

    assert [(e.kind, e.state, e.detail) for e in log.entries() if e.kind != "switched"] == [
        ("launched", "grill", "compacting at 200k"),
    ]
    assert log.belief(announcement(seq=1)) == ({"model": "opus", "effort": "high"}, False)


def test_a_launch_with_no_compaction_point_writes_no_launched_line(log):
    log.record_launch(state="grill", model="opus", effort=None, autocompact=None)

    assert kinds(log) == ["switched"]


def test_a_compaction_is_recorded_where_the_agent_stood(log):
    """The diagnostic: 'its context was summarised three times during
    implement' is read from here and nowhere else (ADR 0047)."""
    log.record_compaction(state="implement")

    assert [(e.kind, e.state) for e in log.entries()] == [("compacted", "implement")]


def test_a_compaction_before_anything_was_announced_names_no_state(log):
    log.record_compaction(state=None)

    assert [(e.kind, e.state) for e in log.entries()] == [("compacted", None)]


def test_a_compaction_leaves_the_belief_where_it_was(log):
    """A summary discards conversation and leaves the Session's settings in
    place, the reason ADR 0039 refused to key the belief on a Clear."""
    log.record(Switch(state="grill", setting="model", value="opus"), seq=1)
    log.record_compaction(state="grill")

    assert log.belief(announcement(seq=2)) == ({"model": "opus"}, False)
