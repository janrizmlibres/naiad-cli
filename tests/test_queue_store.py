"""The Queue on disk: what an Entry carries, the order they come back in, and
what is read of the Run rather than stored.

An Entry records no status of its own, so the four things an
operator wants to know about one are asked of its Run here.
"""

import json
from dataclasses import replace

import pytest

from naiad.domain.decide import Finish
from naiad.domain.entry import Attachment, Entry
from naiad.domain.question import Question
from naiad.runtime.announcements import Announcements
from naiad.runtime.home import StorageError
from naiad.runtime.log import RunLog
from naiad.runtime.queue import (
    DONE,
    PARKED,
    RUNNING,
    WAITING,
    Queue,
    cancel,
    prune,
    status_of,
)
from naiad.runtime.records import EntryTurns, Notices, Waits
from naiad.runtime.run import RunStore


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    return path


@pytest.fixture
def queue(tmp_path):
    return Queue(tmp_path / "naiad" / "queue")


@pytest.fixture
def runs(tmp_path):
    return RunStore(tmp_path / "naiad" / "runs")


def entry(repo, **overrides):
    fields = dict(
        id="20260722-120000-feature-431",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        working_branch="MC-AGENT-8546",
        created_at="2026-07-22T12:00:00Z",
    )
    fields.update(overrides)
    return Entry(**fields)


def test_an_entry_carries_everything_kickoff_would_otherwise_be_told(queue, repo):
    queue.add(
        entry(
            repo,
            pinned_base="MC-AGENT-8000",
            start_state="grill",
            subject="docs/ticket.md",
            skip_gates=True,
        )
    )

    (reloaded,) = queue.all()
    assert reloaded.workflow_path == repo / "workflow.toml"
    assert reloaded.task == "add dark mode"
    assert reloaded.target_repo == repo
    assert reloaded.working_branch == "MC-AGENT-8546"
    assert reloaded.pinned_base == "MC-AGENT-8000"
    assert reloaded.start_state == "grill"
    assert reloaded.subject == "docs/ticket.md"
    assert reloaded.skip_gates is True


def test_an_entry_that_has_not_started_records_no_run(queue, repo):
    queue.add(entry(repo))

    assert queue.all()[0].run_id is None


def test_an_adoption_records_the_session_its_run_attaches_to(queue, repo):
    """An Adoption is an Entry marked to attach rather than spawn,
    and the mark is the session it joins."""
    queue.add(entry(repo, attachment=Attachment(tmux_pane="%42", claude_session_id="a-session")))

    (reloaded,) = queue.all()
    assert reloaded.attachment == Attachment(tmux_pane="%42", claude_session_id="a-session")


def test_an_adoption_that_could_not_gather_a_claude_session_id_still_attaches(queue, repo):
    """The id may be unknowable from inside a tool call, so the pane is the
    reliable key and the mark stands without the other."""
    queue.add(entry(repo, attachment=Attachment(tmux_pane="%42")))

    assert queue.all()[0].attachment == Attachment(tmux_pane="%42")


def test_an_entry_that_is_not_an_adoption_is_marked_with_no_attachment(queue, repo):
    queue.add(entry(repo))

    assert queue.all()[0].attachment is None


def test_entries_come_back_in_id_order_however_they_were_written(queue, repo):
    queue.add(entry(repo, id="20260722-130000-feature-2"))
    queue.add(entry(repo, id="20260722-120000-feature-1"))
    queue.add(entry(repo, id="20260722-140000-feature-3"))

    assert [held.id for held in queue.all()] == [
        "20260722-120000-feature-1",
        "20260722-130000-feature-2",
        "20260722-140000-feature-3",
    ]


def test_removing_an_entry_renumbers_nothing(queue, repo):
    """Entries are addressed by id and hold no position, so taking one out
    leaves every other one saying exactly what it said before."""
    queue.add(entry(repo, id="one"))
    queue.add(entry(repo, id="two"))
    queue.add(entry(repo, id="three"))
    before = {held.id: held for held in queue.all()}

    assert queue.remove("two") is True

    after = {held.id: held for held in queue.all()}
    assert list(after) == ["one", "three"]
    assert after == {name: before[name] for name in after}


