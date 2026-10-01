"""Spawn as the agent meets it: exit status, what lands in the Queue and on the
Parent's Children record, error text.

Run as a real subprocess against a temporary Naiad directory, like the other
Protocol verbs, because Spawn is typed inside a Session and resolves its Run
the way they do.
"""

import json
import subprocess

import pytest

from naiad.domain.entry import Entry
from naiad.domain.settings import StateSetting
from naiad.runtime.log import RunLog
from naiad.runtime.queue import Queue
from naiad.runtime.records import Children
from naiad.runtime.run import RunStore
from naiad_command import NAIAD, naiad_environment, requires_installed_naiad

pytestmark = requires_installed_naiad

WORKFLOW = """
name = "feature"

[[states]]
name = "implement"
prompt = "/implement {task}"

[[states]]
name = "build"
prompt = "/implement {subject}"

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
def worktree(tmp_path):
    """The Child's working tree: a sibling of the Parent's, as a worktree is."""
    path = tmp_path / "repo-wt-01"
    path.mkdir()
    return path


@pytest.fixture
def parent(tmp_path, repo):
    """A live Run started from an Entry, as the Supervisor leaves one."""
    run = RunStore(tmp_path / "naiad" / "runs").create(
        run_id="the-parent",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
        working_branch="feat/dark-mode",
        skip_gates=True,
        settings=(StateSetting(state="build", setting="model", value="sonnet"),),
    )
    queue_of(run).add(
        Entry(
            id="20260719-120000-000000-feature-1",
            workflow_path=run.workflow_path,
            task=run.task,
            target_repo=run.target_repo,
            working_branch=run.working_branch,
            created_at=run.created_at,
            skip_gates=True,
            settings=run.settings,
            run_id=run.id,
        )
    )
    return run


def queue_of(run):
    return Queue(run.root.parents[1] / "queue")


def spawn(run, *arguments, run_id="the-parent"):
    return subprocess.run(
        [NAIAD, "spawn", *arguments],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id=run_id),
        cwd=str(run.target_repo),
        timeout=30,
    )


def children_in_queue(run):
    return [entry for entry in queue_of(run).all() if entry.parent is not None]


def test_spawn_queues_a_child_naming_its_parent_and_says_so(parent, worktree):
    finished = spawn(
        parent, "--repo", str(worktree), "--branch", "feat/dark-mode--01",
        "--base", "feat/dark-mode", "--at", "build", "--subject", "ticket-01.md",
    )

    assert finished.returncode == 0, finished.stderr
    (child,) = children_in_queue(parent)
    assert finished.stdout.startswith(f"queued {child.id}")
    assert child.parent == "the-parent"
    assert child.target_repo == worktree.resolve()
    assert child.working_branch == "feat/dark-mode--01"
    assert child.pinned_base == "feat/dark-mode"
    assert child.start_state == "build"
    assert child.subject == "ticket-01.md"


def test_a_child_takes_its_parents_workflow_settings_gates_and_task(parent, worktree):
    finished = spawn(parent, "--repo", str(worktree), "--at", "build", "--subject", "t-01")

    assert finished.returncode == 0, finished.stderr
    (child,) = children_in_queue(parent)
    assert child.workflow_path == parent.workflow_path
    assert child.task == "add dark mode"
    assert child.skip_gates is True
    assert child.settings == parent.settings


def test_what_the_command_names_beats_what_the_child_inherits(parent, worktree):
    finished = spawn(
        parent, "build ticket one", "--repo", str(worktree), "--at", "build",
        "--subject", "t-01", "--model", "build=opus", "--effort", "build=high",
    )

    assert finished.returncode == 0, finished.stderr
    (child,) = children_in_queue(parent)
    assert child.task == "build ticket one"
    assert set(child.settings) == {
        StateSetting(state="build", setting="model", value="opus"),
        StateSetting(state="build", setting="effort", value="high"),
    }


def test_the_parents_children_record_holds_the_childs_entry(parent, worktree):
    spawn(parent, "--repo", str(worktree), "--at", "build", "--subject", "t-01")

    (child,) = children_in_queue(parent)
    assert [(found.entry_id, found.run_id) for found in Children(parent.root).all()] == [
        (child.id, None)
    ]


def test_the_childrens_record_keeps_what_its_parent_is_told_of_it(parent, worktree):
    """Subject, Working branch and working tree, so that a Child whose Entry is
    gone before it started can still be named to its Parent."""
    spawn(
        parent, "--repo", str(worktree), "--branch", "feat--01", "--at", "build",
        "--subject", "t-01",
    )

    (found,) = Children(parent.root).all()
    assert (found.subject, found.branch, found.worktree) == (
        "t-01",
        "feat--01",
        str(worktree.resolve()),
    )


def test_spawn_supervises_nothing(parent, worktree):
    """It returns as soon as the Entry is on disk: nothing was started."""
    spawn(parent, "--repo", str(worktree), "--at", "build", "--subject", "t-01")

    (child,) = children_in_queue(parent)
    assert child.run_id is None
    assert [run.id for run in RunStore(parent.root.parent).all()] == ["the-parent"]


# Every refusal exits non-zero, says how to fix it, and queues nothing.


def refused(finished, run, *, saying):
    assert finished.returncode != 0
    assert saying in finished.stderr
    assert children_in_queue(run) == []
    assert Children(run.root).all() == []


def test_spawn_outside_any_run_is_refused_as_every_verb_is(parent, worktree):
    finished = spawn(parent, "--repo", str(worktree), run_id="")

    refused(finished, parent, saying="no run is attached to this session")


def test_spawn_from_a_run_that_has_ended_is_refused(parent, worktree):
    RunLog(parent.root).record_cancellation(state="implement")

    finished = spawn(parent, "--repo", str(worktree), "--at", "build", "--subject", "t-01")

    refused(finished, parent, saying="no run is attached to this session")


def test_spawn_from_inside_a_child_is_refused(parent, worktree, repo, tmp_path):
    child_run = RunStore(parent.root.parent).create(
        run_id="a-child",
        workflow_path=parent.workflow_path,
        task="t",
        target_repo=worktree,
        created_at="2026-07-19T12:00:00Z",
    )
    queue_of(parent).add(
        Entry(
            id="20260719-120001-000000-feature-1",
            workflow_path=parent.workflow_path,
            task="t",
            target_repo=worktree,
            working_branch=None,
            created_at="2026-07-19T12:00:01Z",
            parent="the-parent",
            run_id=child_run.id,
        )
    )
    deeper = tmp_path / "deeper"
    deeper.mkdir()

    finished = spawn(child_run, "--repo", str(deeper), run_id="a-child")

    assert finished.returncode != 0
    assert "is itself a child" in finished.stderr
    assert len(children_in_queue(parent)) == 1
    assert Children(child_run.root).all() == []


def test_spawn_into_the_parents_own_working_tree_is_refused(parent, repo):
    finished = spawn(parent, "--repo", str(repo / "."), "--at", "build", "--subject", "t-01")

    refused(finished, parent, saying="git worktree add")


def test_spawn_on_a_branch_claimed_in_that_working_tree_is_refused(parent, worktree):
    spawn(parent, "--repo", str(worktree), "--branch", "b-01", "--at", "build", "--subject", "t-01")
    (first,) = children_in_queue(parent)

    finished = spawn(
        parent, "--repo", str(worktree), "--branch", "b-01", "--at", "build", "--subject", "t-02"
    )

    assert finished.returncode != 0
    assert "name another branch" in finished.stderr
    assert children_in_queue(parent) == [first]
    assert [found.entry_id for found in Children(parent.root).all()] == [first.id]


def test_spawn_at_an_unknown_state_is_refused(parent, worktree):
    finished = spawn(parent, "--repo", str(worktree), "--at", "nowhere")

    refused(finished, parent, saying="nowhere")


def test_spawn_at_a_state_needing_a_subject_without_one_is_refused(parent, worktree):
    finished = spawn(parent, "--repo", str(worktree), "--at", "build")

    refused(finished, parent, saying="naiad spawn --repo <path> --at build --subject <value>")


def test_spawn_without_a_working_tree_is_refused(parent):
    finished = spawn(parent, "--at", "build", "--subject", "t-01")

    refused(finished, parent, saying="--repo")


def test_an_entry_written_before_children_existed_has_no_parent(parent):
    (document,) = queue_of(parent).root.iterdir()
    written = json.loads(document.read_text())
    written.pop("parent", None)
    document.write_text(json.dumps(written))

    assert queue_of(parent).all()[0].parent is None
