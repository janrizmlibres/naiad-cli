"""The tick over real Run files, with the session recorded rather than driven.

The rules themselves are covered in tests/test_decide.py over plain data; what
is pinned here is that the wiring reads the right files and dispatches once per
Announcement — the two ways this could be wrong without any rule being wrong.
"""

import pytest

from naiad.domain.answerer import Answered, Escalated
from naiad.domain.decide import (
    CLEAR_CONFIRM_SECONDS,
    CLEAR_RETRY_LIMIT,
    NOTHING,
    HANG_SECONDS,
    SILENCE_SECONDS,
    DELIVERY_CONFIRM_SECONDS,
    DELIVERY_RETRY_LIMIT,
    Clear,
    Confirm,
    Consult,
    Deliver,
    Finish,
    Notify,
    Nudge,
    Respond,
    Switch,
)
from naiad.domain.notification import Notification
from naiad.domain.question import Question
from naiad.domain.workflow import parse_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.answers import AnswerLog
from naiad.runtime.log import RunLog
from naiad.runtime.loop import UndrivableRun, tick
from naiad.runtime.records import Clears, Deliveries, Handled, Holds, Turns, Waits
from naiad.runtime.submitted import judge
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
prompt = "/implement the ticket at {subject}"
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

    def notify(self, title, message, kind):
        self.notified.append((title, message, kind))


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


def whole(prompt):
    return prompt


def drive(run, workflow, session, *, notifier=None, answerer=None, now=None, submit=whole):
    """Every tick is given its moment, so no test reads the wall clock. The
    default is the instant of the Run's newest record: nothing has been idle.

    A typed Prompt is then submitted as the Session would submit it, and judged
    by what the UserPromptSubmit hook runs (ADR 0053). submit is what the
    Session made of the typing — whole by default, cut short where a test says
    so — and None stands for a Session whose hook never fires."""
    action = tick(
        run=run,
        workflow=workflow,
        session=session,
        notifier=notifier or RecordingNotifier(),
        answerer=answerer or RecordingAnswerer(),
        now=now if now is not None else _later(run, 0),
    )
    if isinstance(action, Deliver) and submit is not None:
        typed = Deliveries(run.root).latest()
        judge(run.root, submit(session.sent[-1][2]), now=typed.at)
    return action


def deliver(run, workflow, session, **kwargs):
    """Drive a Prompt through to its Confirm: typed on one tick, settled on the
    next once the hook has seen it land (ADR 0053). Returns the delivery."""
    delivered = drive(run, workflow, session, **kwargs)
    drive(run, workflow, session, **kwargs)
    return delivered


def announce(run, state, *, then_stop=True, subject=None):
    announcement = Announcements(run.root).announce(state, subject=subject)
    if then_stop:
        Turns(run.root).record_end(latest_seq=announcement.seq)
    return announcement


def land_clear(run):
    """Stand in for the SessionStart(clear) hook confirming the /clear landed —
    the signal the loop waits on before delivering a Clearing State's Prompt."""
    Clears(run.root).record_landing()


def deliver_clearing(run, workflow, session, **kwargs):
    """Drive a Clearing State's two-tick handshake through to its Prompt: type
    /clear, confirm it landed, then deliver (ADR 0019). Returns the delivery."""
    drive(run, workflow, session, **kwargs)
    land_clear(run)
    return drive(run, workflow, session, **kwargs)


def test_an_announcement_with_a_turn_ended_delivers_the_prompt_into_the_pane(
    run, workflow, session
):
    announce(run, "grill")

    action = drive(run, workflow, session)

    assert isinstance(action, Deliver)
    assert session.sent == [
        ("send", "%42", "/grill-with-docs add dark mode, then announce review")
    ]


SWITCHED = """
name = "feature"
model = "sonnet"
effort = "medium"

[[states]]
name = "grill"
prompt = "work, then announce done"
model = "opus"
effort = "high"

[[states]]
name = "done"
terminal = true
"""


def test_a_typed_prompt_is_kept_for_the_hook_to_judge_a_submission_against(
    run, workflow, session
):
    announce(run, "grill")

    drive(run, workflow, session, submit=None)

    assert Deliveries(run.root).latest().prompt == session.sent[-1][2]


def test_an_announcement_is_settled_only_once_the_hook_saw_its_prompt_land(
    run, workflow, session
):
    """Typing the Prompt is not delivering it: the Announcement is handled on the
    tick after the hook reported it whole, and not before (ADR 0053)."""
    announce(run, "grill")

    drive(run, workflow, session)
    assert Handled(run.root).seq() is None

    assert drive(run, workflow, session) == Confirm(state="grill", attempt=1)
    assert Handled(run.root).seq() == 1
    assert [e.kind for e in RunLog(run.root).entries()] == ["announced", "delivered", "confirmed"]


def test_a_prompt_the_session_took_cut_short_is_typed_again_and_then_settles(
    run, workflow, session
):
    """The failure this exists for: the Session dropped the head of the typing
    and took the rest. The hook turns it away and the loop types it again."""
    announce(run, "grill")
    prompt = "/grill-with-docs add dark mode, then announce review"

    first = drive(run, workflow, session, submit=lambda text: text[10:])
    retry = drive(run, workflow, session)
    settled = drive(run, workflow, session)

    assert (first.attempt, retry.attempt) == (1, 2)
    assert session.sent == [("send", "%42", prompt), ("send", "%42", prompt)]
    assert settled == Confirm(state="grill", attempt=2)


