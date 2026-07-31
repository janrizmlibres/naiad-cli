"""The Supervisor's loop: what it does with each Action, and what ends it.

The rules are covered in tests/test_supervise.py. What is pinned here is the
loop, in the shape tests/test_watch.py already pins the watch loop — sleeping
and reporting injected so that nothing waits on a clock, and the operator's
Ctrl-C standing by so that a loop meant to keep going can be shown to keep
going without running forever.

Starting a Run and driving it are handed in rather than done for real. Driving
one for real would need a fake tmux and a fake agent, and green tests over a
system that does not work is the failure this project is avoiding: what belongs
here is which Run was started, which was driven, and in what order.
"""

import pytest

from naiad.cli.supervisor import supervise_queue
from naiad.domain.decide import Finish
from naiad.domain.entry import Entry
from naiad.runtime.home import StorageError
from naiad.runtime.log import RunLog
from naiad.runtime.queue import Queue
from naiad.runtime.run import RunStore


class Interrupted(Exception):
    """Stands in for the operator's Ctrl-C, so that a loop which is meant to
    keep going can be shown to keep going without running forever."""


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    (path / "workflow.toml").write_text('name = "feature"\n')
    return path


@pytest.fixture
def queue(tmp_path):
    return Queue(tmp_path / "naiad" / "queue")


@pytest.fixture
def runs(tmp_path):
    return RunStore(tmp_path / "naiad" / "runs")


def queued(queue, repo, identifier, **overrides):
    fields = dict(
        id=identifier,
        workflow_path=repo / "workflow.toml",
        task=f"task {identifier}",
        target_repo=repo,
        working_branch=f"MC-AGENT-{identifier}",
        created_at="2026-07-22T12:00:00Z",
    )
    fields.update(overrides)
    return queue.add(Entry(**fields))


class Supervision:
    """Starting a Run and driving it, without a session or a tick.

    The Runs it creates are real, because that is what a Resume loads and what
    a finished log is read off. What it fakes is the session the Run would be
    driven in, and the ticking.
    """

    def __init__(self, runs, *, finishes=True, at_most=4):
        self.runs = runs
        self.finishes = finishes
        self.at_most = at_most
        self.started = []
        self.driven = []

    def start(self, entry, predecessor):
        self.started.append((entry.id, predecessor))
        # Counted off the store rather than off this object, so that a second
        # Supervision — a restarted Supervisor — does not name a Run the first
        # one already created.
        return self.runs.create(
            run_id=f"run-{len(self.runs.all()) + 1}",
            workflow_path=entry.workflow_path,
            task=entry.task,
            target_repo=entry.target_repo,
            created_at=entry.created_at,
            working_branch=entry.working_branch,
            predecessor=predecessor,
        )

    def drive(self, run):
        self.driven.append(run.id)
        if len(self.driven) > self.at_most:
            raise AssertionError("the supervisor drove more runs than the queue holds")
        if not self.finishes:
            # What watching a parked Run does: it never returns, because the
            # Run must stay tickable until a human's typing revives it.
            raise Interrupted
        RunLog(run.root).record(Finish(state="done"))


def supervising(queue, runs, supervision, *, following=False, naps_allowed=2, waking=None):
    """Run the Supervisor with the operator's Ctrl-C standing by. A loop that is
    supposed to end on its own never reaches it.

    waking is called on each nap, for the test where something happens to the
    Queue while the Supervisor is following it.
    """
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        if waking is not None:
            waking()
        if len(slept) >= naps_allowed:
            raise Interrupted

    supervise_queue(
        queue=queue,
        runs=runs,
        start=supervision.start,
        drive=supervision.drive,
        following=following,
        sleep=sleep,
        report=lambda _message: None,
    )
    return slept


# Drain or follow is the only difference between the two modes.


def test_draining_an_empty_queue_returns(queue, runs):
    """The operator gets their prompt back rather than having to remember to
    interrupt something that has finished the work."""
    supervision = Supervision(runs)

    assert supervising(queue, runs, supervision) == []
    assert supervision.started == []


def test_following_an_empty_queue_comes_round_again(queue, runs):
    """Entries added later are the point of following, and a loop that had
    returned would never see one."""
    with pytest.raises(Interrupted):
        supervising(queue, runs, Supervision(runs), following=True)


