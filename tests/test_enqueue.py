"""Adding one Entry, and everything that is refused before it exists.

Every failure that used to happen at kickoff happens here, on the trade the
missing-Subject refusal already makes: whoever is adding the Entry is standing
right there and pays the error message only, rather than finding out at three
in the morning.
"""

import json

import pytest

from naiad.cli.batch import BatchError, enqueue_batch
from naiad.cli.enqueue import BranchAlreadyClaimed, Work, enqueue
from naiad.cli.refusals import ADD_COMMAND, MissingSubject, MissingTask
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


def work(repo, **overrides):
    fields = dict(
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        working_branch="MC-AGENT-8546",
    )
    fields.update(overrides)
    return Work(**fields)


def runs_beside(queue):
    """The Run store the Queue's claims resolve through, where the commands
    keep it: beside the Queue under the same Naiad-owned home."""
    return RunStore(queue.root.parent / "runs")


def add(repo, queue, entry_id="20260722-120000-feature-431", **overrides):
    return enqueue(
        work(repo, **overrides),
        queue=queue,
        runs=runs_beside(queue),
        entry_id=entry_id,
        created_at="2026-07-22T12:00:00Z",
        # Which vocabulary the refusals quote back. Every entrance enqueues, so
        # there is no default to fall back on; these tests are the command's.
        remedy=ADD_COMMAND,
    )


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


def test_an_entry_with_no_working_branch_joins_the_queue(repo, queue):
    """Omission is intent (ADR 0022): the agent at the head of the Run derives
    a name there, so work described without one is queued rather than turned
    away."""
    add(repo, queue, working_branch=None)

    (queued,) = queue.all()
    assert queued.working_branch is None


def test_two_branchless_entries_for_the_same_repository_coexist(repo, queue):
    """A branchless Entry claims no branch, so queueing a second is never
    blocked by a name that does not exist yet."""
    add(repo, queue, entry_id="one", working_branch=None)
    add(repo, queue, entry_id="two", task="something else", working_branch=None)

    assert [held.id for held in queue.all()] == ["one", "two"]


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


def test_a_branch_a_branchless_entrys_run_has_recorded_is_claimed(repo, queue):
    """An Entry with no recorded branch but a Run that holds one claims that
    branch. The claim resolves through the Run rather than being copied back
    onto the Entry (the `status_of` pattern, ADR 0013), so a Derived branch
    cannot be collided with invisibly."""
    branchless = add(repo, queue, entry_id="one", working_branch=None)
    runs_beside(queue).create(
        run_id="20260722-121500-feature",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:15:00Z",
        working_branch="MC-AGENT-8546",
    )
    queue.attach_run(branchless, run_id="20260722-121500-feature")

    with pytest.raises(BranchAlreadyClaimed) as caught:
        add(repo, queue, entry_id="two", task="something else")

    assert "MC-AGENT-8546" in str(caught.value)
    assert "one" in str(caught.value)


def test_a_branchless_entry_whose_run_holds_no_branch_yet_claims_nothing(repo, queue):
    """Until the Run's branch is declared, there is no name to collide with."""
    branchless = add(repo, queue, entry_id="one", working_branch=None)
    runs_beside(queue).create(
        run_id="20260722-121500-feature",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:15:00Z",
    )
    queue.attach_run(branchless, run_id="20260722-121500-feature")

    add(repo, queue, entry_id="two", task="something else")

    assert [held.id for held in queue.all()] == ["one", "two"]


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


def test_a_subject_stands_in_for_an_absent_task(repo, queue):
    """ADR 0024: an operator who gave only a Subject has said the Subject
    describes the work, so the Entry's task is total without being typed
    twice — `--at implement --subject <ticket>` needs no task beside it."""
    add(repo, queue, task=None, start_state="implement", subject="docs/ticket.md")

    (queued,) = queue.all()
    assert queued.task == "docs/ticket.md"
    assert queued.subject == "docs/ticket.md"


