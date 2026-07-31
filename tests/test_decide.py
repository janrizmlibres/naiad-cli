"""Every rule, as data in and Action out. No tmux, no subprocess, no clock."""

import pytest

from naiad.domain.announcement import Announcement
from naiad.domain.answerer import Answered, Escalated
from naiad.domain.decide import (
    HANG_SECONDS,
    NOTHING,
    NUDGE_LIMIT,
    SILENCE_SECONDS,
    Consult,
    Deliver,
    Finish,
    Notify,
    Nudge,
    Respond,
    Signals,
    decide,
)
from naiad.domain.question import Question
from naiad.domain.workflow import parse_workflow

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "review"

[[states]]
name = "implement"
prompt = "/implement the next ticket, then announce {next_state}"
clear = true

[[states]]
name = "done"
terminal = true
"""

# A fork whose short branch ends at a Gate State, which is the shape ADR 0007
# is about: the exit an unattended Run must still be offered.
BRANCHING = """
name = "bug"

[[states]]
name = "diagnose"
prompt = "/diagnosing-bugs"
next = ["no-repro", "done"]

[[states]]
name = "no-repro"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def workflow():
    return parse_workflow(WORKFLOW)


@pytest.fixture
def branching():
    return parse_workflow(BRANCHING)


QUESTION = Question(text="Which module owns retries?", options=("the client", "the caller"))


def signals(
    state,
    *,
    seq=1,
    handled_seq=None,
    stopped=True,
    stopped_since_action=False,
    notified=False,
    nudges=0,
    idle_for=0.0,
    question=None,
    consultation=None,
    finished=False,
):
    return Signals(
        announcement=Announcement(seq=seq, state=state, question=question) if state else None,
        handled_seq=handled_seq,
        stopped=stopped,
        stopped_since_action=stopped_since_action,
        notified=notified,
        nudges=nudges,
        idle_for=idle_for,
        consultation=consultation,
        finished=finished,
    )


def test_an_unhandled_announcement_with_a_turn_ended_delivers_that_states_prompt(workflow):
    action = decide(workflow, signals("grill"))

    assert action == Deliver(
        state="grill",
        prompt="/grill-with-docs {task}",
        clear=False,
        next_states=("review",),
    )


def test_an_unhandled_announcement_with_no_turn_ended_takes_no_action(workflow):
    assert decide(workflow, signals("grill", stopped=False)) is NOTHING


def test_an_announcement_already_acted_on_takes_no_action_however_often_asked(workflow):
    handled = signals("grill", seq=7, handled_seq=7)

    assert decide(workflow, handled) is NOTHING
    assert decide(workflow, handled) is NOTHING
    assert decide(workflow, handled) is NOTHING


def test_the_same_state_announced_twice_delivers_twice(workflow):
    """Naiad acts once per Announcement, not once per change of value: the
    agent's fifth implement iteration must be delivered like the fourth."""
    fourth = decide(workflow, signals("implement", seq=4, handled_seq=3))
    fifth = decide(workflow, signals("implement", seq=5, handled_seq=4))

    assert isinstance(fourth, Deliver)
    assert isinstance(fifth, Deliver)
    assert fifth.state == fourth.state == "implement"


def test_a_state_declaring_clear_has_its_context_cleared_before_delivery(workflow):
    assert decide(workflow, signals("implement")).clear is True


def test_a_state_not_declaring_clear_keeps_its_context(workflow):
    assert decide(workflow, signals("grill")).clear is False


def test_nothing_announced_yet_takes_no_action(workflow):
    assert decide(workflow, signals(None, stopped=False)) is NOTHING


def test_a_state_with_no_prompt_is_not_delivered(workflow):
    """A Gate State: Naiad has nothing to send and the human types instead."""
    assert not isinstance(decide(workflow, signals("review")), Deliver)


def test_delivery_names_the_next_state_in_declared_order(workflow):
    assert decide(workflow, signals("implement")).next_states == ("done",)


def test_with_gates_skipped_delivery_names_the_next_state_that_has_a_prompt(workflow):
    assert decide(workflow, signals("grill"), skip_gates=True).next_states == ("implement",)


def test_delivery_from_a_branching_state_names_every_candidate(branching):
    """The delivered Prompt is where the agent reads its exits, so a fork that
    delivered one of two would decide the branch on the agent's behalf."""
    assert decide(branching, signals("diagnose")).next_states == ("no-repro", "done")


