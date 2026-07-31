"""The tick over real Run files, with the session recorded rather than driven.

The rules themselves are covered in tests/test_decide.py over plain data; what
is pinned here is that the wiring reads the right files and dispatches once per
Announcement — the two ways this could be wrong without any rule being wrong.
"""

import pytest

from naiad.domain.decide import NOTHING, HANG_SECONDS, SILENCE_SECONDS, Deliver, Notify, Nudge
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
name = "review"

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


class RecordingNotifier:
    def __init__(self):
        self.notified = []

    def notify(self, title, message):
        self.notified.append((title, message))


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


def drive(run, workflow, session, *, notifier=None, now=None):
    """Every tick is given its moment, so no test reads the wall clock. The
    default is the instant of the Run's newest record: nothing has been idle."""
    return tick(
        run=run,
        workflow=workflow,
        session=session,
        notifier=notifier or RecordingNotifier(),
        now=now if now is not None else _later(run, 0),
    )


def announce(run, state, *, then_stop=True):
    announcement = Announcements(run.root).announce(state)
    if then_stop:
        Turns(run.root).record_end(latest_seq=announcement.seq)
    return announcement


def test_an_announcement_with_a_turn_ended_delivers_the_prompt_into_the_pane(
    run, workflow, session
):
    announce(run, "grill")

    action = drive(run, workflow, session)

    assert isinstance(action, Deliver)
    assert session.sent == [
        ("send", "%42", "/grill-with-docs add dark mode, then announce review")
    ]


def test_an_announcement_with_no_turn_ended_leaves_the_session_alone(run, workflow, session):
    announce(run, "grill", then_stop=False)

    assert drive(run, workflow, session) is NOTHING
    assert session.sent == []


def test_an_announcement_is_delivered_once_however_often_the_loop_ticks(run, workflow, session):
    announce(run, "grill")

    drive(run, workflow, session)
    drive(run, workflow, session)
    drive(run, workflow, session)

    assert len(session.sent) == 1


def test_the_same_state_announced_again_is_delivered_again(run, workflow, session):
    announce(run, "implement")
    drive(run, workflow, session)
    announce(run, "implement")
    drive(run, workflow, session)

    assert [entry[0] for entry in session.sent] == ["clear", "send", "clear", "send"]


def test_a_state_declaring_clear_is_cleared_before_its_prompt_arrives(run, workflow, session):
    announce(run, "implement")

    drive(run, workflow, session)

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
        drive(run, workflow, session)

    assert session.sent == []


def test_a_run_started_with_gates_skipped_delivers_the_next_state_that_has_a_prompt(
    tmp_path, session
):
    """The option is recorded on the Run at kickoff and read back here, since
    the loop runs in a process that outlives the kickoff that chose it."""
    repo = tmp_path / "gated"
    repo.mkdir()
    workflow_path = repo / "workflow.toml"
    workflow_path.write_text(
        'name = "gated"\n'
        "[[states]]\nname = 'grill'\nprompt = 'work, then announce {next_state}'\n"
        "[[states]]\nname = 'review'\n"
        "[[states]]\nname = 'spec'\nprompt = '/to-spec'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )
    run = RunStore(tmp_path / "gated-runs").create(
        run_id="gated-run",
        workflow_path=workflow_path,
        task="t",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
        skip_gates=True,
    )
    run.attach_session(tmux_session="naiad-gated-run", tmux_pane="%7")
    announce(run, "grill")

    drive(run, parse_workflow(workflow_path.read_text()), session)

    assert session.sent == [("send", "%7", "work, then announce spec")]


def test_a_turn_ending_before_the_announcement_is_not_a_turn_ending_since_it(
    run, workflow, session
):
    """The agent announced and carried on working; the recorded turn end is stale."""
    announce(run, "grill")
    drive(run, workflow, session)
    session.sent.clear()

    Announcements(run.root).announce("implement")

    assert drive(run, workflow, session) is NOTHING
    assert session.sent == []


def test_a_gate_state_notifies_the_operator_and_sends_nothing(run, workflow, session):
    """The human types into the session directly; Naiad's only job is to say so."""
    notifier = RecordingNotifier()
    announce(run, "review")

    action = drive(run, workflow, session, notifier=notifier)

    assert isinstance(action, Notify)
    assert session.sent == []
    assert len(notifier.notified) == 1
    assert "review" in notifier.notified[0][1]


def test_the_operator_is_notified_once_however_often_the_loop_ticks(run, workflow, session):
    """The defect most likely to ship: a condition that persists across ticks
    with identical signals, notified every couple of seconds all night."""
    notifier = RecordingNotifier()
    announce(run, "review")

    drive(run, workflow, session, notifier=notifier)
    drive(run, workflow, session, notifier=notifier)
    drive(run, workflow, session, notifier=notifier)

    assert len(notifier.notified) == 1


def test_the_loop_keeps_running_after_a_notification_and_delivers_the_next_announcement(
    run, workflow, session
):
    """Notifying does not end a Run: the human types, the agent announces, and
    delivery resumes. Only a Terminal State ends a Run."""
    notifier = RecordingNotifier()
    announce(run, "review")
    drive(run, workflow, session, notifier=notifier)

    announce(run, "implement")
    action = drive(run, workflow, session, notifier=notifier)

    assert isinstance(action, Deliver)
    assert ("send", "%42", "/implement the next ticket") in session.sent


def test_a_later_gate_notifies_again(run, workflow, session):
    notifier = RecordingNotifier()
    announce(run, "review")
    drive(run, workflow, session, notifier=notifier)
    announce(run, "implement")
    drive(run, workflow, session, notifier=notifier)
    announce(run, "review")

    drive(run, workflow, session, notifier=notifier)

    assert len(notifier.notified) == 2


def test_an_agent_that_ends_a_turn_without_announcing_is_nudged_in_the_session(
    run, workflow, session
):
    announce(run, "grill")
    drive(run, workflow, session)
    session.sent.clear()
    Turns(run.root).record_end(latest_seq=1)

    action = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))

    assert action == Nudge(attempt=1)
    assert [entry[0] for entry in session.sent] == ["send"]


