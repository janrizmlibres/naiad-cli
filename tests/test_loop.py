"""The tick over real Run files, with the session recorded rather than driven.

The rules themselves are covered in tests/test_decide.py over plain data; what
is pinned here is that the wiring reads the right files and dispatches once per
Announcement — the two ways this could be wrong without any rule being wrong.
"""

import pytest

from naiad.domain.decide import NOTHING, Deliver
from naiad.domain.workflow import parse_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.loop import UndrivableRun, tick
from naiad.runtime.records import Turns
from naiad.runtime.run import RunStore

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}, then announce {next_state}"

[[states]]
name = "implement"
prompt = "/implement the next ticket"
clear = true

[[states]]
name = "done"
terminal = true
"""


class RecordingSession:
    def __init__(self):
        self.sent = []

    def send(self, pane, text):
        self.sent.append(("send", pane, text))

    def clear(self, pane):
        self.sent.append(("clear", pane, None))


@pytest.fixture
def run(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "workflow.toml").write_text(WORKFLOW)
    created = RunStore(tmp_path / "runs").create(
        run_id="a-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
    )
    created.attach_session(tmux_session="naiad-a-run", tmux_pane="%42")
    return created


@pytest.fixture
def session():
    return RecordingSession()


@pytest.fixture
def workflow():
    return parse_workflow(WORKFLOW)


def announce(run, state, *, then_stop=True):
    announcement = Announcements(run.root).announce(state)
    if then_stop:
        Turns(run.root).record_end(latest_seq=announcement.seq)
    return announcement


def test_an_announcement_with_a_turn_ended_delivers_the_prompt_into_the_pane(
    run, workflow, session
):
    announce(run, "grill")

    action = tick(run=run, workflow=workflow, session=session)

    assert isinstance(action, Deliver)
    assert session.sent == [
        ("send", "%42", "/grill-with-docs add dark mode, then announce implement")
    ]


def test_an_announcement_with_no_turn_ended_leaves_the_session_alone(run, workflow, session):
    announce(run, "grill", then_stop=False)

    assert tick(run=run, workflow=workflow, session=session) is NOTHING
    assert session.sent == []


def test_an_announcement_is_delivered_once_however_often_the_loop_ticks(run, workflow, session):
    announce(run, "grill")

    tick(run=run, workflow=workflow, session=session)
    tick(run=run, workflow=workflow, session=session)
    tick(run=run, workflow=workflow, session=session)

    assert len(session.sent) == 1


def test_the_same_state_announced_again_is_delivered_again(run, workflow, session):
    announce(run, "implement")
    tick(run=run, workflow=workflow, session=session)
    announce(run, "implement")
    tick(run=run, workflow=workflow, session=session)

    assert [entry[0] for entry in session.sent] == ["clear", "send", "clear", "send"]


def test_a_state_declaring_clear_is_cleared_before_its_prompt_arrives(run, workflow, session):
    announce(run, "implement")

    tick(run=run, workflow=workflow, session=session)

    assert session.sent == [
        ("clear", "%42", None),
        ("send", "%42", "/implement the next ticket"),
    ]


def test_a_run_with_no_pane_recorded_is_refused_rather_than_sent_anywhere(
    run, workflow, session
):
    """tmux reads an empty -t target as the pane the operator is looking at, so
    coercing a missing pane would deliver a Prompt — and a destructive Clear —
    into whatever session happens to be attached."""
    run.tmux_pane = None
    announce(run, "implement")

    with pytest.raises(UndrivableRun):
        tick(run=run, workflow=workflow, session=session)

    assert session.sent == []


def test_a_turn_ending_before_the_announcement_is_not_a_turn_ending_since_it(
    run, workflow, session
):
    """The agent announced and carried on working; the recorded turn end is stale."""
    announce(run, "grill")
    tick(run=run, workflow=workflow, session=session)
    session.sent.clear()

    Announcements(run.root).announce("implement")

    assert tick(run=run, workflow=workflow, session=session) is NOTHING
    assert session.sent == []