def test_the_stand_in_is_unconditional_about_the_start_state(repo, queue):
    """ADR 0024: even a start State whose Prompt renders {task} takes the
    Subject — an operator who gave only a Subject has said the Subject
    describes the work, and refusing would be second-guessing that."""
    add(repo, queue, task=None, start_state="grill", subject="docs/ticket.md")

    (queued,) = queue.all()
    assert queued.task == "docs/ticket.md"


def test_work_naming_no_task_and_no_subject_is_refused(repo, queue):
    """The one refusal the stand-in keeps (ADR 0024): with neither, nothing
    says what the work is — not to the Queue listing, not to the Answerer."""
    with pytest.raises(MissingTask) as caught:
        add(repo, queue, task=None, start_state="grill")

    assert "--subject" in str(caught.value)
    assert queue.all() == []


def test_an_entry_with_no_start_state_begins_where_the_workflow_does(repo, queue):
    """Unclassified work is the default rather than a special case, so nothing
    is invented for an Entry that names no State."""
    add(repo, queue)

    assert queue.all()[0].start_state is None


# Queueing what a batch file declares. The refusals above are the ones that
# matter here: every one of them applies to a batched Entry unchanged, and a
# file with one bad Entry queues none of them, because a half-failed batch
# leaves a partial Queue with no signal — worse than an error. Reading the file
# itself is tested in tests/test_batch.py.


def batch(queue, *works, source="batch.toml"):
    return enqueue_batch(
        works,
        queue=queue,
        runs=runs_beside(queue),
        entry_ids=[f"entry-{position}" for position in range(1, len(works) + 1)],
        created_at="2026-07-22T12:00:00Z",
        source=source,
    )


def test_a_batch_queues_every_entry_it_declares_in_file_order(repo, queue):
    batch(
        queue,
        work(repo, task="first", working_branch="MC-AGENT-8546"),
        work(repo, task="second", working_branch="MC-AGENT-8547"),
        work(repo, task="third", working_branch="MC-AGENT-8548"),
    )

    assert [held.task for held in queue.all()] == ["first", "second", "third"]


def test_entries_in_one_batch_may_differ_in_everything_an_entry_carries(repo, other_repo, queue):
    """Three bugs starting at one State and two designs starting at another go
    in one file, which is what makes a file worth having."""
    batch(
        queue,
        work(repo, start_state="grill"),
        work(
            other_repo,
            workflow_path=other_repo / "workflow.toml",
            working_branch="MC-AGENT-8547",
            start_state="implement",
            subject="docs/ticket.md",
            pinned_base="MC-AGENT-8000",
            skip_gates=True,
        ),
    )

    first, second = queue.all()
    assert first.start_state == "grill"
    assert first.skip_gates is False
    assert second.target_repo == other_repo
    assert second.start_state == "implement"
    assert second.subject == "docs/ticket.md"
    assert second.pinned_base == "MC-AGENT-8000"
    assert second.skip_gates is True


def test_a_batch_with_one_invalid_entry_queues_none_of_them(repo, queue):
    with pytest.raises(BatchError):
        batch(
            queue,
            work(repo, working_branch="MC-AGENT-8546"),
            work(repo, working_branch="MC-AGENT-8547", start_state="grrill"),
            work(repo, working_branch="MC-AGENT-8548"),
        )

    assert queue.all() == []


def test_a_refused_entry_is_named_by_the_file_and_its_position(repo, queue):
    """The way Workflow parsing names a State's, so the message says which line
    to go and fix."""
    with pytest.raises(BatchError) as caught:
        batch(
            queue,
            work(repo, working_branch="MC-AGENT-8546"),
            work(repo, working_branch="MC-AGENT-8547", start_state="grrill"),
            source="nightly.toml",
        )

    assert "nightly.toml" in str(caught.value)
    assert "entry 2" in str(caught.value)
    assert "grrill" in str(caught.value)