def test_a_second_silence_is_nudged_more_firmly_than_the_first(run, workflow, session):
    announce(run, "grill")
    drive(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    session.sent.clear()

    first = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))
    second = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))

    assert (first, second) == (Nudge(attempt=1), Nudge(attempt=2))
    assert session.sent[0][2] != session.sent[1][2]


def test_a_third_silence_notifies_instead_of_nudging(run, workflow, session):
    notifier = RecordingNotifier()
    announce(run, "grill")
    drive(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    session.sent.clear()

    for _ in range(3):
        action = drive(run, workflow, session, notifier=notifier, now=_later(run, SILENCE_SECONDS))

    assert isinstance(action, Notify)
    assert len(session.sent) == 2
    assert len(notifier.notified) == 1

    # And having called the human, it does not call them again on every tick.
    after = drive(run, workflow, session, notifier=notifier, now=_later(run, SILENCE_SECONDS))
    assert after is NOTHING
    assert len(notifier.notified) == 1


def test_a_session_that_never_ends_a_turn_notifies_on_the_timeout(run, workflow, session):
    """A hung agent: no Stop hook ever fires, so no signal will ever arrive."""
    notifier = RecordingNotifier()

    action = drive(run, workflow, session, notifier=notifier, now=_later(run, HANG_SECONDS))

    assert isinstance(action, Notify)
    assert session.sent == []
    assert len(notifier.notified) == 1


def test_a_session_within_the_timeout_is_left_alone(run, workflow, session):
    notifier = RecordingNotifier()

    action = drive(run, workflow, session, notifier=notifier, now=_later(run, 1))

    assert action is NOTHING
    assert notifier.notified == []


def _later(run, seconds):
    """Elapsed time as data rather than something the test waits for: the loop
    measures idleness from the Run's records, so the clock is moved instead."""
    newest = max(path.stat().st_mtime for path in run.root.iterdir() if path.is_file())
    return newest + seconds


def test_an_agent_working_on_what_it_was_given_is_not_nudged_however_long_it_takes(
    run, workflow, session
):
    """The turn end that let a Prompt be delivered is spent by that delivery.
    Reading it a second time makes every phase that outlives the silence bound
    look silent — and an implement phase routinely runs for many minutes —
    so Naiad would type a reminder over an agent working normally."""
    announce(run, "grill")
    drive(run, workflow, session)
    session.sent.clear()

    action = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS * 3))

    assert action is NOTHING
    assert session.sent == []


def test_an_agent_that_never_announces_at_all_is_nudged_after_its_first_turn(
    run, workflow, session
):
    """Kickoff hands the agent its first Prompt directly, so the first thing
    Naiad hears is a turn ending with nothing announced — and that is when a
    forgotten Protocol is most likely."""
    Turns(run.root).record_end(latest_seq=None)

    action = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))

    assert action == Nudge(attempt=1)
    assert [entry[0] for entry in session.sent] == ["send"]
