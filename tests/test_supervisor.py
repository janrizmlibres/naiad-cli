"""The Supervisor's loop: what it does with each Action, and what ends it.

The rules are covered in tests/test_supervise.py. What is pinned here is the
loop — sleeping and reporting injected so that nothing waits on a clock, and
the operator's Ctrl-C standing by so that a loop meant to keep going can be
shown to keep going without running forever.

Starting a Run and ticking one are handed in rather than done for real.
Ticking one for real would need a fake tmux and a fake agent, and green tests
over a system that does not work is the failure this project is avoiding: what
belongs here is which Run was started, which was ticked, and in what order.
"""

from pathlib import Path

import pytest

from naiad.cli.supervisor import supervise_queue
from naiad.domain.decide import Finish
from naiad.domain.entry import Attachment, Entry
from naiad.runtime.announcements import Announcements
from naiad.runtime.home import StorageError
from naiad.runtime.log import RunLog
from naiad.runtime.queue import Queue
from naiad.runtime.records import Children
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
def other_repo(tmp_path):
    path = tmp_path / "other-repo"
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
        working_branch=f"TASK-{identifier}",
        created_at="2026-07-22T12:00:00Z",
    )
    fields.update(overrides)
    return queue.add(Entry(**fields))


class Supervision:
    """Starting a Run and ticking it, without a session or a clock.

    The Runs it creates are real, because that is what a Resume loads and what
    a finished log is read off. What it fakes is the session the Run would be
    ticked in: a tick finishes its Run unless the Run is named as one that
    never does — which is what a parked Run looks like to the loop, a Run that
    is ticked and ticked and never ends.
    """

    def __init__(self, runs, *, never_finishes=(), declares=None, at_most=20):
        self.runs = runs
        self.never_finishes = set(never_finishes)
        # Which Runs declare a Derived branch when ticked, and what name: what
        # the agent at the head of a branchless Run does with `naiad branch`.
        self.declares = declares or {}
        self.at_most = at_most
        self.started = []
        self.ticked = []

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
            # Which way this Entry's Run met its session, carried the way the
            # real wiring carries it (naiad.cli.kickoff.start_entry): an Entry
            # marked to attach becomes an adopted Run. Kept so that a test
            # about an Adoption is about one, rather than passing whether or
            # not the mark is there.
            adopted=entry.attachment is not None,
        )

    def tick(self, run):
        self.ticked.append(run.id)
        if len(self.ticked) > self.at_most:
            raise AssertionError("the supervisor ticked more than the test allows")
        if run.id in self.declares and run.working_branch is None:
            run.working_branch = self.declares[run.id]
            run.save()
        if run.id in self.never_finishes:
            return
        RunLog(run.root).record(Finish(state="done"))


def supervising(
    queue,
    runs,
    supervision,
    *,
    following=False,
    naps_allowed=8,
    waking=None,
    ceiling=None,
    reports=None,
):
    """Run the Supervisor with the operator's Ctrl-C standing by. A loop that is
    supposed to end on its own never reaches it.

    waking is called on each nap, for the test where something happens to the
    Queue while the Supervisor is following it. reports, when given, collects
    what the Supervisor told the operator.
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
        tick=supervision.tick,
        following=following,
        sleep=sleep,
        report=(lambda _message: None) if reports is None else reports.append,
        ceiling=ceiling,
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

    supervising(queue, runs, supervision)

    assert supervision.ticked == ["run-1"]


# Starting an Entry: the Run is created, recorded on the Entry, then ticked.


def test_a_start_is_followed_by_ticking_the_run_it_created(queue, runs, repo):
    entry = queued(queue, repo, "one")
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    assert supervision.started == [(entry.id, None)]
    assert supervision.ticked == ["run-1"]


def test_a_started_entry_is_handed_the_predecessor_the_rules_resolved(queue, runs, repo):
    entry = queued(queue, repo, "one", pinned_base="TASK-8000")
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    assert supervision.started == [(entry.id, "TASK-8000")]
    assert runs.load("run-1").predecessor == "TASK-8000"


def test_the_run_is_recorded_on_the_entry_before_it_is_ticked(queue, runs, repo):
    """What a restarted Supervisor reads to find the same Entry again. Recorded
    after ticking began, it would be lost by exactly the interruption it is for."""
    queued(queue, repo, "one")
    supervision = Supervision(runs)
    recorded = []
    ticking = supervision.tick

    def tick(run):
        recorded.append(queue.all()[0].run_id)
        ticking(run)

    supervision.tick = tick
    supervising(queue, runs, supervision)

    assert recorded == ["run-1"]
    assert queue.all()[0].run_id == "run-1"


# Within a repository the Queue is in order, which is the whole point.


def test_two_entries_for_one_repository_are_run_one_after_the_other(queue, runs, repo):
    first, second = queued(queue, repo, "one"), queued(queue, repo, "two")
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    # The second Entry stands on the first's Working branch, resolved by the
    # rules and carried through the loop untouched.
    assert supervision.started == [(first.id, None), (second.id, first.working_branch)]
    assert supervision.ticked == ["run-1", "run-2"]


def test_a_run_that_never_finishes_holds_its_lane(queue, runs, repo):
    """A parked Run blocks its lane: behind it, the
    same repository's next Entry is never started."""
    queued(queue, repo, "one")
    queued(queue, repo, "two")
    supervision = Supervision(runs, never_finishes={"run-1"})

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision)

    assert len(supervision.started) == 1
    assert set(supervision.ticked) == {"run-1"}


