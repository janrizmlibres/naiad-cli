"""The Run log: what it records, and what it can be read back for.

Its whole purpose is being read after the fact, so what is asserted here is
what a reader gets out of it — the order, the two things that must not blur
into one another, and the Deviation naming both States.
"""

import pytest

from naiad.domain.announcement import Announcement
from naiad.domain.decide import NOTHING, Consult, Deliver, Finish, Notify, Nudge, Respond
from naiad.domain.question import Question
from naiad.runtime.log import RunLog

QUESTION = Question(text="Which module owns retries?", options=("the client", "the caller"))


@pytest.fixture
def log(tmp_path):
    return RunLog(tmp_path)


def announcement(seq=1, state="implement", question=None):
    return Announcement(seq=seq, state=state, question=question)


def kinds(log):
    return [entry.kind for entry in log.entries()]


def test_a_run_that_has_done_nothing_has_an_empty_log(log):
    assert log.entries() == []


def test_every_announcement_and_every_action_is_recorded_in_order(log):
    """One narrative, read top to bottom. Out of order it is not a
    reconstruction of anything."""
    log.record_announcement(announcement(seq=1, state="grill"))
    log.record(Deliver(state="grill", prompt="/grill", clear=False, next_states=("review",)), seq=1)
    log.record_announcement(announcement(seq=2, state="review"))
    log.record(Notify(reason="state 'review' is a Gate State"), seq=2)

    assert kinds(log) == ["announced", "delivered", "announced", "notified"]


def test_delivering_a_prompt_and_answering_a_question_are_told_apart(log):
    """Both type into the same session, and a log that showed them alike would
    leave the operator unable to tell an answered Question from a phase that
    started twice."""
    delivered = Deliver(state="implement", prompt="/implement", clear=True, next_states=("pr",))
    log.record(delivered, seq=1)
    log.record(Respond(question=QUESTION, answer="the client"), seq=2)

    assert kinds(log) == ["delivered", "answered"]


def test_an_announcement_records_the_state_it_named(log):
    log.record_announcement(announcement(seq=3, state="implement"))

    entry = log.entries()[-1]
    assert entry.state == "implement"
    assert entry.seq == 3


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


def test_a_run_that_has_not_ended_is_not_finished(log):
    log.record_announcement(announcement(seq=1, state="grill"))

    assert log.finished() is False


def test_a_run_whose_log_holds_its_ending_is_finished(log):
    """What makes finishing final: it is read back rather than remembered, so
    a watch started again over a Run that ended finds nothing to do."""
    log.record(Finish(state="done"), seq=6)

    assert log.finished() is True


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
