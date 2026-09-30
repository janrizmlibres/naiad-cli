import json

import pytest

from naiad.runtime.home import StorageError
from naiad.runtime.run import RunStore


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "naiad" / "runs")


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "target-repo"
    path.mkdir()
    return path


def create(store, repo, **overrides):
    fields = dict(
        run_id="20260719-120000-feature",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
    )
    fields.update(overrides)
    return store.create(**fields)


def test_creates_a_directory_holding_the_runs_metadata(store, repo):
    run = create(store, repo)

    assert run.root.is_dir()
    assert json.loads(run.metadata_path.read_text())["task"] == "add dark mode"


def test_metadata_records_what_links_the_run_to_its_session_and_task(store, repo):
    run = create(store, repo)
    run.attach_session(tmux_session="naiad-x", tmux_pane="%7", claude_session_id="abc")

    reloaded = store.load(run.id)
    assert reloaded.tmux_session == "naiad-x"
    assert reloaded.tmux_pane == "%7"
    assert reloaded.claude_session_id == "abc"
    assert reloaded.task == "add dark mode"
    assert reloaded.target_repo == repo


def test_a_new_run_has_no_session_yet(store, repo):
    run = create(store, repo)

    assert run.tmux_session is None
    assert run.tmux_pane is None


def test_the_run_directory_lies_outside_the_target_repository(store, repo):
    run = create(store, repo)

    assert repo not in run.root.parents
    assert list(repo.iterdir()) == []


def test_a_store_rooted_inside_the_target_repository_is_refused(repo):
    inside = RunStore(repo / ".naiad" / "runs")

    with pytest.raises(StorageError) as caught:
        create(inside, repo)

    assert "inside the target repository" in str(caught.value)
    assert list(repo.iterdir()) == []


def test_reusing_a_run_id_is_refused(store, repo):
    create(store, repo)

    with pytest.raises(StorageError) as caught:
        create(store, repo)

    assert "already exists" in str(caught.value)


def test_loading_an_unknown_run_gives_nothing(store, repo):
    create(store, repo)

    assert store.load("no-such-run") is None


def test_metadata_records_the_working_branch_and_the_predecessor(store, repo):
    """Run-level facts, so a Run resumed by a second process — or a Prompt
    delivered long after kickoff — reads them back rather than being told
    again."""
    run = create(store, repo, working_branch="TASK-8546", predecessor="TASK-8000")

    reloaded = store.load(run.id)
    assert reloaded.working_branch == "TASK-8546"
    assert reloaded.predecessor == "TASK-8000"


def test_a_run_with_no_predecessor_reloads_without_one(store, repo):
    run = create(store, repo, working_branch="TASK-8546")

    assert store.load(run.id).predecessor is None


def test_metadata_written_before_these_fields_existed_still_loads(store, repo):
    """A Run started by an earlier Naiad is still a Run. It has no Working
    branch because nothing gave it one, not because one was lost."""
    run = create(store, repo, working_branch="TASK-8546")
    document = json.loads(run.metadata_path.read_text())
    del document["working_branch"]
    del document["predecessor"]
    run.metadata_path.write_text(json.dumps(document))

    reloaded = store.load(run.id)
    assert reloaded.working_branch is None
    assert reloaded.predecessor is None


def test_lists_every_run_it_holds(store, repo):
    create(store, repo, run_id="one")
    create(store, repo, run_id="two")

    assert {run.id for run in store.all()} == {"one", "two"}


# Removing a Run. Only a Prune ever asks for this, and only of a Run whose
# Entry is done — the store itself checks nothing, because what a
# Run's own files say about it is the Queue's to read rather than this store's.


def test_removing_a_run_takes_its_whole_directory(store, repo):
    run = create(store, repo)
    (run.root / "log.jsonl").write_text('{"kind": "finish"}\n')

    store.remove(run.id)

    assert not run.root.exists()


def test_removing_a_run_that_is_not_there_is_not_a_refusal(store, repo):
    """A Run that is not there needs no taking, and the caller asked for it to
    be gone rather than for it to have been there."""
    assert store.remove("no-such-run") is None


def test_a_run_directory_that_will_not_go_is_reported_naming_it(store, repo, monkeypatch):
    """Read as a message rather than a traceback, as a damaged Entry is: a
    directory the operator has locked or opened elsewhere is theirs to fix, and
    the path is the only part of it they can act on."""
    run = create(store, repo)

    def refuse(*_arguments, **_keywords):
        raise OSError("device or resource busy")

    monkeypatch.setattr("naiad.runtime.run.shutil.rmtree", refuse)

    with pytest.raises(StorageError) as refusal:
        store.remove(run.id)

    assert str(run.root) in str(refusal.value)
