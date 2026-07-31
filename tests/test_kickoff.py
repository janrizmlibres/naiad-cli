import pytest

from naiad.cli.kickoff import start_run
from naiad.cli.refusals import MissingSubject, MissingWorkingBranch
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
def store(tmp_path):
    return RunStore(tmp_path / "naiad" / "runs")


def start(repo, store, sessions, **overrides):
    fields = dict(
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        working_branch="MC-AGENT-8546",
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


def test_a_run_started_at_a_state_whose_prompt_needs_a_subject_is_rejected(
    repo, store, sessions
):
    """Kickoff is the other entrance to delivery, and the announce command's
    guard does not cover it: nothing is announced here. Without this the first
    Prompt of the Run reads '/implement the ticket at ' and then tells the
    agent to take that ticket's triage as given (ADR 0009)."""
    with pytest.raises(MissingSubject) as caught:
        start(repo, store, sessions, start_state="implement")

    assert "implement" in str(caught.value)
    assert "--subject" in str(caught.value)


def test_a_rejected_kickoff_creates_no_run_and_spawns_no_session(repo, store, sessions):
    """Refused before anything exists, as a bad Workflow and an unknown start
    State already are: an operator who mistyped pays the error message only."""
    with pytest.raises(MissingSubject):
        start(repo, store, sessions, start_state="implement")

    assert sessions.spawned == []
    assert not (store.root / "20260719-120000-feature").exists()


def test_a_run_started_at_such_a_state_with_a_subject_delivers_it(repo, store, sessions):
    """The escape hatch the Workflow file's own comment relies on — starting a
    Run partway in — has to keep working for a State that names a Subject."""
    start(repo, store, sessions, start_state="implement", subject="04-x.md")

    (spawn,) = sessions.spawned
    assert spawn.initial_prompt == "/implement the ticket at 04-x.md"


def test_a_subject_is_not_required_by_a_state_that_does_not_name_one(repo, store, sessions):
    """The requirement is the Workflow's to declare, by using the placeholder.
    Every State that does not is unaffected."""
    start(repo, store, sessions, start_state="grill")

    assert sessions.spawned


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
    assert spawn.initial_prompt.endswith("Then announce implement.")


def test_the_run_remembers_the_branch_it_was_started_with(repo, store, sessions):
    """The tick loop interpolates them into every later Prompt, in a process
    that outlives kickoff, so they must survive on the Run."""
    run = start(repo, store, sessions, working_branch="MC-AGENT-8546", predecessor="MC-AGENT-8000")

    reloaded = store.load(run.id)
    assert reloaded.working_branch == "MC-AGENT-8546"
    assert reloaded.predecessor == "MC-AGENT-8000"


def test_a_run_started_without_a_working_branch_is_refused(repo, store, sessions):
    """No derivation is attempted and none is possible: a correct branch name
    needs the affected application and an issue number, which are conventions
    of the target repository (ADR 0015)."""
    with pytest.raises(MissingWorkingBranch) as caught:
        start(repo, store, sessions, working_branch=None)

    assert "--branch" in str(caught.value)


def test_a_run_refused_for_want_of_a_branch_creates_nothing(repo, store, sessions):
    """The same trade the missing-Subject refusal makes: an operator standing
    at the terminal pays the error message only."""
    with pytest.raises(MissingWorkingBranch):
        start(repo, store, sessions, working_branch=None)

    assert sessions.spawned == []
    assert store.all() == []


def _naming_the_branch(repo):
    """A Workflow whose first State's Prompt names both, so what the opening
    delivery does with them is what is asserted."""
    path = repo / "branching.toml"
    path.write_text(
        'name = "w"\n'
        "[[states]]\nname = 'grill'\nprompt = 'work on {branch} based on {predecessor}'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )
    return path


def test_the_first_prompt_names_the_branch_and_the_predecessor(repo, store, sessions):
    start(
        repo,
        store,
        sessions,
        workflow_path=_naming_the_branch(repo),
        working_branch="MC-AGENT-8546",
        predecessor="MC-AGENT-8000",
    )

    (spawn,) = sessions.spawned
    assert spawn.initial_prompt == "work on MC-AGENT-8546 based on MC-AGENT-8000"


def test_a_run_with_no_predecessor_delivers_the_prompt_with_it_empty(repo, store, sessions):
    """A Run whose work stands on nothing is ordinary — it is what the first
    Entry for a repository is — so the Prompt renders rather than raising."""
    start(
        repo,
        store,
        sessions,
        workflow_path=_naming_the_branch(repo),
        working_branch="MC-AGENT-8546",
    )

    (spawn,) = sessions.spawned
    assert spawn.initial_prompt == "work on MC-AGENT-8546 based on "


def test_a_malformed_workflow_creates_no_run_directory_and_no_session(repo, store, sessions):
    (repo / "broken.toml").write_text('name = "w"\n')

    with pytest.raises(WorkflowError) as caught:
        start(repo, store, sessions, workflow_path=repo / "broken.toml")

    assert "declares no states" in str(caught.value)
    assert sessions.spawned == []
    assert store.all() == []
