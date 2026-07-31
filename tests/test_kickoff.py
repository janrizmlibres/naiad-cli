import pytest

from naiad.cli.kickoff import start_run
from naiad.domain.transitions import UnknownState
from naiad.domain.workflow import WorkflowError
from naiad.runtime.resolve import RUN_ID_VARIABLE, RunResolver
from naiad.runtime.run import RunStore

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}\\n\\nThen announce {next_state}."

[[states]]
name = "review"

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
def store(tmp_path):
    return RunStore(tmp_path / "naiad" / "runs")


def start(repo, store, sessions, **overrides):
    fields = dict(
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        store=store,
        sessions=sessions,
        run_id="20260719-120000-feature",
        claude_session_id="11111111-1111-1111-1111-111111111111",
        created_at="2026-07-19T12:00:00Z",
    )
    fields.update(overrides)
    return start_run(**fields)


def test_creates_a_run_directory_outside_the_target_repository(repo, store, sessions):
    run = start(repo, store, sessions)

    assert run.metadata_path.is_file()
    assert repo not in run.root.parents


def test_writes_nothing_into_the_target_repository(repo, store, sessions):
    before = sorted(p.relative_to(repo) for p in repo.rglob("*"))

    start(repo, store, sessions)

    assert sorted(p.relative_to(repo) for p in repo.rglob("*")) == before


def test_the_run_metadata_records_the_task_and_the_session(repo, store, sessions):
    run = start(repo, store, sessions)

    reloaded = store.load(run.id)
    assert reloaded.task == "add dark mode"
    assert reloaded.tmux_session == "naiad-20260719-120000-feature"
    assert reloaded.tmux_pane == "%42"
    assert reloaded.claude_session_id == "11111111-1111-1111-1111-111111111111"


def test_spawns_one_session_in_the_target_repository_in_bypass_permissions_mode(
    repo, store, sessions
):
    start(repo, store, sessions)

    (spawn,) = sessions.spawned
    assert spawn.cwd == repo
    assert spawn.name == "naiad-20260719-120000-feature"
    assert spawn.permission_mode == "bypassPermissions"


def test_names_the_run_in_the_sessions_environment(repo, store, sessions):
    start(repo, store, sessions)

    (spawn,) = sessions.spawned
    assert spawn.environ[RUN_ID_VARIABLE] == "20260719-120000-feature"


def test_delivers_the_first_states_prompt_with_the_task_interpolated(repo, store, sessions):
    start(repo, store, sessions)

    (spawn,) = sessions.spawned
    assert spawn.initial_prompt == "/grill-with-docs add dark mode\n\nThen announce review."


def test_the_run_is_resolvable_without_the_environment_variable(repo, store, sessions):
    run = start(repo, store, sessions)
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%42").id == run.id
    assert resolver.resolve(claude_session_id=run.claude_session_id).id == run.id


def test_a_gate_state_first_leaves_the_session_untouched(repo, store, sessions):
    (repo / "gate.toml").write_text(
        'name = "w"\n[[states]]\nname = "review"\n[[states]]\nname = "done"\nterminal = true\n'
    )

    start(repo, store, sessions, workflow_path=repo / "gate.toml")

    (spawn,) = sessions.spawned
    assert spawn.initial_prompt is None


def test_a_run_started_at_a_named_state_delivers_that_states_prompt_first(repo, store, sessions):
    (repo / "later.toml").write_text(
        'name = "w"\n'
        "[[states]]\nname = 'grill'\nprompt = '/grill'\n"
        "[[states]]\nname = 'spec'\nprompt = '/to-spec {task}'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )

    start(repo, store, sessions, workflow_path=repo / "later.toml", start_state="spec")

    (spawn,) = sessions.spawned
    assert spawn.initial_prompt == "/to-spec add dark mode"


def test_a_run_started_at_a_state_the_workflow_does_not_declare_is_rejected(
    repo, store, sessions
):
    """Rejected before a session exists, so a typo costs the operator nothing
    but the error message."""
    with pytest.raises(UnknownState) as caught:
        start(repo, store, sessions, start_state="spek")

    assert "spek" in str(caught.value)
    assert sessions.spawned == []
    assert store.all() == []


def test_the_run_remembers_the_options_it_was_started_with(repo, store, sessions):
    """The tick loop resolves the next State on every delivery, in a process
    that outlives kickoff, so the options must survive on the Run."""
    run = start(repo, store, sessions, start_state="review", skip_gates=True)

    reloaded = store.load(run.id)
    assert reloaded.skip_gates is True
    assert reloaded.start_state == "review"


def test_a_run_started_with_gates_skipped_names_the_next_state_that_has_a_prompt(
    repo, store, sessions
):
    start(repo, store, sessions, skip_gates=True)

    (spawn,) = sessions.spawned
    assert spawn.initial_prompt.endswith("Then announce done.")


def test_a_malformed_workflow_creates_no_run_directory_and_no_session(repo, store, sessions):
    (repo / "broken.toml").write_text('name = "w"\n')

    with pytest.raises(WorkflowError) as caught:
        start(repo, store, sessions, workflow_path=repo / "broken.toml")

    assert "declares no states" in str(caught.value)
    assert sessions.spawned == []
    assert store.all() == []