def test_removing_an_entry_that_is_not_there_is_reported(queue, repo):
    queue.add(entry(repo))

    assert queue.remove("no-such-entry") is False


def test_an_entry_records_the_run_it_became(queue, repo):
    """The one thing that changes about an Entry, and the only field on it that
    says anything about a Run."""
    queued = queue.add(entry(repo))

    attached = queue.attach_run(queued, run_id="a-run")

    assert attached.run_id == "a-run"
    assert queue.all()[0].run_id == "a-run"


def test_recording_the_run_changes_nothing_else_about_the_entry(queue, repo):
    """Everything else was decided when the Entry was made, so a Supervisor
    writing the Entry again must not quietly restate any of it."""
    queued = queue.add(entry(repo, pinned_base="MC-AGENT-8000", start_state="grill"))

    queue.attach_run(queued, run_id="a-run")

    (reloaded,) = queue.all()
    assert reloaded == replace(queued, run_id="a-run")


def test_a_queue_rooted_inside_the_target_repository_is_refused(repo):
    """For the reason a Run's directory is: nothing Naiad owns may turn up in
    the pull request the work produces."""
    inside = Queue(repo / ".naiad" / "queue")

    with pytest.raises(StorageError) as caught:
        inside.add(entry(repo))

    assert "inside the target repository" in str(caught.value)
    assert list(repo.iterdir()) == []


def test_reusing_an_entry_id_is_refused(queue, repo):
    queue.add(entry(repo))

    with pytest.raises(StorageError) as caught:
        queue.add(entry(repo))

    assert "already exists" in str(caught.value)


def test_an_empty_queue_holds_nothing(queue):
    assert queue.all() == []


def test_an_entry_is_serialised_as_json_like_a_runs_metadata(queue, repo):
    queue.add(entry(repo))

    (document,) = queue.root.iterdir()
    assert json.loads(document.read_text())["task"] == "add dark mode"


def test_an_entry_file_that_cannot_be_read_is_reported_and_names_itself(queue, repo):
    """One file per Entry is storage an operator can see, so one they have
    truncated or hand-edited is a mistake they can make. Reading the Queue says
    which file rather than raising something the command cannot report."""
    queue.add(entry(repo))
    (document,) = queue.root.iterdir()
    document.write_text("{ not json")

    with pytest.raises(StorageError) as caught:
        queue.all()

    assert str(document) in str(caught.value)


# What became of an Entry is read of its Run: no Run means waiting,
# a finished Run log means done, a notice against the current Announcement
# means parked, and anything else is running.


def started(runs, repo, run_id="a-run"):
    return runs.create(
        run_id=run_id,
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )


def test_an_entry_with_no_run_is_waiting(runs, repo):
    assert status_of(entry(repo), runs) == WAITING


def test_an_entry_whose_run_is_under_way_is_running(runs, repo):
    run = started(runs, repo)
    Announcements(run.root).announce("implement")

    assert status_of(entry(repo, run_id=run.id), runs) == RUNNING


def test_an_entry_whose_run_has_been_notified_for_its_announcement_is_parked(runs, repo):
    run = started(runs, repo)
    announcement = Announcements(run.root).announce("handover")
    Notices(run.root).record_notified(announcement)

    assert status_of(entry(repo, run_id=run.id), runs) == PARKED


def test_an_entry_parked_after_its_waits_ran_out_is_still_read_as_parked(runs, repo):
    """The notification is recorded against the Announcement's latest Wait, and
    the Queue must read it with the same key or a parked Run shows as
    running."""
    run = started(runs, repo)
    announcement = Announcements(run.root).announce("handover")
    Waits(run.root).record(announcement, reason="a check", now=0.0, seconds=60.0)
    Notices(run.root).record_notified(announcement, wait_count=1)

    assert status_of(entry(repo, run_id=run.id), runs) == PARKED