def test_two_entries_in_one_file_claiming_one_branch_are_refused(repo, queue):
    """The duplicate-branch check has to catch a claim made inside the same
    file, where neither Entry is on disk for the other to find."""
    with pytest.raises(BatchError) as caught:
        batch(
            queue,
            work(repo, task="first", working_branch="MC-AGENT-8546"),
            work(repo, task="second", working_branch="MC-AGENT-8546"),
        )

    assert "entry 2" in str(caught.value)
    assert "MC-AGENT-8546" in str(caught.value)
    assert queue.all() == []


def test_two_entries_in_one_file_for_different_repositories_may_share_a_branch(
    repo, other_repo, queue
):
    batch(
        queue,
        work(repo),
        work(other_repo, workflow_path=other_repo / "workflow.toml"),
    )

    assert [held.working_branch for held in queue.all()] == ["MC-AGENT-8546", "MC-AGENT-8546"]


def test_a_batched_entry_claiming_a_branch_the_queue_already_holds_is_refused(repo, queue):
    add(repo, queue, entry_id="already-queued")

    with pytest.raises(BatchError) as caught:
        batch(queue, work(repo, task="second"))

    assert "already-queued" in str(caught.value)
    assert [held.id for held in queue.all()] == ["already-queued"]


def test_named_and_branchless_entries_compose_in_one_file(repo, queue):
    """Each behaviour applies per Entry: a batch mixing given branches and
    omissions queues both as they were described."""
    batch(
        queue,
        work(repo, task="named"),
        work(repo, task="branchless", working_branch=None),
    )

    assert [held.working_branch for held in queue.all()] == ["MC-AGENT-8546", None]


def test_a_batched_entry_whose_start_state_needs_a_subject_and_has_none_is_refused(repo, queue):
    with pytest.raises(BatchError) as caught:
        batch(queue, work(repo, start_state="implement"))

    assert "entry 1" in str(caught.value)
    assert "subject" in str(caught.value)
    assert queue.all() == []


def test_a_batched_entry_naming_only_a_subject_takes_it_as_its_task(repo, queue):
    batch(queue, work(repo, task=None, start_state="implement", subject="docs/ticket.md"))

    (queued,) = queue.all()
    assert queued.task == "docs/ticket.md"


def test_a_batched_entry_naming_no_task_and_no_subject_is_refused(repo, queue):
    with pytest.raises(BatchError) as caught:
        batch(queue, work(repo, task=None, start_state="grill"))

    assert "entry 1" in str(caught.value)
    assert "task" in str(caught.value) and "subject" in str(caught.value)
    assert queue.all() == []


def test_a_batched_entry_naming_a_workflow_that_cannot_be_run_is_refused(repo, queue):
    (repo / "broken.toml").write_text('name = "broken"\n')

    with pytest.raises(BatchError) as caught:
        batch(queue, work(repo, workflow_path=repo / "broken.toml"))

    assert "entry 1" in str(caught.value)
    assert queue.all() == []


def test_nothing_records_that_a_batch_arrived_together(repo, queue):
    """A batch is not a domain concept: it produces N Entries, and neither an
    Entry nor the Queue beside it says they arrived in one file. There is
    nothing to cancel and nothing to report on, because nothing has been asked
    of the Queue that requires knowing."""
    batched, _also_batched = batch(
        queue,
        work(repo, task="one"),
        work(repo, task="two", working_branch="MC-AGENT-8547"),
    )
    alone = add(repo, queue, entry_id="on-its-own", working_branch="MC-AGENT-8548")

    written = {path.name: json.loads(path.read_text()) for path in queue.root.iterdir()}
    assert sorted(written) == sorted(f"{held.id}.json" for held in queue.all())
    assert written[f"{batched.id}.json"].keys() == written[f"{alone.id}.json"].keys()