# Repositories are lanes, ticked in turn within one pass.


def test_entries_for_two_repositories_run_at_the_same_time(queue, runs, repo, other_repo):
    """The pass ticks every lane's live Run once: a Run still working in one
    repository is interleaved with, not ahead of, the other repository's. A
    pass starts one Run, so the other repository's starts on the next."""
    queued(queue, repo, "one")
    queued(queue, other_repo, "two")
    supervision = Supervision(runs, never_finishes={"run-1"})

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision)

    assert supervision.started == [("one", None), ("two", None)]
    # The parked lane keeps being ticked after the other lane's Run finished.
    assert supervision.ticked[:4] == ["run-1", "run-1", "run-2", "run-1"]


def test_a_lane_that_parks_does_not_stop_another_repository_finishing(
    queue, runs, repo, other_repo
):
    """Parked at review in one repository,
    the Queue still works through the whole of another repository's lane."""
    queued(queue, repo, "a-parked")
    first = queued(queue, other_repo, "b-first")
    second = queued(queue, other_repo, "c-second")
    supervision = Supervision(runs, never_finishes={"run-1"})

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision)

    # The other repository's lane ran both its Entries in order, stacked.
    assert supervision.started == [
        ("a-parked", None),
        (first.id, None),
        (second.id, first.working_branch),
    ]


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
    assert supervision.ticked == ["run-1"]


# The Predecessor resolves through Runs: a preceding Entry whose own
# record carries no branch yields the branch its Run declared.


def test_the_next_entry_stands_on_the_branch_the_preceding_run_declared(queue, runs, repo):
    """The stacking chain works for Derived branches exactly as for given ones:
    the declared name is read off the Run, resolved by the rules, and recorded
    on the next Run for its Prompts to render."""
    first = queued(queue, repo, "one", working_branch=None)
    second = queued(queue, repo, "two")
    supervision = Supervision(runs, declares={"run-1": "feat/dark-mode"})

    supervising(queue, runs, supervision)

    assert supervision.started == [(first.id, None), (second.id, "feat/dark-mode")]
    assert runs.load("run-2").predecessor == "feat/dark-mode"


def test_a_run_that_never_declared_contributes_no_predecessor(queue, runs, repo):
    """A branchless Entry whose Run never recorded a branch — it never reached
    a head — contributes none, exactly as a missing Predecessor renders."""
    first = queued(queue, repo, "one", working_branch=None)
    second = queued(queue, repo, "two")
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    assert supervision.started == [(first.id, None), (second.id, None)]


def test_resolution_continues_past_an_undeclared_run_to_the_branch_before_it(queue, runs, repo):
    """Walked past rather than stopped at: behind an Entry with no branch
    anywhere, the next Entry still stands on the nearest branch the lane holds."""
    first = queued(queue, repo, "a-first")
    headless = queued(queue, repo, "b-headless", working_branch=None)
    third = queued(queue, repo, "c-third")
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    assert supervision.started == [
        (first.id, None),
        (headless.id, first.working_branch),
        (third.id, first.working_branch),
    ]


# An Adoption is an Entry like any other: it waits its Lane's turn and jumps
# nothing.


def test_an_adoption_behind_a_live_run_in_its_lane_waits_for_it(queue, runs, repo):
    """It attaches when its turn comes. Started sooner it would put a second
    agent into a working tree a Run is already live in — which is the single
    thing one Run per working tree exists to prevent, and the session an
    Adoption would be typing into is the human's own."""
    queued(queue, repo, "one")
    queued(queue, repo, "two", attachment=Attachment(tmux_pane="%7"))
    supervision = Supervision(runs, never_finishes={"run-1"})

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision)

    assert supervision.started == [("one", None)]
    # Nothing joined the human's session: the only Run there is spawned one.
    assert [run.adopted for run in runs.all()] == [False]


def test_an_adoption_starts_once_the_run_ahead_of_it_finishes(queue, runs, repo):
    first = queued(queue, repo, "one")
    adoption = queued(queue, repo, "two", attachment=Attachment(tmux_pane="%7"))
    supervision = Supervision(runs)

    supervising(queue, runs, supervision)

    assert supervision.started == [(first.id, None), (adoption.id, first.working_branch)]
    assert runs.load("run-2").adopted is True


def test_another_lane_proceeds_beside_an_adoption_waiting_its_turn(
    queue, runs, repo, other_repo
):
    queued(queue, repo, "a-parked")
    queued(queue, repo, "b-adoption", attachment=Attachment(tmux_pane="%7"))
    elsewhere = queued(queue, other_repo, "c-elsewhere")
    supervision = Supervision(runs, never_finishes={"run-1"})

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision)

    assert supervision.started == [("a-parked", None), (elsewhere.id, None)]
    assert [run.adopted for run in runs.all()] == [False, False]