def test_an_entry_notified_over_an_announcement_it_has_since_left_is_running_again(runs, repo):
    """A notice belongs to the Announcement it was made about. The agent
    announcing again is what re-arms the Run, and the Queue reads that rather
    than a status somebody wrote down."""
    run = started(runs, repo)
    Notices(run.root).record_notified(Announcements(run.root).announce("handover"))
    Announcements(run.root).announce("implement")

    assert status_of(entry(repo, run_id=run.id), runs) == RUNNING


def test_an_entry_whose_run_asked_a_question_and_was_escalated_is_parked(runs, repo):
    """A Question that ends in an Escalation is a Run needing a human, and it
    is notified against the Announcement carrying the Question."""
    run = started(runs, repo)
    asked = Announcements(run.root).ask(Question(text="which?", options=("a", "b")), state="grill")
    Notices(run.root).record_notified(asked)

    assert status_of(entry(repo, run_id=run.id), runs) == PARKED


def test_an_entry_whose_run_has_reached_a_terminal_state_is_done(runs, repo):
    run = started(runs, repo)
    announcement = Announcements(run.root).announce("done")
    RunLog(run.root).record(Finish(state="done"), seq=announcement.seq)

    assert status_of(entry(repo, run_id=run.id), runs) == DONE


def test_a_finished_run_that_was_notified_along_the_way_is_done_rather_than_parked(runs, repo):
    """Finishing is final: a Run that needed a human once and went on to end is
    over, however loudly it asked on the way."""
    run = started(runs, repo)
    announcement = Announcements(run.root).announce("done")
    Notices(run.root).record_notified(announcement)
    RunLog(run.root).record(Finish(state="done"), seq=announcement.seq)

    assert status_of(entry(repo, run_id=run.id), runs) == DONE


# Pruning. What a Prune takes is read through `status_of` rather than decided
# again here, so that what the listing calls done and what a Prune removes can
# never come apart.


def finished(runs, repo, run_id="a-run"):
    run = started(runs, repo, run_id=run_id)
    announcement = Announcements(run.root).announce("done")
    RunLog(run.root).record(Finish(state="done"), seq=announcement.seq)
    return run


def test_pruning_takes_the_done_entries_and_the_runs_they_became(queue, runs, repo):
    run = finished(runs, repo)
    queue.add(entry(repo, id="done-entry", run_id=run.id))

    pruned = prune(queue, runs)

    assert [taken.id for taken in pruned.removed] == ["done-entry"]
    assert queue.all() == []
    assert not run.root.exists()


def test_pruning_leaves_a_waiting_entry_where_it_is(queue, runs, repo):
    """Waiting is future work. Taking it would cancel something, which is what
    removing one by name is for."""
    queue.add(entry(repo, id="waiting-entry"))

    assert prune(queue, runs).removed == []

    assert [held.id for held in queue.all()] == ["waiting-entry"]


def test_pruning_leaves_a_running_entry_and_its_run_alone(queue, runs, repo):
    run = started(runs, repo)
    Announcements(run.root).announce("implement")
    queue.add(entry(repo, id="running-entry", run_id=run.id))

    assert prune(queue, runs).removed == []

    assert [held.id for held in queue.all()] == ["running-entry"]
    assert run.root.is_dir()


def test_pruning_leaves_a_parked_entry_and_its_run_alone(queue, runs, repo):
    """A parked Run is one asking for a human. It looks idle, but the work is
    not finished, and taking it would hide the request."""
    run = started(runs, repo)
    Notices(run.root).record_notified(Announcements(run.root).announce("handover"))
    queue.add(entry(repo, id="parked-entry", run_id=run.id))

    assert prune(queue, runs).removed == []

    assert [held.id for held in queue.all()] == ["parked-entry"]
    assert run.root.is_dir()


def test_pruning_takes_only_the_done_entries_out_of_a_mixed_queue(queue, runs, repo):
    queue.add(entry(repo, id="a-waiting-entry"))
    queue.add(entry(repo, id="b-done-entry", run_id=finished(runs, repo, run_id="done-run").id))
    parked = started(runs, repo, run_id="parked-run")
    Notices(parked.root).record_notified(Announcements(parked.root).announce("handover"))
    queue.add(entry(repo, id="c-parked-entry", run_id=parked.id))

    pruned = prune(queue, runs)

    assert [taken.id for taken in pruned.removed] == ["b-done-entry"]
    assert [held.id for held in queue.all()] == ["a-waiting-entry", "c-parked-entry"]