def test_a_prompt_cut_short_every_time_tells_the_operator(run, workflow, session):
    notifier = RecordingNotifier()
    announce(run, "grill")

    for _ in range(DELIVERY_RETRY_LIMIT):
        drive(run, workflow, session, notifier=notifier, submit=lambda text: text[10:])
    action = drive(run, workflow, session, notifier=notifier)

    assert isinstance(action, Notify)
    assert len(session.sent) == DELIVERY_RETRY_LIMIT
    assert len(notifier.notified) == 1


def test_a_prompt_no_hook_reported_tells_the_operator_and_is_not_typed_again(
    run, workflow, session
):
    notifier = RecordingNotifier()
    announce(run, "grill")
    drive(run, workflow, session, submit=None)

    waited = drive(run, workflow, session, notifier=notifier, now=_later(run, DELIVERY_CONFIRM_SECONDS - 1))
    told = drive(run, workflow, session, notifier=notifier, now=_later(run, DELIVERY_CONFIRM_SECONDS))

    assert waited is NOTHING
    assert isinstance(told, Notify)
    assert len(session.sent) == 1


def test_each_switch_is_typed_on_its_own_tick_ahead_of_the_prompt(run, session):
    """One send a tick (ADR 0038). The session discards whatever arrives while
    it is handling a slash command, so the two Switches and the Prompt are three
    ticks rather than three sends."""
    keyed = parse_workflow(SWITCHED)
    announce(run, "grill")

    drive(run, keyed, session)
    assert session.sent == [("send", "%42", "/model opus")]

    drive(run, keyed, session)
    assert session.sent[-1] == ("send", "%42", "/effort high")

    drive(run, keyed, session)
    assert session.sent[-1] == ("send", "%42", "work, then announce done")


# The same States with a Gate among them, so a Notify can be driven rather than
# written into the log by hand: a Gate State is the hand-off Naiad plans for.
SWITCHED_WITH_GATE = """
name = "feature"
model = "sonnet"
effort = "medium"

[[states]]
name = "grill"
prompt = "work, then announce done"
model = "opus"
effort = "high"

[[states]]
name = "review"

[[states]]
name = "done"
terminal = true
"""


def test_the_next_announcement_reuses_what_the_session_holds(run, session):
    """A Switch carries what the Session does not already hold (ADR 0039). The
    settings are sticky, so a State asking for the ones already there goes
    straight to its Prompt rather than spending two Ticks saying so again."""
    keyed = parse_workflow(SWITCHED)
    announce(run, "grill")
    for _ in range(3):
        drive(run, keyed, session)

    announce(run, "grill")
    action = drive(run, keyed, session)

    assert isinstance(action, Deliver)
    assert session.sent[-1] == ("send", "%42", "work, then announce done")


def test_a_notification_makes_the_next_delivery_switch_again(run, session):
    """A Notify is Naiad telling a human it needs them, and a human at the
    keyboard may type a /model of their own. Past one the belief is worthless,
    so the settings go in again whether or not they changed (ADR 0039). It is
    the only heal left now that a Switch is not typed on every delivery."""
    gated = parse_workflow(SWITCHED_WITH_GATE)
    announce(run, "grill")
    for _ in range(3):
        drive(run, gated, session)

    announce(run, "review")
    assert isinstance(drive(run, gated, session), Notify)

    announce(run, "grill")
    action = drive(run, gated, session)

    assert isinstance(action, Switch)
    assert session.sent[-1] == ("send", "%42", "/model opus")


def test_the_subject_reaches_the_pane_in_the_delivered_prompt(run, workflow, session):
    """The wiring hop the Subject exists for: the Clear discards the context
    that chose the ticket, and the Prompt arriving after it names the ticket
    anyway (ADR 0009)."""
    announce(run, "implement", subject=".scratch/f/issues/04-x.md")

    deliver_clearing(run, workflow, session)

    assert ("send", "%42", "/implement the ticket at .scratch/f/issues/04-x.md") in session.sent


def test_successive_iterations_are_delivered_their_own_subjects(run, workflow, session):
    """One State announced once per item, each delivery naming its own. This is
    what the Subject buys over re-deriving the choice in a Cleared context."""
    announce(run, "implement", subject="01-a.md")
    deliver_clearing(run, workflow, session)
    announce(run, "implement", subject="02-b.md")
    deliver_clearing(run, workflow, session)

    delivered = [message for kind, _, message in session.sent if kind == "send"]
    assert delivered == ["/implement the ticket at 01-a.md", "/implement the ticket at 02-b.md"]


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
    announce(run, "implement", subject="04-x.md")
    deliver_clearing(run, workflow, session)
    announce(run, "implement", subject="04-x.md")
    deliver_clearing(run, workflow, session)

    assert [entry[0] for entry in session.sent] == ["clear", "send", "clear", "send"]


def test_a_state_declaring_clear_is_cleared_before_its_prompt_arrives(run, workflow, session):
    announce(run, "implement", subject="04-x.md")

    deliver_clearing(run, workflow, session)

    assert session.sent == [
        ("clear", "%42", None),
        ("send", "%42", "/implement the ticket at 04-x.md"),
    ]