def test_a_gate_state_reached_as_a_candidate_still_notifies_with_gates_skipped(branching):
    """ADR 0007: the stop an author put on a fork is one an unattended Run
    honours, so a bug it could not reproduce parks rather than opening a pull
    request on no diagnosis."""
    delivered = decide(branching, signals("diagnose"), skip_gates=True)
    parked = decide(branching, signals("no-repro"), skip_gates=True)

    assert delivered.next_states == ("no-repro", "done")
    assert isinstance(parked, Notify)


def test_a_gate_state_notifies_the_operator(workflow):
    """Everything that ends with Naiad stopping and the human taking over is
    one behaviour: a Gate reached, an agent silent, an agent hung."""
    action = decide(workflow, signals("review"))

    assert isinstance(action, Notify)


def test_a_notification_names_why_the_operator_is_needed(workflow):
    """A notification at 3am is useless if it does not say what it is about."""
    assert "review" in decide(workflow, signals("review")).reason


def test_a_gate_state_notifies_once_however_often_the_decision_is_made(workflow):
    """The condition persists across ticks with identical signals, so a naive
    implementation notifies the operator every couple of seconds all night."""
    already = signals("review", notified=True)

    assert decide(workflow, already) is NOTHING
    assert decide(workflow, already) is NOTHING


def test_a_new_announcement_re_arms_notification(workflow):
    """notified is a fact about one Announcement. The next Gate must notify
    again, or a Run notifies its operator once and then never again."""
    action = decide(workflow, signals("review", seq=9, notified=False))

    assert isinstance(action, Notify)


def test_an_idle_agent_that_announced_nothing_is_nudged(workflow):
    """Silence is usually a forgotten Protocol rather than a stuck agent."""
    idle = signals("grill", seq=1, handled_seq=1, stopped_since_action=True, idle_for=SILENCE_SECONDS)

    assert decide(workflow, idle) == Nudge(attempt=1)


def test_an_agent_idle_for_less_than_the_silence_bound_is_left_alone(workflow):
    """Delivering into a session mid-thought types over work in progress."""
    working = signals(
        "grill", seq=1, handled_seq=1, stopped_since_action=True, idle_for=SILENCE_SECONDS - 1
    )

    assert decide(workflow, working) is NOTHING


def test_a_second_idle_period_sends_a_second_nudge(workflow):
    idle = signals(
        "grill", seq=1, handled_seq=1, stopped_since_action=True, nudges=1, idle_for=SILENCE_SECONDS
    )

    assert decide(workflow, idle) == Nudge(attempt=2)


def test_a_third_idle_period_notifies_rather_than_nudging_again(workflow):
    """The bound is the point: an agent that is genuinely stuck will not
    recover from being asked again, and unbounded nudging is Naiad fighting
    the agent rather than driving it."""
    idle = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        nudges=NUDGE_LIMIT,
        idle_for=SILENCE_SECONDS,
    )

    action = decide(workflow, idle)

    assert isinstance(action, Notify)
    silenced = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        nudges=NUDGE_LIMIT,
        idle_for=SILENCE_SECONDS,
        notified=True,
    )
    assert decide(workflow, silenced) is NOTHING


def test_nudges_are_counted_per_announcement(workflow):
    """An agent that recovers, announces, and later stalls again gets a fresh
    allowance — the count is a fact about one Announcement, like notified."""
    recovered = signals(
        "implement", seq=2, handled_seq=2, stopped_since_action=True, nudges=0,
        idle_for=SILENCE_SECONDS
    )

    assert decide(workflow, recovered) == Nudge(attempt=1)


def test_a_state_the_workflow_does_not_declare_notifies_rather_than_going_quiet(workflow):
    """The announce command rejects an unknown name, so reaching here means the
    agent found a way around it. Nobody but a human can say what was meant, and
    every abnormal outcome ends the same way: notified and waiting."""
    action = decide(workflow, signals("shipit"))

    assert isinstance(action, Notify)
    assert "shipit" in action.reason


def test_a_gate_already_notified_is_not_nudged_while_the_human_works(workflow):
    """At a Gate the human is typing into the session themselves. A Nudge is
    text typed into that session, so nudging here would type over the person
    Naiad just called — the Gate holds until they announce, however long they
    take."""
    waiting = signals(
        "review", notified=True, stopped_since_action=True, idle_for=SILENCE_SECONDS * 10
    )

    assert decide(workflow, waiting) is NOTHING


