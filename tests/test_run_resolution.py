import pytest

from naiad.runtime.resolve import RUN_ID_VARIABLE, RunResolver
from naiad.runtime.run import RunStore


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "runs")


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    return path


def create(store, repo, run_id):
    return store.create(
        run_id=run_id,
        workflow_path=repo / "w.toml",
        task="t",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
    )


def test_resolves_from_the_environment_variable(store, repo):
    create(store, repo, "one")
    resolver = RunResolver(store, environ={RUN_ID_VARIABLE: "one"})

    assert resolver.resolve().id == "one"


def test_resolves_from_the_tmux_pane_when_the_environment_is_empty(store, repo):
    run = create(store, repo, "one")
    run.attach_session(tmux_session="naiad-one", tmux_pane="%7")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%7").id == "one"


def test_resolves_from_the_claude_session_id_when_the_environment_is_empty(store, repo):
    run = create(store, repo, "one")
    run.attach_session(tmux_session="naiad-one", tmux_pane="%7", claude_session_id="sess-abc")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(claude_session_id="sess-abc").id == "one"


def test_picks_the_run_owning_the_pane_when_several_runs_exist(store, repo):
    create(store, repo, "one").attach_session(tmux_session="a", tmux_pane="%1")
    create(store, repo, "two").attach_session(tmux_session="b", tmux_pane="%2")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%2").id == "two"


def test_resolves_to_nothing_when_no_run_is_attached(store, repo):
    create(store, repo, "one")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%9") is None
    assert resolver.resolve() is None


def test_an_environment_variable_naming_an_unknown_run_falls_back_to_the_session(store, repo):
    create(store, repo, "one").attach_session(tmux_session="a", tmux_pane="%1")
    resolver = RunResolver(store, environ={RUN_ID_VARIABLE: "gone"})

    assert resolver.resolve(tmux_pane="%1").id == "one"