def test_a_clearing_states_prompt_is_held_back_until_the_clear_is_confirmed(run, workflow, session):
    """The whole of ADR 0019: the Prompt does not follow the /clear on faith.
    A first tick types /clear and stops there; only once the Clear is confirmed
    does a later tick deliver, so a dropped /clear can never be delivered
    through."""
    announce(run, "implement", subject="04-x.md")

    first = drive(run, workflow, session)

    assert isinstance(first, Clear)
    assert session.sent == [("clear", "%42", None)]

    land_clear(run)
    delivered = drive(run, workflow, session)

    assert isinstance(delivered, Deliver)
    assert session.sent == [
        ("clear", "%42", None),
        ("send", "%42", "/implement the ticket at 04-x.md"),
    ]


def test_a_dropped_clear_is_retyped_once_the_confirm_window_passes(run, workflow, session):
    """No confirmation arrives, so after the window the /clear is typed again
    rather than the Prompt delivered into the context it should have cleared."""
    announce(run, "implement", subject="04-x.md")
    drive(run, workflow, session)

    waited = drive(run, workflow, session, now=_later(run, CLEAR_CONFIRM_SECONDS - 1))
    retry = drive(run, workflow, session, now=_later(run, CLEAR_CONFIRM_SECONDS))

    assert waited is NOTHING
    assert isinstance(retry, Clear) and retry.attempt == 2
    assert [kind for kind, _, _ in session.sent] == ["clear", "clear"]


def test_a_clear_that_never_lands_notifies_the_operator_and_delivers_nothing(
    run, workflow, session
):
    """Past the retry bound the human is told and the session is left un-cleared
    for them, rather than a Prompt delivered into a context that never cleared —
    the bug this whole handshake exists to prevent."""
    notifier = RecordingNotifier()
    announce(run, "implement", subject="04-x.md")

    action = None
    for _ in range(CLEAR_RETRY_LIMIT + 1):
        action = drive(run, workflow, session, notifier=notifier, now=_later(run, CLEAR_CONFIRM_SECONDS))

    assert isinstance(action, Notify)
    assert [kind for kind, _, _ in session.sent] == ["clear"] * CLEAR_RETRY_LIMIT
    assert len(notifier.notified) == 1

    after = drive(run, workflow, session, notifier=notifier, now=_later(run, CLEAR_CONFIRM_SECONDS))
    assert after is NOTHING
    assert len(notifier.notified) == 1


def test_the_clear_reaches_the_run_log_before_the_delivery(run, workflow, session):
    announce(run, "implement", subject="04-x.md")

    deliver_clearing(run, workflow, session)

    assert [(e.kind, e.state) for e in RunLog(run.root).entries()] == [
        ("announced", "implement"),
        ("cleared", "implement"),
        ("delivered", "implement"),
    ]


def test_a_run_with_no_pane_recorded_is_refused_rather_than_sent_anywhere(
    run, workflow, session
):
    """tmux reads an empty -t target as the pane the operator is looking at, so
    coercing a missing pane would deliver a Prompt — and a destructive Clear —
    into whatever session happens to be attached."""
    run.tmux_pane = None
    announce(run, "implement", subject="04-x.md")

    with pytest.raises(UndrivableRun):
        drive(run, workflow, session)

    assert session.sent == []


# An adopted Run's first Prompt (ADR 0028). A Run that spawned its session was
# handed one as that session launched; a Run that joined a session already
# running is owed one, and is owed it until a turn has ended.