def test_pruning_takes_the_entry_before_the_run_so_a_failure_leaves_no_lie(
    queue, runs, repo, monkeypatch
):
    """The order that matters, seen from the failure it is chosen for. The
    Entry still counts as removed, because it was: one that vanished with no
    line naming it would be a removal the operator was never told about, and
    the orphan left behind is the separate fact the refusal states.
    """
    run = finished(runs, repo)
    queue.add(entry(repo, id="done-entry", run_id=run.id))

    def refuse(_self, _run_id):
        raise StorageError(f"run directory {run.root} cannot be removed (device busy)")

    monkeypatch.setattr(RunStore, "remove", refuse)

    pruned = prune(queue, runs)

    assert queue.all() == []
    assert [taken.id for taken in pruned.removed] == ["done-entry"]
    assert str(run.root) in "\n".join(pruned.failures)


def test_one_failed_run_removal_does_not_stop_the_rest(queue, runs, repo, monkeypatch):
    """Reported and gone past, rather than stopping: one stuck directory must
    not spare the whole backlog."""
    stubborn = finished(runs, repo, run_id="stubborn-run")
    willing = finished(runs, repo, run_id="willing-run")
    queue.add(entry(repo, id="a-entry", run_id=stubborn.id))
    queue.add(entry(repo, id="b-entry", run_id=willing.id))
    taking = RunStore.remove

    def refuse_one(self, run_id):
        if run_id == "stubborn-run":
            raise StorageError(f"run directory {stubborn.root} cannot be removed (device busy)")
        return taking(self, run_id)

    monkeypatch.setattr(RunStore, "remove", refuse_one)

    pruned = prune(queue, runs)

    assert [taken.id for taken in pruned.removed] == ["a-entry", "b-entry"]
    assert queue.all() == []
    assert not willing.root.exists()
    assert stubborn.root.is_dir()
    assert len(pruned.failures) == 1


def test_pruning_a_queue_holding_a_damaged_entry_refuses_before_taking_anything(
    queue, runs, repo
):
    """Read whole before anything is deleted, as a batch is queued whole: an
    Entry nobody can read might be the done one, and a Prune already under way
    could not be taken back."""
    run = finished(runs, repo)
    queue.add(entry(repo, id="done-entry", run_id=run.id))
    (queue.root / "damaged.json").write_text("{ not json")

    with pytest.raises(StorageError):
        prune(queue, runs)

    assert run.root.is_dir()
    assert (queue.root / "done-entry.json").exists()


# Orphaned Runs. A Run directory no Entry names is taken by a Prune when it
# reads done or parked, skipped and named when it reads running, and reported
# as a failure when it cannot be read at all.


def test_pruning_takes_a_done_orphaned_run(queue, runs, repo):
    orphan = finished(runs, repo, run_id="orphaned-run")

    pruned = prune(queue, runs)

    assert pruned.orphans == ["orphaned-run"]
    assert not orphan.root.exists()


def test_pruning_takes_a_parked_orphaned_run(queue, runs, repo):
    """Parked protects a Run someone will return to, and no one returns to an
    orphan: an Entry-less Run can never be ticked, answered or advanced, so its
    parking is permanent and protects nobody."""
    orphan = started(runs, repo, run_id="orphaned-run")
    Notices(orphan.root).record_notified(Announcements(orphan.root).announce("handover"))

    pruned = prune(queue, runs)

    assert pruned.orphans == ["orphaned-run"]
    assert not orphan.root.exists()


def test_pruning_leaves_a_running_orphan_and_names_it_by_path(queue, runs, repo):
    """Running cannot tell a live Session from a dead one that never announced,
    and Naiad never looks at tmux to find out. Liveness is the operator's fact,
    so the directory stays and its path is named, every Prune, until they act."""
    orphan = started(runs, repo, run_id="orphaned-run")
    Announcements(orphan.root).announce("implement")

    pruned = prune(queue, runs)

    assert pruned.orphans == []
    assert pruned.skipped == [str(orphan.root)]
    assert pruned.failures == []
    assert orphan.root.is_dir()


