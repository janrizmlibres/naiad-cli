"""What ends the watch and what does not.

The tick itself is covered in tests/test_loop.py and the rules in
tests/test_decide.py. What is pinned here is the one thing the loop decides for
itself — whether to come round again — because the failure it protects against
is a Run that has finished still ticking all night, and its opposite: a Run
parked at a Gate that stops ticking and never notices the human's reply.
"""

import pytest

from fake_terminal import ESCAPE, styles_of, to_terminal
from naiad.cli.watch import _narrate, tell, tick_once, told, watch
from naiad.domain.notification import Notification
from naiad.domain.answerer import Answered
from naiad.domain.decide import Clear, Confirm, Finish, Notify, Nudge, Report
from naiad.domain.question import Question
from naiad.domain.workflow import parse_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.log import RunLog
from naiad.runtime.records import Turns
from naiad.runtime.run import RunStore

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "review"

[[states]]
name = "done"
terminal = true
"""


class Interrupted(Exception):
    """Stands in for the operator's Ctrl-C, so that a loop which is meant to
    keep ticking can be shown to keep ticking without running forever."""


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

    def notify(self, title, message, kind):
        self.notified.append((title, message, kind))


class UnusedAnswerer:
    def consult(self, spec):
        raise AssertionError("no Question was asked")


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


def announce(run, state):
    announcement = Announcements(run.root).announce(state)
    Turns(run.root).record_end(latest_seq=announcement.seq)


def drive(run, *, ticks_allowed=3, session=None, notifier=None):
    """Watch the Run, with the operator's Ctrl-C standing by. A loop that is
    supposed to end on its own never reaches it."""
    slept = []

    def sleep(_seconds):
        slept.append(_seconds)
        if len(slept) >= ticks_allowed:
            raise Interrupted

    action = watch(
        run=run,
        workflow=parse_workflow(WORKFLOW),
        session=session or RecordingSession(),
        notifier=notifier or RecordingNotifier(),
        answerer=UnusedAnswerer(),
        sleep=sleep,
        report=lambda _message: None,
    )
    return action, slept


def test_watching_stops_once_the_run_reaches_a_terminal_state(run):
    """A finished Run must not leave something ticking forever."""
    announce(run, "done")

    action, slept = drive(run)

    assert action == Finish(state="done")
    assert slept == []


def test_watching_continues_while_a_run_waits_for_a_human(run):
    """Asserted beside the Terminal case: a Run parked at a Gate stays alive
    and keeps ticking, because the human types and the agent announces, and a
    loop that had stopped would never see it."""
    announce(run, "review")

    with pytest.raises(Interrupted):
        drive(run, ticks_allowed=3)


def test_finishing_notifies_the_operator_that_the_run_is_done(run):
    """The operator is asleep; the whole point of ending is being told."""
    announce(run, "done")
    notifier = RecordingNotifier()

    drive(run, notifier=notifier)

    assert notifier.notified
    title, message, _kind = notifier.notified[-1]
    assert run.id in title
    assert "done" in message


def test_a_finished_run_is_left_with_its_session_untouched(run):
    """Killing it destroys the evidence the operator wants when the result
    looks wrong — and the session is the only place that evidence lives."""
    announce(run, "done")
    session = RecordingSession()

    drive(run, session=session)

    assert session.sent == []


def test_watching_a_run_that_has_already_finished_does_not_start_ticking(run):
    """A finished Run decides Nothing on every tick, so a watch that did not
    ask first would spin over it forever — the one thing ending a Run is for."""
    announce(run, "done")
    drive(run)

    action, slept = drive(run)

    assert action is None
    assert slept == []


def test_nothing_the_agent_says_after_the_end_starts_the_run_again(run):
    """The session is left alive, so the agent may well say something more
    into it. It is talking to the operator, not to Naiad."""
    announce(run, "done")
    drive(run)
    session = RecordingSession()

    announce(run, "grill")
    drive(run, session=session)

    assert session.sent == []


def test_watching_a_cancelled_run_does_not_start_ticking(run):
    """A Run the operator called off is over by the other ending,
    and it stops a watch for the same reason a Finish does: nothing is coming,
    so a watch that ticked it would spin over it forever."""
    announce(run, "implement")
    RunLog(run.root).record_cancellation(state="implement")

    action, slept = drive(run)

    assert action is None
    assert slept == []


class ScriptedAnswerer:
    def __init__(self, outcome):
        self.outcome = outcome

    def consult(self, spec):
        return self.outcome


ANSWERED_WORKFLOW = WORKFLOW.replace('name = "feature"\n', 'name = "feature"\n\n[answerer]\n', 1)
LONG_QUESTION = "Which module should own retries when the upstream vendor rate limits us? " * 3
QUESTION_OPTIONS = ("the client, which already backs off", "the caller")


def narration_of(run, answerer, *, lead=0):
    """Every line the operator is told while a Question is consulted and answered."""
    Announcements(run.root).ask(
        Question(text=LONG_QUESTION, options=QUESTION_OPTIONS), state="grill"
    )
    Turns(run.root).record_end(latest_seq=1)
    lines = []
    for _ in range(2):
        tick_once(
            run=run,
            workflow=parse_workflow(ANSWERED_WORKFLOW),
            session=RecordingSession(),
            notifier=RecordingNotifier(),
            answerer=answerer,
            report=lines.append,
            lead=lead,
        )
    return lines


def test_the_consultation_echo_is_one_line_cut_to_the_terminal_width(run, monkeypatch):
    monkeypatch.setenv("COLUMNS", "60")

    consulted, _ = narration_of(run, ScriptedAnswerer(Answered(text="the client")))

    assert consulted.startswith("consulting the answerer: Which module should own retries")
    assert len(consulted) == 60
    assert consulted.endswith("…")
    assert "\n" not in consulted


def test_the_answer_echo_drops_the_options_and_keeps_the_first_clause(run, monkeypatch):
    monkeypatch.setenv("COLUMNS", "60")

    _, answered = narration_of(
        run, ScriptedAnswerer(Answered(text="the client, since it already backs off"))
    )

    assert answered == "answered: the client"


def test_the_echo_leaves_room_for_what_the_caller_prints_before_it(run, monkeypatch):
    """Runs in different lanes are told apart by a prefix the Supervisor adds,
    and the line as the operator sees it is what may not exceed the width."""
    monkeypatch.setenv("COLUMNS", "60")

    consulted, _ = narration_of(run, ScriptedAnswerer(Answered(text="x")), lead=20)

    assert len(consulted) == 40


# How the narration looks to the operator at a terminal. Every line above reads
# it as words; the styles are what a terminal is shown of the same line.


def test_progress_is_led_by_its_verb_and_names_the_state_as_a_state():
    assert styles_of(_narrate(Clear(state="grill", attempt=1), width=80)) == {
        "clearing": "event.progress",
        "grill": "state",
    }
    assert styles_of(_narrate(Confirm(state="grill", attempt=1), width=80)) == {
        "confirmed": "event.progress",
        "grill": "state",
    }
    assert styles_of(_narrate(Report(state="review"), width=80)) == {
        "reported entering": "event.progress",
        "review": "state",
    }


def test_a_retry_is_said_aside():
    clearing = _narrate(Clear(state="grill", attempt=2), width=80)

    assert clearing == "clearing grill again (attempt 2)"
    assert styles_of(clearing)[" again (attempt 2)"] == "secondary"


def test_what_wants_watching_is_led_by_a_verb_that_says_so(run, monkeypatch):
    monkeypatch.setenv("COLUMNS", "60")
    consulted, answered = narration_of(run, ScriptedAnswerer(Answered(text="the client")))

    assert styles_of(consulted)["consulting the answerer:"] == "event.attention"
    assert styles_of(answered)["answered:"] == "event.attention"
    assert styles_of(_narrate(Nudge(attempt=2), width=80))["nudged the agent"] == "event.attention"


def test_the_end_of_a_run_is_led_by_a_verb_of_its_own():
    assert styles_of(_narrate(Finish(state="done"), width=80)) == {
        "finished at": "event.ended",
        "done": "state",
    }


def test_watching_a_run_that_has_already_ended_says_so_as_an_end(run):
    announce(run, "done")
    drive(run)
    told = []

    watch(
        run=run,
        workflow=parse_workflow(WORKFLOW),
        session=RecordingSession(),
        notifier=RecordingNotifier(),
        answerer=UnusedAnswerer(),
        report=told.append,
    )

    assert told == ["a-run has already ended"]
    assert styles_of(told[0]) == {"a-run": "id", "has already ended": "event.ended"}


# A telling on the terminal leg: the same words the desktop banner and the
# phone are given, with its Run styled as an id and its naiad: as the kind of
# telling it is.


def test_a_telling_reads_as_its_title_and_message():
    line = told("naiad: run-1", "entered ship", Notification.REPORT)

    assert line == "naiad: run-1: entered ship"


def test_a_telling_is_styled_by_what_kind_of_telling_it_is():
    report = told("naiad: run-1", "entered ship", Notification.REPORT)
    needed = told("naiad: run-1", "parked at review", Notification.NOTIFY)
    finished = told("naiad: run-1", "finished at done", Notification.FINISH)

    assert styles_of(report) == {"naiad:": "event.progress", "run-1": "id"}
    assert styles_of(needed)["naiad:"] == "event.attention"
    assert styles_of(finished)["naiad:"] == "event.ended"


def test_a_title_naming_no_run_is_kept_whole():
    assert told("naiad", "why", Notification.NOTIFY) == "naiad: why"


def test_a_telling_is_coloured_on_stderr_only_at_a_terminal(monkeypatch, capsys):
    tell("naiad: run-1", "entered ship", Notification.REPORT)
    assert capsys.readouterr().err == "naiad: run-1: entered ship\n"

    terminal = to_terminal(monkeypatch, stream="stderr")
    tell("naiad: run-1", "entered ship", Notification.REPORT)
    assert ESCAPE in terminal.getvalue()
