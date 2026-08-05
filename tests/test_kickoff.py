import pytest

from naiad.cli.kickoff import attach_run, start_entry, start_run
from naiad.domain.announcement import Announcement
from naiad.cli.refusals import MissingSubject
from naiad.domain.entry import Attachment, Entry
from naiad.domain.transitions import UnknownState
from naiad.domain.workflow import WorkflowError
from naiad.runtime.log import RunLog
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


def announcement(seq=1, state="grill"):
    return Announcement(seq=seq, state=state)


# A Workflow whose first State carries both settings — one of its own and one
# off the file-level default — so what the spawn carried can be told from what
# the State declares.
SWITCHED = """
name = "feature"
model = "sonnet"
effort = "medium"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"
model = "opus"

[[states]]
name = "done"
terminal = true
"""

# The same, entered at a Gate State: it delivers nothing, so nothing rides.
GATE_FIRST = """
name = "feature"
model = "sonnet"

[[states]]
name = "review"

[[states]]
name = "done"
terminal = true
"""


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


def test_the_first_states_model_and_effort_reach_the_spawn(repo, store, sessions):
    """At kickoff the first Prompt is handed over at launch, so its switches
    ride the same way — as flags on the spawn (ADR 0026)."""
    (repo / "workflow.toml").write_text(
        """
        name = "feature"
        model = "sonnet"
        effort = "medium"

        [[states]]
        name = "grill"
        prompt = "/grill-with-docs {task}"
        model = "opus"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    start(repo, store, sessions)

    (spawn,) = sessions.spawned
    assert spawn.model == "opus"
    assert spawn.effort == "medium"


def test_the_flags_the_spawn_carried_are_written_to_the_log(repo, store, sessions):
    """A launch flag sets the Session as surely as a Switch typed into it, so
    it is written down as one (ADR 0039). Without the lines the belief starts
    empty, and the Run's second State would type settings the launch had
    already set."""
    (repo / "workflow.toml").write_text(SWITCHED)

    run = start(repo, store, sessions)

    assert [(e.kind, e.state, e.setting, e.detail) for e in RunLog(run.root).entries()] == [
        ("switched", "grill", "model", "opus"),
        ("switched", "grill", "effort", "medium"),
    ]


def test_a_spawned_runs_second_state_reuses_what_the_launch_set(repo, store, sessions):
    """What the seeding buys, read the way the tick loop reads it: the flags
    are the belief every later State is compared against."""
    (repo / "workflow.toml").write_text(SWITCHED)

    run = start(repo, store, sessions)

    assert RunLog(run.root).belief(announcement(seq=1)) == (
        {"model": "opus", "effort": "medium"},
        False,
    )


def test_a_gate_state_first_writes_no_settings_to_the_log(repo, store, sessions):
    """Nothing rode the spawn, so nothing is believed of the Session: what is
    recorded is what was set, not what the State declares."""
    (repo / "workflow.toml").write_text(GATE_FIRST)

    run = start(repo, store, sessions)

    assert RunLog(run.root).entries() == []


def test_a_gate_state_first_spawns_without_model_or_effort_flags(repo, store, sessions):
    """The switches ride Prompt delivery: a Gate State delivers nothing, so
    nothing rides (ADR 0026)."""
    (repo / "workflow.toml").write_text(
        """
        name = "feature"
        model = "sonnet"

        [[states]]
        name = "review"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    start(repo, store, sessions)

    (spawn,) = sessions.spawned
    assert spawn.model is None
    assert spawn.effort is None


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


def test_a_spawned_run_ignores_its_first_states_clear_flag(repo, store, sessions):
    """The other half of the divergence an Adoption makes (ADR 0028). A session
    about to be opened holds nothing to discard, so the flag is not acted on
    here: nothing is cleared, and the Prompt is handed over at launch rather
    than held back behind a Clear waiting to be confirmed."""
    start(repo, store, sessions, start_state="implement", subject="04-x.md")

    assert sessions.cleared == []
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


def test_a_run_started_without_a_working_branch_records_none(repo, store, sessions):
    """Omission is intent (ADR 0022): the Run starts with no Working branch,
    and the agent at its head derives a name in the repository and declares
    it. Naiad still attempts no derivation of its own (ADR 0015)."""
    run = start(repo, store, sessions, working_branch=None)

    assert store.load(run.id).working_branch is None
    assert len(sessions.spawned) == 1


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


# An Adoption: the other way a Run meets its session (ADR 0028).
# Nothing is opened and nothing is delivered — the Run joins the pane the Entry
# named, and its first Prompt waits for the tick loop and a Turn end.


def attach(repo, store, sessions, **overrides):
    fields = dict(
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        working_branch="MC-AGENT-8546",
        attachment=Attachment(tmux_pane="%7"),
        store=store,
        sessions=sessions,
        run_id="20260719-120000-feature",
        created_at="2026-07-19T12:00:00Z",
    )
    fields.update(overrides)
    return attach_run(**fields)


def test_an_adoption_attaches_to_the_named_pane_rather_than_spawning_a_session(
    repo, store, sessions
):
    """The whole point of the feature: the session is the one the human has
    been talking to, so opening a second would throw away the conversation."""
    attach(repo, store, sessions)

    assert sessions.spawned == []
    assert sessions.attached == ["%7"]


def test_the_adopted_runs_metadata_records_the_session_it_joined(repo, store, sessions):
    run = attach(
        repo,
        store,
        sessions,
        attachment=Attachment(
            tmux_pane="%7", claude_session_id="22222222-2222-2222-2222-222222222222"
        ),
    )

    reloaded = store.load(run.id)
    assert reloaded.tmux_pane == "%7"
    assert reloaded.tmux_session == "the-humans-session"
    assert reloaded.claude_session_id == "22222222-2222-2222-2222-222222222222"


def test_an_adoption_that_could_gather_no_session_id_records_none(repo, store, sessions):
    """The id may be unknowable from inside the tool call that adopts; the pane
    is the reliable key and the one an Adoption turns on."""
    run = attach(repo, store, sessions)

    assert store.load(run.id).claude_session_id is None


def test_the_adopted_run_is_resolvable_from_its_pane_without_the_environment_variable(
    repo, store, sessions
):
    """A variable cannot be injected into a process that already exists, so the
    shortcut is simply absent: the hooks and the agent's own commands find this
    Run through the resolution seam's second key."""
    run = attach(repo, store, sessions)
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%7").id == run.id


def test_attaching_delivers_nothing_and_leaves_that_to_the_loop(repo, store, sessions):
    """Delivery waits on a turn ending, and attaching is not where that is
    known: the agent is most likely mid-turn when the Supervisor reaches it."""
    run = attach(repo, store, sessions)

    assert RunLog(run.root).opened() is False
    assert RunLog(run.root).delivered_states() == []


def test_the_adoption_is_the_first_line_of_the_adopted_runs_log(repo, store, sessions):
    run = attach(repo, store, sessions)

    (line,) = RunLog(run.root).entries()
    assert line.kind == "adopted"
    assert "%7" in line.detail


def test_the_adopted_run_remembers_what_it_was_adopted_with(repo, store, sessions):
    """The first Prompt goes out in a later tick, in a process that may not be
    the one that attached the Run, so what it renders from lives on the Run."""
    run = attach(repo, store, sessions, start_state="implement", subject="04-x.md")

    reloaded = store.load(run.id)
    assert reloaded.adopted is True
    assert reloaded.start_state == "implement"
    assert reloaded.start_subject == "04-x.md"


def test_a_workflow_edited_since_the_adoption_was_queued_is_refused(repo, store, sessions):
    """The checks are made again here for the reason kickoff makes them again:
    an Entry queued at the session is taken hours later, and the file it names
    may have been edited in between."""
    (repo / "workflow.toml").write_text(
        'name = "w"\n'
        "[[states]]\nname = 'spec'\nprompt = '/to-spec {subject}'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )

    with pytest.raises(MissingSubject) as caught:
        attach(repo, store, sessions, start_state="spec")

    assert "naiad adopt" in str(caught.value)


def test_a_refused_adoption_creates_no_run_and_attaches_nothing(repo, store, sessions):
    with pytest.raises(UnknownState):
        attach(repo, store, sessions, start_state="spek")

    assert sessions.attached == []
    assert store.all() == []


# One place turns an Entry into the Run it always described, whichever way that
# Run meets its session.


def test_an_attach_marked_entry_becomes_a_run_that_joined_its_session(repo, store, sessions):
    run = start_entry(
        _entry(repo, attachment=Attachment(tmux_pane="%7")),
        predecessor=None,
        store=store,
        sessions=sessions,
        run_id="20260719-120000-feature",
        claude_session_id="11111111-1111-1111-1111-111111111111",
        created_at="2026-07-19T12:00:00Z",
    )

    assert run.adopted is True
    assert sessions.attached == ["%7"]
    assert sessions.spawned == []


def test_an_ordinary_entry_becomes_a_run_with_a_session_of_its_own(repo, store, sessions):
    run = start_entry(
        _entry(repo),
        predecessor="MC-AGENT-8000",
        store=store,
        sessions=sessions,
        run_id="20260719-120000-feature",
        claude_session_id="11111111-1111-1111-1111-111111111111",
        created_at="2026-07-19T12:00:00Z",
    )

    assert run.adopted is False
    assert run.predecessor == "MC-AGENT-8000"
    assert sessions.attached == []
    assert len(sessions.spawned) == 1


def _entry(repo, **overrides):
    fields = dict(
        id="20260719-115900-feature",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        working_branch="MC-AGENT-8546",
        created_at="2026-07-19T11:59:00Z",
    )
    fields.update(overrides)
    return Entry(**fields)


def test_a_malformed_workflow_creates_no_run_directory_and_no_session(repo, store, sessions):
    (repo / "broken.toml").write_text('name = "w"\n')

    with pytest.raises(WorkflowError) as caught:
        start(repo, store, sessions, workflow_path=repo / "broken.toml")

    assert "declares no states" in str(caught.value)
    assert sessions.spawned == []
    assert store.all() == []