def test_a_run_an_entry_still_names_is_not_an_orphan(queue, runs, repo):
    """However its Run reads, an Entry naming it keeps it out of the orphan
    pass. A parked Run with its Entry is a Run asking for a human, and stays."""
    run = started(runs, repo, run_id="parked-run")
    Notices(run.root).record_notified(Announcements(run.root).announce("handover"))
    queue.add(entry(repo, id="parked-entry", run_id=run.id))

    pruned = prune(queue, runs)

    assert pruned.orphans == []
    assert pruned.skipped == []
    assert run.root.is_dir()


def test_an_unreadable_orphan_is_a_failure_and_the_rest_are_taken_anyway(queue, runs, repo):
    """Not deleting is the safe act, so one unreadable directory is reported by
    path and must not spare the other orphans."""
    damaged = started(runs, repo, run_id="damaged-run")
    (damaged.root / "state.json").write_text("{ not json")
    willing = finished(runs, repo, run_id="willing-run")

    pruned = prune(queue, runs)

    assert pruned.orphans == ["willing-run"]
    assert not willing.root.exists()
    assert damaged.root.is_dir()
    assert str(damaged.root) in "\n".join(pruned.failures)


def test_an_orphan_that_would_not_go_is_a_failure_naming_its_path(queue, runs, repo, monkeypatch):
    orphan = finished(runs, repo, run_id="orphaned-run")

    def refuse(_self, _run_id):
        raise StorageError(f"run directory {orphan.root} cannot be removed (device busy)")

    monkeypatch.setattr(RunStore, "remove", refuse)

    pruned = prune(queue, runs)

    assert pruned.orphans == []
    assert str(orphan.root) in "\n".join(pruned.failures)


def test_an_entry_that_was_already_gone_is_not_claimed_as_taken(queue, runs, repo, monkeypatch):
    """Removal answers False when there was no such Entry, and a Prune has to
    believe it. Counting one anyway would print a line for a removal this Prune
    did not make — and would delete a Run whoever removed the Entry by name has
    only cancelled, which is theirs to keep reading until the next Prune.
    """
    run = finished(runs, repo)
    queue.add(entry(repo, id="done-entry", run_id=run.id))
    monkeypatch.setattr(Queue, "remove", lambda _self, _entry_id: False)

    pruned = prune(queue, runs)

    assert pruned.removed == []
    assert pruned.failures == []
    assert run.root.is_dir()


# Cancelling. Removing an Entry by name ends the Run it became, which releases
# that Run's Session. The Run directory stays: it is the diagnostic,
# and only a Prune ever deletes one.


def test_cancelling_takes_the_entry_out_and_ends_its_run(queue, runs, repo):
    run = started(runs, repo)
    run.attach_session(tmux_session="naiad-a-run", tmux_pane="%7")
    Announcements(run.root).announce("implement")
    queue.add(entry(repo, id="an-entry", run_id=run.id))

    cancelled = cancel(queue, runs, "an-entry")

    assert cancelled.entry.id == "an-entry"
    assert cancelled.run.tmux_pane == "%7"
    assert queue.all() == []
    assert run.root.is_dir()
    assert RunLog(run.root).ended() is True


def test_a_cancelled_run_reads_done_so_the_next_prune_takes_the_orphan(queue, runs, repo):
    """The whole point of recording the ending rather than deriving it: one
    reading answers the Session release and the Prune alike, so a cancelled Run
    does not sit in the 'reads as running, yours to judge' limbo for ever."""
    run = started(runs, repo)
    Announcements(run.root).announce("implement")
    queue.add(entry(repo, id="an-entry", run_id=run.id))
    cancel(queue, runs, "an-entry")

    pruned = prune(queue, runs)

    assert pruned.orphans == [run.id]
    assert not run.root.exists()


