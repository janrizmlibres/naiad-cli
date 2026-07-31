"""Adding one Entry, and everything that is refused before it exists.

Every failure that used to happen at kickoff happens here, on the trade the
missing-Subject refusal already makes: whoever is adding the Entry is standing
right there and pays the error message only, rather than finding out at three
in the morning.
"""

import pytest

from naiad.cli.enqueue import BranchAlreadyClaimed, enqueue
from naiad.cli.refusals import ADD_COMMAND, MissingSubject, MissingWorkingBranch
from naiad.domain.transitions import UnknownState
from naiad.domain.workflow import WorkflowError
from naiad.runtime.queue import Queue
from naiad.runtime.run import RunStore

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "implement"
prompt = "/implement the ticket at {subject}"
clear = true

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    (path / "workflow.toml").write_text(WORKFLOW)
    return path


@pytest.fixture
def other_repo(tmp_path):
    path = tmp_path / "other-repo"
    path.mkdir()
    (path / "workflow.toml").write_text(WORKFLOW)
    return path


@pytest.fixture
def queue(tmp_path):
    return Queue(tmp_path / "naiad" / "queue")


def add(repo, queue, **overrides):
    fields = dict(
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        working_branch="MC-AGENT-8546",
        queue=queue,
        entry_id="20260722-120000-feature-431",
        created_at="2026-07-22T12:00:00Z",
        # Which line the refusals quote back. Both entrances enqueue, so there
        # is no default to fall back on; these tests are the queueing one's.
        how=ADD_COMMAND,
    )
    fields.update(overrides)
    return enqueue(**fields)


def test_an_entry_joins_the_queue_carrying_what_kickoff_would_be_told(repo, queue):
    added = add(
        repo,
        queue,
        pinned_base="MC-AGENT-8000",
        start_state="implement",
        subject="docs/ticket.md",
        skip_gates=True,
    )

    (queued,) = queue.all()
    assert queued == added
    assert queued.task == "add dark mode"
    assert queued.target_repo == repo
    assert queued.working_branch == "MC-AGENT-8546"
    assert queued.pinned_base == "MC-AGENT-8000"
    assert queued.start_state == "implement"
    assert queued.subject == "docs/ticket.md"
    assert queued.skip_gates is True


def test_adding_an_entry_supervises_nothing(repo, queue, tmp_path):
    """The command an agent inside a session uses. It starts no Run and opens
    no session, because a tool call that becomes a process blocking for hours
    is the failure it exists to avoid."""
    added = add(repo, queue)

    assert added.run_id is None
    assert RunStore(tmp_path / "naiad" / "runs").all() == []


def test_an_entry_with_no_working_branch_is_refused(repo, queue):
    with pytest.raises(MissingWorkingBranch) as caught:
        add(repo, queue, working_branch=None)

    assert "--branch" in str(caught.value)
    assert queue.all() == []


def test_a_working_branch_already_claimed_in_the_same_repository_is_refused(repo, queue):
    """The subtle one: without it two Entries silently share a branch, and
    because checking out a branch that exists is idempotent the second stacks
    into the first invisibly."""
    add(repo, queue, entry_id="one")

    with pytest.raises(BranchAlreadyClaimed) as caught:
        add(repo, queue, entry_id="two", task="something else")

    assert "MC-AGENT-8546" in str(caught.value)
    assert "one" in str(caught.value)
    assert [held.id for held in queue.all()] == ["one"]


def test_two_entries_for_different_repositories_may_share_a_working_branch(
    repo, other_repo, queue
):
    """A branch name from another repository is not a fact about this one."""
    add(repo, queue, entry_id="one")
    add(other_repo, queue, entry_id="two", workflow_path=other_repo / "workflow.toml")

    assert [held.id for held in queue.all()] == ["one", "two"]


def test_the_same_repository_reached_by_another_path_still_claims_its_branch(repo, queue):
    """The claim is per repository, so which spelling of the path an operator
    typed cannot be what decides it: `.` and `../repo` are one repository, and
    a refusal that missed the second is the silent branch-sharing this check
    exists to prevent."""
    add(repo, queue, entry_id="one")

    with pytest.raises(BranchAlreadyClaimed):
        add(repo, queue, entry_id="two", target_repo=repo / "." / ".." / repo.name)

    assert [held.id for held in queue.all()] == ["one"]


def test_a_branch_is_free_again_once_the_entry_claiming_it_is_removed(repo, queue):
    add(repo, queue, entry_id="one")
    queue.remove("one")

    assert add(repo, queue, entry_id="two").working_branch == "MC-AGENT-8546"


def test_an_entry_naming_a_workflow_that_cannot_be_run_is_refused(repo, queue):
    (repo / "broken.toml").write_text('name = "broken"\n')

    with pytest.raises(WorkflowError):
        add(repo, queue, workflow_path=repo / "broken.toml")

    assert queue.all() == []


def test_an_entry_starting_at_a_state_the_workflow_does_not_declare_is_refused(repo, queue):
    with pytest.raises(UnknownState) as caught:
        add(repo, queue, start_state="grrill")

    assert "grrill" in str(caught.value) and "grill" in str(caught.value)
    assert queue.all() == []


def test_an_entry_whose_start_state_needs_a_subject_and_has_none_is_refused(repo, queue):
    with pytest.raises(MissingSubject) as caught:
        add(repo, queue, start_state="implement")

    assert "implement" in str(caught.value)
    assert "--subject" in str(caught.value)
    assert queue.all() == []


def test_a_start_state_whose_prompt_names_no_subject_needs_none(repo, queue):
    add(repo, queue, start_state="grill")

    assert queue.all()[0].start_state == "grill"


def test_an_entry_with_no_start_state_begins_where_the_workflow_does(repo, queue):
    """Unclassified work is the default rather than a special case, so nothing
    is invented for an Entry that names no State."""
    add(repo, queue)

    assert queue.all()[0].start_state is None