# Crash recovery: there is no resume path, because there is no state to resume.


def test_a_supervisor_restarted_mid_run_ticks_the_same_run(queue, runs, repo):
    """It finds the same Entry and ticks its Run again."""
    first = queued(queue, repo, "one")
    queued(queue, repo, "two")
    interrupted = Supervision(runs, never_finishes={"run-1"})
    with pytest.raises(Interrupted):
        supervising(queue, runs, interrupted)

    resumed = Supervision(runs)
    supervising(queue, runs, resumed)

    # The first Entry's Run is ticked again rather than started again, and
    # only the second Entry is ever started.
    assert resumed.ticked[0] == "run-1"
    assert resumed.started == [("two", first.working_branch)]


def test_a_supervisor_restarted_after_a_run_finished_moves_on(queue, runs, repo):
    """A finished Run's Entry is scanned past, so the lane reaches the next
    Entry rather than ticking a Run that is over."""
    first = queued(queue, repo, "one")
    supervising(queue, runs, Supervision(runs))
    queued(queue, repo, "two")

    second = Supervision(runs)
    supervising(queue, runs, second)

    assert second.started == [("two", first.working_branch)]
    assert second.ticked == ["run-2"]


def test_an_entry_whose_run_has_gone_missing_is_reported(queue, runs, repo):
    """Nothing left on disk says the Run ended, so the scan keeps choosing it.
    Said out loud rather than spun on, because only the operator can decide
    whether to remove the Entry or put the Run back."""
    queued(queue, repo, "one", run_id="a-run-that-was-deleted")

    with pytest.raises(StorageError) as caught:
        supervising(queue, runs, Supervision(runs))

    assert "a-run-that-was-deleted" in str(caught.value)


# A Child is an Entry like any other, in a working tree of its own: a Lane of
# its own, started beside its live Parent.


def test_a_child_starts_in_its_own_lane_beside_its_live_parent(queue, runs, repo, other_repo):
    queued(queue, repo, "1-parent")
    queued(queue, other_repo, "2-child", parent="run-1")
    supervision = Supervision(runs, never_finishes={"run-1"})

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision)

    assert [started for started, _ in supervision.started] == ["1-parent", "2-child"]
    assert "run-1" in supervision.ticked[supervision.ticked.index("run-2"):]


def test_starting_a_child_records_its_run_on_its_parents_children_record(
    queue, runs, repo, other_repo
):
    queued(queue, repo, "parent")
    supervision = Supervision(runs, never_finishes={"run-1"})
    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision, naps_allowed=1)
    Children(runs.root_for("run-1")).record_spawn("child")
    queued(queue, other_repo, "child", parent="run-1")

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision, naps_allowed=1)

    (child,) = Children(runs.root_for("run-1")).all()
    assert (child.entry_id, child.run_id) == ("child", "run-2")


# Capacity: the ceiling holds back starting, never ticking.

JOINING = """
name = "fan-out"

[[states]]
name = "implement"
prompt = "take in {children}"
join = true

[[states]]
name = "done"
terminal = true
"""


def test_at_the_ceiling_a_waiting_entry_is_not_started(queue, runs, repo, other_repo):
    queued(queue, repo, "one")
    queued(queue, other_repo, "two")
    supervision = Supervision(runs, never_finishes={"run-1"})

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision, ceiling=1)

    assert supervision.started == [("one", None)]
    assert set(supervision.ticked) == {"run-1"}


def test_the_reason_nothing_starts_is_reported_once_not_every_pass(
    queue, runs, repo, other_repo
):
    queued(queue, repo, "one")
    queued(queue, other_repo, "two")
    supervision = Supervision(runs, never_finishes={"run-1"})
    reports = []

    with pytest.raises(Interrupted):
        supervising(queue, runs, supervision, ceiling=1, reports=reports)

    assert len([report for report in reports if "ceiling" in report]) == 1


def test_a_parent_held_at_its_join_does_not_keep_its_child_from_a_ceiling_of_one(
    queue, runs, repo, other_repo
):
    (repo / "workflow.toml").write_text(JOINING)
    queued(queue, repo, "1-parent", start_state="implement")
    supervision = Supervision(runs, never_finishes={"run-1", "run-2"})

    def spawning(run):
        supervision.tick(run)
        if run.id == "run-1" and not Children(run.root).all():
            Children(run.root).record_spawn("2-child", worktree=other_repo)
            queued(queue, other_repo, "2-child", parent="run-1")
            Announcements(run.root).announce("implement")

    with pytest.raises(Interrupted):
        supervise_queue(
            queue=queue,
            runs=runs,
            start=supervision.start,
            tick=spawning,
            following=False,
            sleep=_interrupting_after(4),
            report=lambda _message: None,
            ceiling=1,
        )

    assert [started for started, _ in supervision.started] == ["1-parent", "2-child"]


def _interrupting_after(naps):
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        if len(slept) >= naps:
            raise Interrupted

    return sleep