def test_draining_returns_once_every_entry_is_done(queue, runs, repo):
    queued(queue, repo, "one")
    supervision = Supervision(runs)

    assert supervising(queue, runs, supervision) == []
    assert supervision.driven == ["run-1"]


# Starting an Entry: the Run is created, recorded on the Entry, then driven.


def test_a_start_is_followed_by_driving_the_run_it_created(queue, runs, repo):
    entry = queued(queue, repo, "one")
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    assert supervision.started == [(entry.id, None)]
    assert supervision.driven == ["run-1"]


def test_a_started_entry_is_handed_the_predecessor_the_rules_resolved(queue, runs, repo):
    entry = queued(queue, repo, "one", pinned_base="MC-AGENT-8000")
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    assert supervision.started == [(entry.id, "MC-AGENT-8000")]
    assert runs.load("run-1").predecessor == "MC-AGENT-8000"


def test_the_run_is_recorded_on_the_entry_before_it_is_driven(queue, runs, repo):
    """What a restarted Supervisor reads to find the same Entry again. Recorded
    after driving began, it would be lost by exactly the interruption it is for."""
    queued(queue, repo, "one")
    supervision = Supervision(runs)
    recorded = []
    driving = supervision.drive

    def drive(run):
        recorded.append(queue.all()[0].run_id)
        driving(run)

    supervision.drive = drive
    supervising(queue, runs, supervision)

    assert recorded == ["run-1"]
    assert queue.all()[0].run_id == "run-1"


# The Queue in order, which is the whole point.


def test_two_queued_entries_are_run_one_after_the_other(queue, runs, repo):
    first, second = queued(queue, repo, "one"), queued(queue, repo, "two")
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    assert supervision.started == [(first.id, None), (second.id, None)]
    assert supervision.driven == ["run-1", "run-2"]


def test_a_run_that_never_finishes_holds_the_queue(queue, runs, repo):
    """A parked Run blocks (ADR 0012), and it costs no code: watching one never
    returns, so nothing after it is ever reached."""
    queued(queue, repo, "one")
    queued(queue, repo, "two")
    supervision = Supervision(runs, finishes=False)

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision)

    assert len(supervision.started) == 1


def test_an_entry_added_while_following_is_picked_up(queue, runs, repo):
    """Following is for the operator who queues something after the Supervisor
    started, so the Entries are gathered afresh each time round."""
    supervision = Supervision(runs)
    added = []

    def add_one():
        if not added:
            added.append(queued(queue, repo, "one"))

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision, following=True, waking=add_one)

    assert supervision.started == [("one", None)]
    assert supervision.driven == ["run-1"]


# Crash recovery: there is no resume path, because there is no state to resume.


def test_a_supervisor_restarted_mid_run_drives_the_same_run(queue, runs, repo):
    """It finds the same Entry and watches its Run again, which the existing
    watch handles in both directions (ADR 0013)."""
    queued(queue, repo, "one")
    queued(queue, repo, "two")
    interrupted = Supervision(runs, finishes=False)
    with pytest.raises(Interrupted):
        supervising(queue, runs, interrupted)

    resumed = Supervision(runs)
    supervising(queue, runs, resumed)

    # The first Entry's Run is driven again rather than started again, and only
    # the second Entry is ever started.
    assert resumed.driven[0] == "run-1"
    assert resumed.started == [("two", None)]


def test_a_supervisor_restarted_after_a_run_finished_moves_on(queue, runs, repo):
    """Watching reports that a finished Run has finished and returns, so the
    scan passes it and reaches the next Entry."""
    queued(queue, repo, "one")
    supervising(queue, runs, Supervision(runs))
    queued(queue, repo, "two")

    second = Supervision(runs)
    supervising(queue, runs, second)

    assert second.started == [("two", None)]


def test_an_entry_whose_run_has_gone_missing_is_reported(queue, runs, repo):
    """Nothing left on disk says the Run ended, so the scan keeps choosing it.
    Said out loud rather than spun on, because only the operator can decide
    whether to remove the Entry or put the Run back."""
    queued(queue, repo, "one", run_id="a-run-that-was-deleted")

    with pytest.raises(StorageError) as caught:
        supervising(queue, runs, Supervision(runs))

    assert "a-run-that-was-deleted" in str(caught.value)