def adopted_at(tmp_path, state=None, *, text=WORKFLOW, **overrides):
    """A Run attached to a session that was already there — the human's own
    pane, with no session of Naiad's naming and no session id to be had.

    A start State is named for the case the feature exists for, where the early
    States were done by hand; without one the Run begins where the Workflow
    does, as any Run does.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "workflow.toml").write_text(text)
    created = RunStore(tmp_path / "runs").create(
        run_id="an-adopted-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
        adopted=True,
        start_state=state,
        **overrides,
    )
    created.attach_session(tmux_session="mine", tmux_pane="%7", claude_session_id=None)
    RunLog(created.root).record_adoption(pane="%7")
    return created


@pytest.fixture
def adopted(tmp_path):
    return adopted_at(tmp_path)


def end_turn(run):
    """Stand in for the Stop hook firing in a session that has announced
    nothing — which is every adopted session before its first Announcement."""
    Turns(run.root).record_end(latest_seq=None)


def workflow_of(run):
    return parse_workflow(run.workflow_path.read_text())


def test_an_adopted_run_is_delivered_the_prompt_of_the_state_it_was_adopted_at(
    adopted, workflow, session
):
    end_turn(adopted)

    action = drive(adopted, workflow, session)

    assert isinstance(action, Deliver)
    assert session.sent == [
        ("send", "%7", "/grill-with-docs add dark mode, then announce review")
    ]


def test_an_adopted_run_is_left_alone_until_a_turn_has_ended(adopted, workflow, session):
    """The Run joins the session while the agent is still mid-conversation: the
    Prompt waits, exactly as an Answer waits."""
    drive(adopted, workflow, session)

    assert session.sent == []


def test_the_prompt_an_adoption_was_owed_is_delivered_once_however_often_it_ticks(
    adopted, workflow, session
):
    """Nothing is announced between the delivery and the agent's first
    Announcement, so a loop reading the same signals must not send again."""
    end_turn(adopted)

    drive(adopted, workflow, session)
    drive(adopted, workflow, session)
    drive(adopted, workflow, session)

    assert len(session.sent) == 1


def test_an_adopted_runs_switches_take_a_tick_each_like_any_others(adopted, session):
    """An adopted Run has no launch for the Switches to ride as flags, so the
    ticks before its first delivery are where they arrive (ADR 0026, 0038).
    Their count is kept against no seq, as its Clear is: nothing has been
    announced yet."""
    keyed = parse_workflow(SWITCHED)
    end_turn(adopted)

    drive(adopted, keyed, session)
    drive(adopted, keyed, session)
    drive(adopted, keyed, session)

    assert session.sent == [
        ("send", "%7", "/model opus"),
        ("send", "%7", "/effort high"),
        ("send", "%7", "work, then announce done"),
    ]


def test_the_subject_an_adoption_named_reaches_the_pane_in_that_prompt(tmp_path, session):
    """The State adopted at may name a Subject, and there is no Announcement to
    carry it: it was described when the Entry was made and rides on the Run.

    A State that does not Clear, so that what is asserted is the Subject alone.
    """
    naming = (
        'name = "w"\n'
        "[[states]]\nname = 'spec'\nprompt = '/to-spec {subject}'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )
    run = adopted_at(tmp_path, "spec", text=naming, start_subject="04-x.md")
    end_turn(run)

    drive(run, parse_workflow(naming), session)

    assert session.sent == [("send", "%7", "/to-spec 04-x.md")]


def test_a_run_adopted_at_a_gate_state_notifies_and_sends_nothing(tmp_path, session):
    run = adopted_at(tmp_path, "review")
    end_turn(run)
    notifier = RecordingNotifier()

    action = drive(run, workflow_of(run), session, notifier=notifier)

    assert isinstance(action, Notify)
    assert session.sent == []
    assert "review" in notifier.notified[0][1]


def test_an_adopted_run_at_a_clearing_state_is_cleared_before_its_prompt(tmp_path, session):
    """The one divergence from kickoff (ADR 0028): a spawned Run's session holds
    nothing to discard, and an adopted one holds the whole conversation. The
    /clear goes first and the Prompt waits on the confirmation (ADR 0019)."""
    run = adopted_at(tmp_path, "implement", start_subject="04-x.md")
    end_turn(run)

    first = drive(run, workflow_of(run), session)

    assert isinstance(first, Clear)
    assert session.sent == [("clear", "%7", None)]

    land_clear(run)
    delivered = drive(run, workflow_of(run), session)

    assert isinstance(delivered, Deliver)
    assert session.sent == [
        ("clear", "%7", None),
        ("send", "%7", "/implement the ticket at 04-x.md"),
    ]


def test_a_dropped_clear_at_adoption_is_retyped_and_then_the_human_is_told(tmp_path, session):
    """The unconfirmed-Clear path behaves as delivery's already does: bounded
    retries, then the operator, and never a Prompt into an un-cleared context."""
    run = adopted_at(tmp_path, "implement", start_subject="04-x.md")
    notifier = RecordingNotifier()
    end_turn(run)

    action = None
    for _ in range(CLEAR_RETRY_LIMIT + 1):
        action = drive(
            run,
            workflow_of(run),
            session,
            notifier=notifier,
            now=_later(run, CLEAR_CONFIRM_SECONDS),
        )

    assert isinstance(action, Notify)
    assert [kind for kind, _, _ in session.sent] == ["clear"] * CLEAR_RETRY_LIMIT
    assert len(notifier.notified) == 1


def test_the_clear_an_adoption_owed_reaches_the_run_log_before_its_delivery(tmp_path, session):
    run = adopted_at(tmp_path, "implement", start_subject="04-x.md")
    end_turn(run)

    drive(run, workflow_of(run), session)
    land_clear(run)
    drive(run, workflow_of(run), session)

    assert [(e.kind, e.state) for e in RunLog(run.root).entries()] == [
        ("adopted", None),
        ("cleared", "implement"),
        ("delivered", "implement"),
    ]


def test_an_adoption_at_a_non_clearing_state_sends_the_prompt_and_nothing_else(
    adopted, workflow, session
):
    """The whole point of the feature: the conversation the early States built
    is the context the Prompt lands in, so nothing is typed ahead of it."""
    end_turn(adopted)

    drive(adopted, workflow, session)

    assert session.sent == [
        ("send", "%7", "/grill-with-docs add dark mode, then announce review")
    ]
    assert [e.kind for e in RunLog(adopted.root).entries()] == ["adopted", "delivered"]


def test_an_agent_working_on_the_prompt_it_was_adopted_with_is_not_nudged(
    adopted, workflow, session
):
    """The turn end that let the first Prompt be delivered is spent by that
    delivery, exactly as it is for a delivery answering an Announcement."""
    end_turn(adopted)
    deliver(adopted, workflow, session)

    assert drive(adopted, workflow, session, now=_later(adopted, SILENCE_SECONDS)) is NOTHING


def test_the_first_announcement_of_an_adopted_run_is_delivered_as_any_other(
    adopted, workflow, session
):
    """From its first Announcement the adopted Run is an ordinary Run: what it
    announces is delivered, and what it was adopted at is over and done with."""
    end_turn(adopted)
    drive(adopted, workflow, session)
    announce(adopted, "grill")

    action = drive(adopted, workflow, session)

    assert isinstance(action, Deliver)
    assert len(session.sent) == 2


def test_the_adoption_and_everything_after_it_reach_the_run_log(adopted, workflow, session):
    """The log is the diagnostic, and an adopted Run's is readable from the
    moment it joined the session rather than from its first Announcement."""
    end_turn(adopted)
    drive(adopted, workflow, session)
    announce(adopted, "review")
    drive(adopted, workflow, session)

    assert [(e.kind, e.state) for e in RunLog(adopted.root).entries()] == [
        ("adopted", None),
        ("delivered", "grill"),
        ("announced", "review"),
        ("notified", None),
    ]


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


def _branching_run(tmp_path, **overrides):
    """A Run whose Workflow names the Working branch in a State that Clears —
    the case the fields exist for, since a Cleared context has forgotten the
    branch it was told about at kickoff."""
    repo = tmp_path / "branched"
    repo.mkdir()
    workflow_path = repo / "workflow.toml"
    workflow_path.write_text(
        'name = "branched"\n'
        "[[states]]\nname = 'grill'\nprompt = 'work'\n"
        "[[states]]\nname = 'implement'\n"
        "prompt = 'work on {branch} based on {predecessor}'\nclear = true\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )
    fields = dict(
        run_id="branched-run",
        workflow_path=workflow_path,
        task="t",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
        working_branch="MC-AGENT-8546",
    )
    fields.update(overrides)
    run = RunStore(tmp_path / "branched-runs").create(**fields)
    run.attach_session(tmux_session="naiad-branched-run", tmux_pane="%7")
    return run, parse_workflow(workflow_path.read_text())


def test_a_prompt_after_the_first_still_names_the_branch_and_the_predecessor(
    tmp_path, session
):
    """Run-level facts, read back off the Run rather than remembered from
    kickoff: the loop runs in a process that outlives it, and the State that
    reads them Clears first."""
    run, workflow = _branching_run(tmp_path, predecessor="MC-AGENT-8000")
    announce(run, "implement")

    deliver_clearing(run, workflow, session)

    assert session.sent == [
        ("clear", "%7", None),
        ("send", "%7", "work on MC-AGENT-8546 based on MC-AGENT-8000"),
    ]


def test_the_branch_reaches_every_delivery_not_only_the_first(tmp_path, session):
    """A State repeating over a series is delivered the branch each time, for
    the reason it is delivered its Subject each time."""
    run, workflow = _branching_run(tmp_path, predecessor="MC-AGENT-8000")
    announce(run, "implement")
    deliver_clearing(run, workflow, session)
    announce(run, "implement")
    deliver_clearing(run, workflow, session)

    delivered = [message for kind, _, message in session.sent if kind == "send"]
    assert delivered == ["work on MC-AGENT-8546 based on MC-AGENT-8000"] * 2


def test_a_run_with_no_predecessor_delivers_the_prompt_with_it_empty(tmp_path, session):
    run, workflow = _branching_run(tmp_path)
    announce(run, "implement")

    deliver_clearing(run, workflow, session)

    assert ("send", "%7", "work on MC-AGENT-8546 based on ") in session.sent


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

    announce(run, "implement", subject="04-x.md")
    action = deliver_clearing(run, workflow, session, notifier=notifier)

    assert isinstance(action, Deliver)
    assert ("send", "%42", "/implement the ticket at 04-x.md") in session.sent


def test_a_later_gate_notifies_again(run, workflow, session):
    notifier = RecordingNotifier()
    announce(run, "review")
    drive(run, workflow, session, notifier=notifier)
    announce(run, "implement", subject="04-x.md")
    drive(run, workflow, session, notifier=notifier)
    announce(run, "review")

    drive(run, workflow, session, notifier=notifier)

    assert len(notifier.notified) == 2


def test_an_agent_that_ends_a_turn_without_announcing_is_nudged_in_the_session(
    run, workflow, session
):
    announce(run, "grill")
    deliver(run, workflow, session)
    session.sent.clear()
    Turns(run.root).record_end(latest_seq=1)

    action = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))

    assert action == Nudge(attempt=1)
    assert [entry[0] for entry in session.sent] == ["send"]


def test_a_second_silence_is_nudged_more_firmly_than_the_first(run, workflow, session):
    announce(run, "grill")
    deliver(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    session.sent.clear()

    first = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))
    second = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))

    assert (first, second) == (Nudge(attempt=1), Nudge(attempt=2))
    assert session.sent[0][2] != session.sent[1][2]


def test_a_third_silence_notifies_instead_of_nudging(run, workflow, session):
    notifier = RecordingNotifier()
    announce(run, "grill")
    deliver(run, workflow, session)
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


def declare_wait(run, reason, *, seconds):
    """Stand in for the agent's `naiad wait` command: the Wait recorded
    against the Run's current Announcement, starting now."""
    waits = Waits(run.root)
    waits.record(
        Announcements(run.root).latest(), reason=reason, now=_later(run, 0), seconds=seconds
    )
    return waits


