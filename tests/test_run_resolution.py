import pytest

from naiad.domain.decide import Finish
from naiad.domain.entry import Attachment, Entry
from naiad.domain.question import Question
from naiad.runtime.announcements import Announcements
from naiad.runtime.log import RunLog
from naiad.runtime.resolve import RUN_ID_VARIABLE, RunResolver, turn_recipient
from naiad.runtime.run import RunStore

WORKFLOW = """
name = "w"

[[states]]
name = "work"
prompt = "do it"

[[states]]
name = "done"
terminal = true
"""


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


def write_workflow(repo):
    """Write the Workflow every Run in this module names.

    Only the tests that need a Terminal State read back call this. The rest
    leave the file absent, which is itself a case: a Run whose Workflow cannot
    be read falls back to the log line.
    """
    (repo / "w.toml").write_text(WORKFLOW)


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


def test_a_run_that_announced_its_terminal_state_resolves_to_nothing(store, repo):
    write_workflow(repo)
    run = create(store, repo, "one")
    run.attach_session(tmux_session="a", tmux_pane="%1", claude_session_id="sess-abc")
    Announcements(run.root).announce("done")
    resolver = RunResolver(store, environ={RUN_ID_VARIABLE: "one"})

    assert resolver.resolve(tmux_pane="%1", claude_session_id="sess-abc") is None


def test_a_run_standing_in_an_ordinary_state_still_resolves(store, repo):
    write_workflow(repo)
    run = create(store, repo, "one")
    run.attach_session(tmux_session="a", tmux_pane="%1")
    Announcements(run.root).announce("work")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%1").id == "one"


def test_a_question_asked_from_the_terminal_state_is_not_an_ending(store, repo):
    write_workflow(repo)
    run = create(store, repo, "one")
    run.attach_session(tmux_session="a", tmux_pane="%1")
    Announcements(run.root).ask(Question(text="which?", options=("a", "b")), state="done")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%1").id == "one"


def test_the_pane_of_an_ended_run_is_free_for_the_run_that_adopts_it(store, repo):
    write_workflow(repo)
    ended = create(store, repo, "one")
    ended.attach_session(tmux_session="a", tmux_pane="%1")
    Announcements(ended.root).announce("done")
    adopted = create(store, repo, "two")
    adopted.attach_session(tmux_session="a", tmux_pane="%1")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%1").id == "two"


def test_an_environment_variable_naming_an_ended_run_falls_back_to_the_session(store, repo):
    write_workflow(repo)
    ended = create(store, repo, "one")
    ended.attach_session(tmux_session="a", tmux_pane="%1")
    Announcements(ended.root).announce("done")
    adopted = create(store, repo, "two")
    adopted.attach_session(tmux_session="a", tmux_pane="%1")
    resolver = RunResolver(store, environ={RUN_ID_VARIABLE: "one"})

    assert resolver.resolve(tmux_pane="%1").id == "two"


def test_a_finished_run_stays_ended_however_much_the_agent_announces_after(store, repo):
    write_workflow(repo)
    run = create(store, repo, "one")
    run.attach_session(tmux_session="a", tmux_pane="%1")
    Announcements(run.root).announce("done")
    RunLog(run.root).record(Finish(state="done"), seq=1)
    Announcements(run.root).ask(Question(text="which?", options=("a", "b")), state="work")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%1") is None


def test_a_workflow_that_cannot_be_read_leaves_the_run_resolving(store, repo):
    run = create(store, repo, "one")
    run.attach_session(tmux_session="a", tmux_pane="%1")
    Announcements(run.root).announce("done")
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%1").id == "one"


def test_a_workflow_that_cannot_be_read_falls_back_to_the_log(store, repo):
    run = create(store, repo, "one")
    run.attach_session(tmux_session="a", tmux_pane="%1")
    Announcements(run.root).announce("done")
    RunLog(run.root).record(Finish(state="done"), seq=1)
    resolver = RunResolver(store, environ={})

    assert resolver.resolve(tmux_pane="%1") is None


def waiting_entry(entry_id, *, pane=None, claude_session_id=None, run_id=None, repo=None):
    """An adopted Entry in the gap: queued, claiming a Session, its Run not
    started yet unless a run_id says otherwise."""
    return Entry(
        id=entry_id,
        workflow_path=repo / "w.toml",
        task="t",
        target_repo=repo,
        working_branch=None,
        created_at="2026-08-08T07:52:54Z",
        attachment=(
            Attachment(tmux_pane=pane, claude_session_id=claude_session_id) if pane else None
        ),
        run_id=run_id,
    )


def test_a_live_run_receives_the_turn_before_any_entry(store, repo):
    run = create(store, repo, "one")
    run.attach_session(tmux_session="a", tmux_pane="%1")
    entry = waiting_entry("e1", pane="%1", repo=repo)

    recipient = turn_recipient(
        RunResolver(store, environ={}), [entry], tmux_pane="%1"
    )

    assert recipient.id == "one"


def test_the_entry_awaiting_attachment_receives_the_turn_when_no_run_answers(store, repo):
    """The adopting turn ends before the Supervisor's pass creates the Run;
    the ending belongs to the Entry that will become it."""
    entry = waiting_entry("e1", pane="%1", repo=repo)

    recipient = turn_recipient(RunResolver(store, environ={}), [entry], tmux_pane="%1")

    assert recipient.id == "e1"


def test_an_entry_whose_run_exists_is_past_its_gap(store, repo):
    """Once the Run is recorded on the Entry it is resolvable by pane, and an
    ended one has released the Session — either way the Entry no
    longer stands in for it."""
    entry = waiting_entry("e1", pane="%1", run_id="one", repo=repo)

    assert turn_recipient(RunResolver(store, environ={}), [entry], tmux_pane="%1") is None


def test_an_entry_claiming_another_pane_does_not_receive_the_turn(store, repo):
    entry = waiting_entry("e1", pane="%1", repo=repo)

    assert turn_recipient(RunResolver(store, environ={}), [entry], tmux_pane="%2") is None


def test_a_spawned_entry_never_receives_a_turn(store, repo):
    entry = waiting_entry("e1", repo=repo)

    assert turn_recipient(RunResolver(store, environ={}), [entry], tmux_pane="%1") is None


def test_the_first_waiting_entry_claiming_the_pane_receives_the_turn(store, repo):
    """Queue order is id order; the earlier Entry is the next Run for the pane."""
    later = waiting_entry("e2", pane="%1", repo=repo)
    earlier = waiting_entry("e1", pane="%1", repo=repo)

    recipient = turn_recipient(
        RunResolver(store, environ={}), [later, earlier], tmux_pane="%1"
    )

    assert recipient.id == "e1"


def test_the_claude_session_id_is_the_entrys_second_key(store, repo):
    entry = waiting_entry("e1", pane="%1", claude_session_id="sess-abc", repo=repo)

    recipient = turn_recipient(
        RunResolver(store, environ={}), [entry], claude_session_id="sess-abc"
    )

    assert recipient.id == "e1"


def test_no_run_and_no_entry_leaves_the_turn_unrecorded(store, repo):
    assert turn_recipient(RunResolver(store, environ={}), [], tmux_pane="%1") is None