def test_a_session_producing_no_signal_at_all_notifies_on_the_timeout(workflow):
    """A hung agent never ends a turn, so nudging it is pointless: no signal
    will ever arrive and the wall clock is all there is to go on."""
    hung = signals("grill", stopped=False, idle_for=HANG_SECONDS)

    assert isinstance(decide(workflow, hung), Notify)


def test_a_turn_ending_within_the_timeout_does_not_notify(workflow):
    """A turn ended, so the session is alive and has not hung."""
    alive = signals(
        "grill", seq=1, handled_seq=1, stopped_since_action=True, idle_for=SILENCE_SECONDS - 1
    )

    assert decide(workflow, alive) is NOTHING


def test_an_agent_working_on_what_it_was_given_is_not_nudged_however_long_it_takes(workflow):
    """The turn end that let the Prompt be delivered is spent by that delivery.
    Reading it again as silence would nudge an agent working normally, and an
    implement phase routinely runs longer than the silence bound."""
    working = signals(
        "grill", seq=1, handled_seq=1, stopped=True, stopped_since_action=False,
        idle_for=SILENCE_SECONDS * 3
    )

    assert decide(workflow, working) is NOTHING


def test_an_announcement_within_the_timeout_does_not_notify(workflow):
    """The agent announced and is working on it; the clock proves nothing."""
    working = signals("grill", stopped=False, idle_for=HANG_SECONDS - 1)

    assert decide(workflow, working) is NOTHING


def test_a_hang_notifies_once_however_often_the_decision_is_made(workflow):
    hung = signals("grill", stopped=False, idle_for=HANG_SECONDS, notified=True)

    assert decide(workflow, hung) is NOTHING


def test_with_gates_skipped_delivery_is_otherwise_unchanged(workflow):
    """Skipping Gates is a resolution-time filter and nothing more: the same
    Prompt is delivered, of the same State, Clearing or not as declared."""
    kept = decide(workflow, signals("grill"))
    skipped = decide(workflow, signals("grill"), skip_gates=True)

    assert (skipped.state, skipped.prompt, skipped.clear) == (kept.state, kept.prompt, kept.clear)


def test_an_unacted_on_question_consults_the_answerer(workflow):
    """The whole point of the Answerer: a Question resolves without a human."""
    action = decide(workflow, signals("implement", question=QUESTION))

    assert action == Consult(question=QUESTION)


def test_a_question_is_consulted_even_before_a_turn_has_ended(workflow):
    """Consulting sends nothing into the session, so unlike a Prompt it cannot
    type over work in progress — and the Answerer may as well think while the
    agent finishes its turn."""
    action = decide(workflow, signals("implement", question=QUESTION, stopped=False))

    assert action == Consult(question=QUESTION)


def test_a_question_is_resolved_rather_than_its_states_prompt_redelivered(workflow):
    """A Question rides on an Announcement, so without this the agent asking
    one would be sent the Prompt it is already working on."""
    action = decide(workflow, signals("implement", seq=2, handled_seq=1, question=QUESTION))

    assert not isinstance(action, Deliver)


def test_an_answer_from_the_answerer_is_sent_back_with_its_question(workflow):
    """The Answer log needs the Question and its options beside the answer, and
    Naiad holds both halves — the agent cannot log an answer it never saw."""
    answered = signals("implement", question=QUESTION, consultation=Answered(text="the client"))

    assert decide(workflow, answered) == Respond(question=QUESTION, answer="the client")


def test_an_escalation_from_the_answerer_notifies_rather_than_responding(workflow):
    """Escalation is mechanically the Gate State: Naiad stops acting and the
    human types into the session themselves."""
    escalated = signals(
        "implement", question=QUESTION, consultation=Escalated(reason="that is a budget call")
    )

    action = decide(workflow, escalated)

    assert isinstance(action, Notify)
    assert "that is a budget call" in action.reason


def test_an_escalation_notification_carries_the_question_for_the_answer_log(workflow):
    """An escalation is what became of that Question, so the operator reading
    the log sees it beside the Questions that were answered."""
    escalated = signals(
        "implement", question=QUESTION, consultation=Escalated(reason="that is a budget call")
    )

    assert decide(workflow, escalated).question == QUESTION


def test_an_escalation_notifies_once_however_often_the_decision_is_made(workflow):
    """The condition persists with identical signals until the human acts."""
    already = signals(
        "implement",
        question=QUESTION,
        consultation=Escalated(reason="that is a budget call"),
        notified=True,
    )

    assert decide(workflow, already) is NOTHING


