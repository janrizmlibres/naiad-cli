"""The Queue's rules, as data in and Action out. No tmux, no subprocess, no clock.

One scan produces three behaviours — sequential ordering, a parked Run blocking
the Queue, and crash recovery — with no special case for any of them. Each is
asserted separately here because each would be a different bug.
"""

from pathlib import Path

from naiad.domain.entry import Entry
from naiad.domain.supervise import DRAINED, IDLE, Resume, Signals, Start, supervise

REPO = Path("/repos/naiad")


def entry(identifier, **overrides):
    fields = dict(
        id=identifier,
        workflow_path=REPO / "workflow.toml",
        task="add dark mode",
        target_repo=REPO,
        working_branch=f"MC-AGENT-{identifier}",
        created_at="2026-07-22T12:00:00Z",
    )
    fields.update(overrides)
    return Entry(**fields)


def draining(*entries, finished=()):
    return Signals(entries=entries, finished=finished, following=False)


def following(*entries, finished=()):
    return Signals(entries=entries, finished=finished, following=True)


# An empty Queue is the whole of the difference between the two modes: one
# returns, the other comes round again.


def test_an_empty_queue_drains_when_draining():
    assert supervise(draining()) == DRAINED


def test_an_empty_queue_idles_when_following():
    """Following means Entries added later are picked up, so nothing to do now
    is not the same as nothing to do."""
    assert supervise(following()) == IDLE


# The scan: the first Entry that is not done, started if it has no Run and
# resumed if it has.


def test_the_first_entry_with_no_run_is_started():
    first, second = entry("one"), entry("two")

    assert supervise(draining(first, second)) == Start(entry=first, predecessor=None)


def test_a_started_entry_carries_its_pinned_base_as_its_predecessor():
    """Resolution rides on the Action, so the rule that picks an Entry and the
    rule that decides what it stands on are one decision rather than two."""
    pinned = entry("one", pinned_base="MC-AGENT-8000")

    assert supervise(draining(pinned)) == Start(entry=pinned, predecessor="MC-AGENT-8000")


def test_an_entry_whose_run_has_not_finished_is_resumed():
    running = entry("one", run_id="a-run")

    assert supervise(draining(running)) == Resume(entry=running)


def test_an_entry_whose_run_has_not_finished_stops_the_next_from_starting():
    """Sequential ordering and a parked Run blocking the Queue are the same
    case: the scan stops at the first Entry that is not done, and a parked Run
    is not finished (ADR 0012)."""
    running, waiting = entry("one", run_id="a-run"), entry("two")

    assert supervise(draining(running, waiting)) == Resume(entry=running)


def test_a_supervisor_restarted_mid_run_resumes_the_same_entry():
    """Crash recovery needs no resume path: a restarted Supervisor is handed
    the same signals and finds the same Entry (ADR 0013)."""
    interrupted, waiting = entry("one", run_id="a-run"), entry("two")
    signals = draining(interrupted, waiting)

    assert supervise(signals) == supervise(signals) == Resume(entry=interrupted)


def test_a_finished_entry_is_scanned_past_to_the_next():
    done, waiting = entry("one", run_id="a-run"), entry("two")

    assert supervise(draining(done, waiting, finished={"a-run"})) == Start(
        entry=waiting, predecessor=None
    )


def test_a_finished_entry_is_scanned_past_to_the_next_unfinished_run():
    done, running = entry("one", run_id="a-run"), entry("two", run_id="another-run")

    assert supervise(draining(done, running, finished={"a-run"})) == Resume(entry=running)


# Every Entry done is the empty Queue again, and answers the same way.


def test_a_queue_whose_every_entry_is_done_drains():
    first, second = entry("one", run_id="a-run"), entry("two", run_id="another-run")

    assert supervise(draining(first, second, finished={"a-run", "another-run"})) == DRAINED


def test_a_queue_whose_every_entry_is_done_idles_when_following():
    first, second = entry("one", run_id="a-run"), entry("two", run_id="another-run")

    assert supervise(following(first, second, finished={"a-run", "another-run"})) == IDLE


def test_the_entries_are_taken_in_the_order_they_are_given():
    """Queue order is id order, settled by whoever gathered the signals. The
    rule reads the sequence it was handed and sorts nothing itself."""
    first, second, third = entry("one"), entry("two"), entry("three")

    assert supervise(draining(first, second, third)).entry is first