def test_the_cancellation_says_where_the_run_stood(queue, runs, repo):
    run = started(runs, repo)
    Announcements(run.root).announce("implement")
    queue.add(entry(repo, id="an-entry", run_id=run.id))

    cancel(queue, runs, "an-entry")

    (line,) = [entry for entry in RunLog(run.root).entries() if entry.kind == "cancelled"]
    assert line.state == "implement"


def test_cancelling_an_entry_that_never_started_takes_the_entry_alone(queue, runs, repo):
    """Waiting is an Entry with no Run. There is nothing to end and no Session
    to release, so removal is what it always was."""
    queue.add(entry(repo, id="waiting-entry"))

    cancelled = cancel(queue, runs, "waiting-entry")

    assert cancelled.entry.id == "waiting-entry"
    assert cancelled.run is None
    assert queue.all() == []


def test_cancelling_an_entry_whose_run_directory_has_gone_still_takes_the_entry(
    queue, runs, repo
):
    """A Run nobody can find holds no Session to release, so its absence must
    not trap the Entry naming it in the Queue."""
    queue.add(entry(repo, id="an-entry", run_id="a-run-that-was-deleted"))

    cancelled = cancel(queue, runs, "an-entry")

    assert cancelled.run is None
    assert queue.all() == []


def test_cancelling_a_run_that_had_already_ended_writes_no_second_ending(queue, runs, repo):
    """Its Session was released when it finished. A second line would say the
    operator called off work that was already over."""
    run = finished(runs, repo)
    queue.add(entry(repo, id="done-entry", run_id=run.id))

    cancelled = cancel(queue, runs, "done-entry")

    assert [line.kind for line in RunLog(run.root).entries()] == ["finished"]
    assert queue.all() == []
    # No line was written, so no Run comes back: a caller reporting this field
    # must not claim a cancellation this act did not make.
    assert cancelled.run is None


def test_a_cancellation_that_cannot_be_written_leaves_the_entry_where_it_is(
    queue, runs, repo, monkeypatch
):
    """The order this turns on, seen from the failure it is chosen for: the
    ending goes first, so a refusal cannot leave a Run orphaned and still
    driving its Session — which is the whole failure being removed here."""
    run = started(runs, repo)
    Announcements(run.root).announce("implement")
    queue.add(entry(repo, id="an-entry", run_id=run.id))

    def refuse(_self, *, state):
        raise OSError("read-only file system")

    monkeypatch.setattr(RunLog, "record_cancellation", refuse)

    with pytest.raises(StorageError):
        cancel(queue, runs, "an-entry")

    assert [held.id for held in queue.all()] == ["an-entry"]


def test_cancelling_an_entry_that_is_not_there_answers_nothing(queue, runs, repo):
    """False from `remove` in a different shape: the caller says so rather than
    guessing, and no Run is touched on the way."""
    assert cancel(queue, runs, "no-such-entry") is None


def test_removing_an_entry_takes_its_turn_sidecar_with_it(queue, repo):
    """The sidecar is owned by the Entry's lifecycle: an Entry removed before
    its Run started leaves no record waiting for a Run that will never come."""
    added = queue.add(entry(repo))
    EntryTurns(queue.root, added.id).record_end()

    assert queue.remove(added.id) is True
    assert not EntryTurns(queue.root, added.id).path.exists()


def test_a_turn_sidecar_beside_an_entry_is_not_read_as_an_entry(queue, repo):
    added = queue.add(entry(repo))
    EntryTurns(queue.root, added.id).record_end()

    assert [found.id for found in queue.all()] == [added.id]


def test_the_entry_a_run_became_is_found_from_the_run_id(tmp_path, repo):
    queue = Queue(tmp_path / "queue")
    started = queue.add(entry(repo, id="first", working_branch=None))
    queue.attach_run(started, run_id="first-run")
    queue.add(entry(repo, id="second", working_branch="other"))

    assert queue.entry_of("first-run").id == "first"


def test_a_run_no_entry_became_has_no_entry(tmp_path, repo):
    queue = Queue(tmp_path / "queue")
    queue.add(entry(repo, id="waiting"))

    assert queue.entry_of("orphaned-run") is None
