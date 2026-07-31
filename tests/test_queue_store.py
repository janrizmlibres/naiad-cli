"""The Queue on disk: what an Entry carries, the order they come back in, and
what is read of the Run rather than stored.

An Entry records no status of its own (ADR 0013), so the four things an
operator wants to know about one are asked of its Run here.
"""

import json
from dataclasses import replace

import pytest

from naiad.domain.decide import Finish
from naiad.domain.entry import Entry
from naiad.domain.question import Question
from naiad.runtime.announcements import Announcements
from naiad.runtime.home import StorageError
from naiad.runtime.log import RunLog
from naiad.runtime.queue import DONE, PARKED, RUNNING, WAITING, Queue, status_of
from naiad.runtime.records import Notices
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
    says anything about a Run (ADR 0013)."""
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


# What became of an Entry is read of its Run (ADR 0013): no Run means waiting,
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