def test_a_question_already_acted_on_is_not_consulted_twice(workflow):
    """Consulting is a headless Claude call. Repeating it every couple of
    seconds would spend money and could contradict the answer already sent."""
    handled = signals("implement", seq=3, handled_seq=3, question=QUESTION)

    assert decide(workflow, handled) is NOTHING
    assert decide(workflow, handled) is NOTHING


def test_an_announcement_carrying_no_question_is_delivered_as_before(workflow):
    """Questions are an addition to Announcements, not a replacement."""
    assert isinstance(decide(workflow, signals("implement")), Deliver)


def test_an_answer_is_not_sent_into_a_session_that_has_not_ended_its_turn(workflow):
    """Respond types into the pane exactly as Deliver does, so it wants the
    same guard. Consulting needs none — it sends nothing — but the branch that
    sends must not inherit that exemption: the agent that asked may still be
    working, and typing over it is destructive."""
    working = signals(
        "implement", question=QUESTION, consultation=Answered(text="the client"), stopped=False
    )

    assert not isinstance(decide(workflow, working), Respond)


def test_an_answer_waiting_on_a_session_that_never_ends_a_turn_still_notifies(workflow):
    """Holding the answer back must not swallow the hang rule: an answer in
    hand cannot mean waiting on a dead session forever."""
    hung = signals(
        "implement",
        question=QUESTION,
        consultation=Answered(text="the client"),
        stopped=False,
        idle_for=HANG_SECONDS,
    )

    assert isinstance(decide(workflow, hung), Notify)


def test_an_answer_is_sent_once_the_turn_has_ended(workflow):
    """The guard delays the answer, it does not lose it."""
    stopped = signals(
        "implement", question=QUESTION, consultation=Answered(text="the client"), stopped=True
    )

    assert decide(workflow, stopped) == Respond(question=QUESTION, answer="the client")


def test_announcing_a_terminal_state_finishes_the_run(workflow):
    """The Workflow marks its last State Terminal; announcing it is what ends
    the Run, so that Naiad never needs to know what any State means."""
    assert decide(workflow, signals("done")) == Finish(state="done")


def test_a_terminal_state_is_read_from_the_workflow_rather_than_from_its_name(workflow):
    """No State name is special-cased. A Workflow whose 'done' is an ordinary
    State and whose last State is called something else must behave the same
    way round, or Naiad has learned one Workflow's vocabulary."""
    other = parse_workflow(
        "name = 'other'\n"
        "[[states]]\nname = 'start'\nprompt = '/start'\n"
        "[[states]]\nname = 'done'\nprompt = '/done'\n"
        "[[states]]\nname = 'shipped'\nterminal = true\n"
    )

    assert isinstance(decide(other, signals("done")), Deliver)
    assert decide(other, signals("shipped")) == Finish(state="shipped")


def test_a_finished_run_is_not_acted_on_again(workflow):
    """The Run is over. A tick loop that outlives it — a watch restarted, or
    one that has not noticed yet — must find nothing left to do rather than
    nudging an agent about a Run that ended."""
    over = signals("done", seq=4, finished=True, stopped_since_action=True, idle_for=HANG_SECONDS)

    assert decide(workflow, over) is NOTHING


def test_nothing_the_agent_says_after_the_end_revives_the_run(workflow):
    """The session is left alive, so the agent may well say something more
    into it — and it is talking to the operator, not to Naiad. Reading only
    the latest Announcement would drive a Run that had already ended."""
    after = signals("grill", seq=5, finished=True)

    assert decide(workflow, after) is NOTHING


def test_needing_a_human_does_not_finish_the_run(workflow):
    """Asserted beside the Terminal case because collapsing the two is the
    tempting mistake: a Run that needs a human stays alive and keeps ticking,
    and only a Terminal State ends one."""
    assert isinstance(decide(workflow, signals("review")), Notify)
    assert isinstance(decide(workflow, signals("done")), Finish)


def test_a_terminal_state_with_a_prompt_finishes_rather_than_delivering(workflow):
    """Terminal outranks delivery: the Run is over, so there is nothing left
    to send and nobody left to send it to."""
    talkative = parse_workflow(
        "name = 'other'\n"
        "[[states]]\nname = 'start'\nprompt = '/start'\n"
        "[[states]]\nname = 'shipped'\nterminal = true\nprompt = '/celebrate'\n"
    )

    assert decide(talkative, signals("shipped")) == Finish(state="shipped")