def test_a_declared_wait_keeps_the_silent_agent_unnudged(run, workflow, session):
    """The screenshot case (ADR 0021): background review agents running, the
    turn correctly ended, and the wake already guaranteed — a Nudge here buys
    a wasted poll turn and marches toward a false parking."""
    announce(run, "grill")
    deliver(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    declare_wait(run, "2 review agents", seconds=SILENCE_SECONDS * 4)
    session.sent.clear()

    action = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS * 3))

    assert action is NOTHING
    assert session.sent == []


def test_an_expired_wait_is_nudged_naming_what_was_waited_on(run, workflow, session):
    announce(run, "grill")
    deliver(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    declare_wait(run, "2 review agents", seconds=SILENCE_SECONDS)
    session.sent.clear()

    action = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))

    assert action == Nudge(attempt=1, expired_wait="2 review agents")
    assert "2 review agents" in session.sent[0][2]


def test_a_fresh_wait_re_arms_the_nudge_allowance(run, workflow, session):
    """A re-declared Wait after a wake answers a new silence, so the count
    starts over rather than inheriting the expired Wait's nudges (ADR 0021)."""
    announce(run, "grill")
    drive(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    declare_wait(run, "first agent", seconds=SILENCE_SECONDS)
    drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))
    declare_wait(run, "second agent", seconds=SILENCE_SECONDS)
    session.sent.clear()

    action = drive(run, workflow, session, now=_later(run, SILENCE_SECONDS))

    assert action == Nudge(attempt=1, expired_wait="second agent")


def declare_hold(run, reason):
    """Stand in for the agent's `naiad hold` command: the Hold recorded
    against the Run's current Announcement."""
    Holds(run.root).record(Announcements(run.root).latest(), reason=reason)


def test_a_declared_hold_parks_the_run_calmly_and_indefinitely(run, workflow, session):
    """The pause case (ADR 0025): the human typed 'pause', the agent relayed
    it, and the Run must idle unnudged for as long as they stay away — told
    apart from a stall by the one calm notification."""
    notifier = RecordingNotifier()
    announce(run, "grill")
    deliver(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    declare_hold(run, "user typed 'pause' — holding until they resume")
    session.sent.clear()

    action = drive(run, workflow, session, notifier=notifier, now=_later(run, SILENCE_SECONDS * 50))

    assert isinstance(action, Notify)
    assert "held at your request" in notifier.notified[0][1]
    assert "user typed 'pause'" in notifier.notified[0][1]
    assert session.sent == []

    after = drive(
        run, workflow, session, notifier=notifier, now=_later(run, SILENCE_SECONDS * 100)
    )

    assert after is NOTHING
    assert session.sent == []
    assert len(notifier.notified) == 1


def test_a_hold_declared_after_a_silence_notification_still_notifies(run, workflow, session):
    """The likeliest real sequence: agent silent, Nudged twice, operator told,
    operator returns and types 'pause', agent holds. The Hold's notification is
    load-bearing (ADR 0025), so the earlier alarm must not swallow it."""
    notifier = RecordingNotifier()
    announce(run, "grill")
    deliver(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    for _ in range(3):
        drive(run, workflow, session, notifier=notifier, now=_later(run, SILENCE_SECONDS))
    assert len(notifier.notified) == 1

    declare_hold(run, "user typed 'pause'")
    drive(run, workflow, session, notifier=notifier, now=_later(run, 1))

    assert len(notifier.notified) == 2
    assert "held at your request" in notifier.notified[1][1]


def test_asking_a_question_lifts_the_hold(run, workflow, session):
    """A Question is the agent signalling again (ADR 0025): the Hold is keyed
    to the Announcement it was declared against, and asking makes a new one."""
    announce(run, "grill")
    drive(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    declare_hold(run, "user typed 'pause'")

    Announcements(run.root).ask(
        Question(text="Which theme is wanted?", options=("dark", "dim")), state="grill"
    )
    action = drive(run, workflow, session)

    assert isinstance(action, Consult)


def test_announcing_again_lifts_the_hold_and_the_run_moves_on(run, workflow, session):
    """The agent signalling again is what ends a Hold (ADR 0025)."""
    announce(run, "grill")
    drive(run, workflow, session)
    Turns(run.root).record_end(latest_seq=1)
    declare_hold(run, "user typed 'pause'")

    announce(run, "implement", subject="04-x.md")
    action = drive(run, workflow, session)

    assert isinstance(action, Clear)


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
    deliver(run, workflow, session)
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


class RecordingAnswerer:
    """The Answerer with the headless session taken out: it records what it was
    asked and returns whatever the test scripted."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.consulted = []

    def consult(self, specification):
        self.consulted.append(specification)
        return self.outcomes.pop(0) if self.outcomes else Answered(text="the client")


def ask(run, question, *options, then_stop=True):
    """The agent asks and then stops, which is what waiting for an answer looks
    like from outside. The turn end is what lets the answer be sent back."""
    announcement = Announcements(run.root).ask(
        Question(text=question, options=tuple(options)), state="implement"
    )
    if then_stop:
        Turns(run.root).record_end(latest_seq=announcement.seq)
    return announcement


def resolve(run, workflow, session, answerer, *, notifier=None):
    """Consult, then act on what came back — the two decisions a Question takes."""
    notifier = notifier or RecordingNotifier()
    consulted = drive(run, workflow, session, answerer=answerer, notifier=notifier)
    acted = drive(run, workflow, session, answerer=answerer, notifier=notifier)
    return consulted, acted


def test_an_unacted_on_question_consults_the_answerer_and_sends_nothing(run, workflow, session):
    ask(run, "Which module owns retries?", "the client", "the caller")
    answerer = RecordingAnswerer()

    action = drive(run, workflow, session, answerer=answerer)

    assert isinstance(action, Consult)
    assert len(answerer.consulted) == 1
    assert session.sent == []


def test_the_answerer_runs_against_the_target_repository(run, workflow, session):
    """Its answers must reflect the conventions actually in use, which it can
    only read by being in the repository."""
    ask(run, "Which module owns retries?", "the client")
    answerer = RecordingAnswerer()

    drive(run, workflow, session, answerer=answerer)

    assert answerer.consulted[0].cwd == run.target_repo


def test_the_workflows_answerer_keys_reach_the_consultation(run, session):
    keyed = parse_workflow(
        WORKFLOW
        + """
[answerer]
model = "haiku"
effort = "low"
"""
    )
    ask(run, "Which module owns retries?", "the client")
    answerer = RecordingAnswerer()

    drive(run, keyed, session, answerer=answerer)

    assert answerer.consulted[0].model == "haiku"
    assert answerer.consulted[0].effort == "low"


def test_a_workflow_without_an_answerer_table_consults_with_neither_key(run, workflow, session):
    ask(run, "Which module owns retries?", "the client")
    answerer = RecordingAnswerer()

    drive(run, workflow, session, answerer=answerer)

    assert answerer.consulted[0].model is None
    assert answerer.consulted[0].effort is None


def test_the_first_consultation_starts_an_answerer_session_and_records_it(run, workflow, session):
    ask(run, "Which module owns retries?", "the client")
    answerer = RecordingAnswerer()

    drive(run, workflow, session, answerer=answerer)

    assert answerer.consulted[0].resume is False
    assert run.answerer_session_id
    assert answerer.consulted[0].claude_session_id == run.answerer_session_id


def test_every_later_consultation_resumes_the_same_answerer_session(run, workflow, session):
    """One Answerer per Run, resumed, so that its later answers cannot
    contradict its earlier ones — the operator reads them as a single log."""
    answerer = RecordingAnswerer()
    ask(run, "Which module owns retries?", "the client")
    resolve(run, workflow, session, answerer)

    ask(run, "Where do the tests live?", "beside the code")
    resolve(run, workflow, session, answerer)

    first, second = answerer.consulted
    assert second.resume is True
    assert second.claude_session_id == first.claude_session_id


def test_an_answer_is_sent_into_the_session_and_appended_to_the_answer_log(
    run, workflow, session
):
    ask(run, "Which module owns retries?", "the client", "the caller")
    answerer = RecordingAnswerer(Answered(text="the client"))

    _, acted = resolve(run, workflow, session, answerer)

    assert isinstance(acted, Respond)
    assert "the client" in session.sent[0][2]
    entry = AnswerLog(run.root).entries()[0]
    assert (entry.question, entry.options, entry.answer, entry.escalated) == (
        "Which module owns retries?", ("the client", "the caller"), "the client", False,
    )


def test_an_escalation_notifies_and_is_logged_and_sends_nothing_into_the_session(
    run, workflow, session
):
    """Nothing may reach the agent: the Answerer declined to decide, so there
    is no answer to give, and inventing one is what escalating avoids."""
    ask(run, "Which SMS vendor?", "Twilio", "Vonage")
    answerer = RecordingAnswerer(Escalated(reason="vendor choice is not in the repository"))
    notifier = RecordingNotifier()

    _, acted = resolve(run, workflow, session, answerer, notifier=notifier)

    assert isinstance(acted, Notify)
    assert session.sent == []
    assert "vendor choice is not in the repository" in notifier.notified[0][1]
    entry = AnswerLog(run.root).entries()[0]
    assert entry.escalated is True
    assert entry.options == ("Twilio", "Vonage")


def test_a_question_is_consulted_once_however_often_the_loop_ticks(run, workflow, session):
    """Consulting is a headless Claude call: repeating it every couple of
    seconds spends money and risks contradicting the answer already sent."""
    ask(run, "Which module owns retries?", "the client")
    answerer = RecordingAnswerer()

    for _ in range(4):
        drive(run, workflow, session, answerer=answerer)

    assert len(answerer.consulted) == 1


def test_an_answered_question_is_responded_to_once_however_often_the_loop_ticks(
    run, workflow, session
):
    ask(run, "Which module owns retries?", "the client")
    answerer = RecordingAnswerer()

    for _ in range(4):
        drive(run, workflow, session, answerer=answerer)

    assert len(session.sent) == 1
    assert len(AnswerLog(run.root).entries()) == 1


def test_the_answer_log_shows_every_question_in_the_order_they_occurred(run, workflow, session):
    answerer = RecordingAnswerer(
        Answered(text="the client"), Escalated(reason="not in the repository")
    )
    ask(run, "Which module owns retries?", "the client")
    resolve(run, workflow, session, answerer)
    ask(run, "Which SMS vendor?", "Twilio")
    resolve(run, workflow, session, answerer)

    entries = AnswerLog(run.root).entries()

    assert [entry.question for entry in entries] == [
        "Which module owns retries?", "Which SMS vendor?",
    ]
    assert [entry.escalated for entry in entries] == [False, True]


def test_an_answer_is_held_back_from_a_session_still_working(run, workflow, session):
    """The agent asked and carried on rather than stopping. Sending the answer
    now would type over the work it is doing."""
    ask(run, "Which module owns retries?", "the client", then_stop=False)
    answerer = RecordingAnswerer()

    drive(run, workflow, session, answerer=answerer)
    drive(run, workflow, session, answerer=answerer)

    assert answerer.consulted, "the answerer should still be consulted; consulting sends nothing"
    assert session.sent == []


def test_every_announcement_and_every_action_reaches_the_run_log(run, workflow, session):
    """The log is the diagnostic. What it is worth depends entirely on the
    tick loop writing to it as it goes, not on anything the agent does."""
    announce(run, "grill")

    drive(run, workflow, session)

    log = RunLog(run.root)
    assert [(entry.kind, entry.state) for entry in log.entries()] == [
        ("announced", "grill"),
        ("delivered", "grill"),
    ]


def test_an_announcement_is_logged_once_however_many_ticks_read_it(run, workflow, session):
    """The loop reads the State file several times a minute."""
    announce(run, "grill")

    drive(run, workflow, session)
    drive(run, workflow, session)
    drive(run, workflow, session)

    assert [e.kind for e in RunLog(run.root).entries()].count("announced") == 1


def test_an_announcement_off_the_expected_path_is_logged_as_a_deviation(run, workflow, session):
    """The Run began at 'grill', so 'review' was owed and 'implement' is a
    departure — permitted, delivered, and written down."""
    announce(run, "implement", subject="04-x.md")

    drive(run, workflow, session)

    deviation = RunLog(run.root).deviations()[-1]
    assert deviation.state == "implement"
    assert deviation.expected == "review"


def test_an_announcement_on_the_expected_path_is_not_logged_as_a_deviation(
    run, workflow, session
):
    """Where the agent stands is read back from the log, so a Run that passed
    a Gate — announced and never delivered — must not deviate next."""
    announce(run, "review")
    drive(run, workflow, session)

    announce(run, "implement", subject="04-x.md")
    drive(run, workflow, session)

    assert RunLog(run.root).deviations() == []


def test_a_completed_run_can_be_reconstructed_from_its_log(run, workflow, session):
    """The whole point: 'it produced something strange overnight' becomes a
    readable sequence of which States it passed through and why Naiad did what
    it did — without opening the session."""
    answerer = RecordingAnswerer(Answered(text="the client"))

    announce(run, "grill")
    drive(run, workflow, session)
    asked = Announcements(run.root).ask(
        Question(text="Which module owns retries?", options=("the client", "the caller")),
        state="grill",
    )
    Turns(run.root).record_end(latest_seq=asked.seq)
    resolve(run, workflow, session, answerer)
    announce(run, "review")
    drive(run, workflow, session)
    announce(run, "done")
    drive(run, workflow, session)

    assert [(e.kind, e.state) for e in RunLog(run.root).entries()] == [
        ("announced", "grill"),
        ("delivered", "grill"),
        ("asked", "grill"),
        ("consulted", None),
        ("answered", None),
        ("announced", "review"),
        ("notified", None),
        ("announced", "done"),
        ("finished", "done"),
    ]


def test_the_run_log_says_why_the_operator_was_notified(run, workflow, session):
    announce(run, "review")

    drive(run, workflow, session)

    notified = [e for e in RunLog(run.root).entries() if e.kind == "notified"][-1]
    assert "review" in notified.detail


def test_an_announcement_that_is_never_delivered_still_records_its_deviation(
    run, workflow, session
):
    """A jump straight to the end. Naiad delivers nothing for it, so a
    Deviation recorded only alongside a delivery would lose the one most worth
    seeing."""
    announce(run, "done")

    drive(run, workflow, session)

    deviated = RunLog(run.root).deviations()[-1]
    assert deviated.state == "done"
    assert deviated.expected == "review"


def test_a_finished_run_is_not_driven_by_anything_the_agent_says_afterwards(
    run, workflow, session
):
    """The session is left alive, so the agent may well announce again into
    it. The Run is over and it is talking to the operator."""
    announce(run, "done")
    drive(run, workflow, session)

    announce(run, "implement", subject="04-x.md")

    assert drive(run, workflow, session) is NOTHING
    assert session.sent == []


def test_a_human_who_is_needed_is_told_so_as_a_notify(run, workflow, session):
    """The kind rides with the telling because a phone grades its pushes and
    the loop must not learn any service's scale to say which telling it is
    making."""
    notifier = RecordingNotifier()
    announce(run, "review")

    action = drive(run, workflow, session, notifier=notifier)

    assert isinstance(action, Notify)
    assert notifier.notified[0][2] is Notification.NOTIFY


def test_a_run_that_reached_its_terminal_state_is_told_as_a_finish(run, workflow, session):
    """Good news and a Run standing still are not equally urgent, and it is
    the loop that knows which of the two this is."""
    notifier = RecordingNotifier()
    announce(run, "done")

    action = drive(run, workflow, session, notifier=notifier)

    assert isinstance(action, Finish)
    assert notifier.notified[0][2] is Notification.FINISH
    assert "done" in notifier.notified[0][1]
