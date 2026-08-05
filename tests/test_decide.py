"""Every rule, as data in and Action out. No tmux, no subprocess, no clock."""

import pytest

from naiad.domain.announcement import Announcement
from naiad.domain.answerer import Answered, Escalated
from naiad.domain.decide import (
    CLEAR_CONFIRM_SECONDS,
    CLEAR_RETRY_LIMIT,
    HANG_SECONDS,
    NOTHING,
    NUDGE_LIMIT,
    SILENCE_SECONDS,
    Clear,
    Consult,
    Deliver,
    Finish,
    Notify,
    Nudge,
    Opening,
    Respond,
    Signals,
    Switch,
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


# A Workflow whose States carry both Switches, so the order they are typed in
# can be read off the ticks.
SWITCHED = """
name = "feature"

model = "sonnet"
effort = "medium"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"
model = "opus"

[[states]]
name = "spec"
prompt = "/to-spec {task}"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def switched():
    return parse_workflow(SWITCHED)


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
    subject=None,
    cleared=False,
    clear_attempts=0,
    switches=0,
    belief=None,
    handed_over=False,
    waiting=False,
    wait_reason=None,
    holding=False,
    hold_reason=None,
    opening=None,
):
    return Signals(
        announcement=(
            Announcement(seq=seq, state=state, question=question, subject=subject)
            if state
            else None
        ),
        opening=opening,
        handled_seq=handled_seq,
        stopped=stopped,
        stopped_since_action=stopped_since_action,
        notified=notified,
        nudges=nudges,
        idle_for=idle_for,
        consultation=consultation,
        finished=finished,
        cleared=cleared,
        clear_attempts=clear_attempts,
        switches=switches,
        belief=belief or {},
        handed_over=handed_over,
        waiting=waiting,
        wait_reason=wait_reason,
        holding=holding,
        hold_reason=hold_reason,
    )


def test_an_unhandled_announcement_with_a_turn_ended_delivers_that_states_prompt(workflow):
    action = decide(workflow, signals("grill"))

    assert action == Deliver(
        state="grill",
        prompt="/grill-with-docs {task}",
        next_states=("review",),
    )


def test_the_model_is_switched_before_the_prompt(switched):
    """Each Switch is its own Action on its own tick (ADR 0038). The session
    discards whatever arrives while it is handling a slash command, so a Switch
    and the Prompt behind it cannot be typed in one go."""
    action = decide(switched, signals("grill"))

    assert action == Switch(state="grill", setting="model", value="opus")


def test_the_effort_is_switched_on_the_tick_after_the_model(switched):
    action = decide(switched, signals("grill", switches=1))

    assert action == Switch(state="grill", setting="effort", value="medium")


def test_the_prompt_follows_once_every_switch_has_been_typed(switched):
    action = decide(switched, signals("grill", switches=2))

    assert action == Deliver(
        state="grill",
        prompt="/grill-with-docs {task}",
        next_states=("spec",),
    )


def test_a_state_the_session_already_holds_types_no_switch(switched):
    """A Switch carries what the Session does not already hold (ADR 0039). The
    settings are sticky, so re-typing what is there buys nothing and costs the
    State two Ticks."""
    action = decide(switched, signals("grill", belief={"model": "opus", "effort": "medium"}))

    assert action == Deliver(
        state="grill",
        prompt="/grill-with-docs {task}",
        next_states=("spec",),
    )


def test_only_the_setting_that_changed_is_typed(switched):
    """The comparison is per setting rather than over the pair, so a State that
    moves the Model and keeps the Effort spends one Tick and not two."""
    held = {"model": "opus", "effort": "medium"}

    assert decide(switched, signals("spec", belief=held)) == Switch(
        state="spec", setting="model", value="sonnet"
    )
    assert decide(switched, signals("spec", switches=1, belief=held)) == Deliver(
        state="spec",
        prompt="/to-spec {task}",
        next_states=("done",),
    )


def test_a_hand_off_to_a_human_types_every_setting_again(switched):
    """The belief is discarded where a human has had the keyboard, and every
    setting the State declares goes in again though none of them changed (ADR
    0039). It is what the narrowing gives up and this gives back: past a Notify
    is the one moment Naiad knows its belief may be wrong."""
    held = {"model": "opus", "effort": "medium"}

    assert decide(switched, signals("grill", belief=held, handed_over=True)) == Switch(
        state="grill", setting="model", value="opus"
    )
    assert decide(
        switched, signals("grill", switches=1, belief=held, handed_over=True)
    ) == Switch(state="grill", setting="effort", value="medium")
    assert decide(
        switched, signals("grill", switches=2, belief=held, handed_over=True)
    ) == Deliver(
        state="grill",
        prompt="/grill-with-docs {task}",
        next_states=("spec",),
    )


def test_a_hand_off_types_nothing_for_a_state_that_declares_nothing(workflow):
    """The hand-off discards the belief; it does not invent settings. A file
    mentioning neither key still leaves the session alone."""
    action = decide(workflow, signals("grill", handed_over=True))

    assert isinstance(action, Deliver)


def test_a_belief_of_the_wrong_value_is_typed_over(switched):
    """Held is not the same as held correctly: a Session believed to be on one
    Model still gets the Switch for another."""
    action = decide(switched, signals("grill", belief={"model": "sonnet", "effort": "medium"}))

    assert action == Switch(state="grill", setting="model", value="opus")


def test_a_workflow_without_the_keys_delivers_on_the_first_tick(workflow):
    """No Switch to type is no tick spent: a file mentioning neither key leaves
    the session's settings alone, and its delivery is what it always was."""
    action = decide(workflow, signals("grill"))

    assert isinstance(action, Deliver)


def test_a_state_with_one_switch_spends_one_tick_on_it():
    """The sequence is built from the Switches a State actually has, so a file
    naming one key does not spend a tick waiting for the other."""
    model_only = parse_workflow(
        """
        name = "feature"

        model = "sonnet"

        [[states]]
        name = "grill"
        prompt = "/grill-with-docs {task}"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert decide(model_only, signals("grill")) == Switch(
        state="grill", setting="model", value="sonnet"
    )
    assert decide(model_only, signals("grill", switches=1)) == Deliver(
        state="grill", prompt="/grill-with-docs {task}", next_states=("done",)
    )


def test_a_clearing_state_clears_before_it_switches():
    """The Clear keeps its place at the head of delivery (ADR 0019): it is the
    one step confirmed rather than spaced, and nothing follows it until the
    SessionStart hook says the context is gone."""
    clearing = parse_workflow(
        """
        name = "feature"

        model = "sonnet"

        [[states]]
        name = "implement"
        prompt = "/implement"
        clear = true

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert decide(clearing, signals("implement")) == Clear(state="implement", attempt=1)
    assert decide(clearing, signals("implement", cleared=True)) == Switch(
        state="implement", setting="model", value="sonnet"
    )


def test_delivery_carries_the_announcements_subject(workflow):
    """The Subject rides from the Announcement to the delivered Prompt, which
    is what lets the selection be made before the Clear rather than after it
    (ADR 0009)."""
    action = decide(workflow, signals("implement", subject="04-x.md", cleared=True))

    assert action.subject == "04-x.md"


def test_delivery_of_a_state_announced_without_a_subject_carries_none(workflow):
    action = decide(workflow, signals("grill"))

    assert action.subject is None


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
    fourth = decide(workflow, signals("implement", seq=4, handled_seq=3, cleared=True))
    fifth = decide(workflow, signals("implement", seq=5, handled_seq=4, cleared=True))

    assert isinstance(fourth, Deliver)
    assert isinstance(fifth, Deliver)
    assert fifth.state == fourth.state == "implement"


def test_a_state_declaring_clear_is_cleared_before_it_is_delivered(workflow):
    """The Clear splits off from delivery as its own Action, so that the /clear
    can be confirmed before the Prompt follows it (ADR 0019)."""
    assert decide(workflow, signals("implement")) == Clear(state="implement", attempt=1)


def test_a_cleared_state_is_then_delivered(workflow):
    """Once the Clear is confirmed the Prompt follows, and it does not Clear
    again — the Clear Action did that."""
    action = decide(workflow, signals("implement", cleared=True))

    assert action == Deliver(
        state="implement",
        prompt="/implement the next ticket, then announce {next_state}",
        next_states=("done",),
    )


def test_a_state_not_declaring_clear_is_delivered_without_clearing(workflow):
    assert isinstance(decide(workflow, signals("grill")), Deliver)


def test_a_typed_clear_is_waited_on_before_it_is_judged_dropped(workflow):
    """The /clear has been typed; until the confirm window is up it may still
    land, so Naiad does nothing rather than re-typing over a Clear on its way."""
    waiting = signals("implement", clear_attempts=1, idle_for=CLEAR_CONFIRM_SECONDS - 1)

    assert decide(workflow, waiting) is NOTHING


def test_a_dropped_clear_is_retyped_once_the_confirm_window_passes(workflow):
    """No marker within the window means the /clear was dropped: it is typed
    again, the attempt numbered so the retry reads apart from the first."""
    dropped = signals("implement", clear_attempts=1, idle_for=CLEAR_CONFIRM_SECONDS)

    assert decide(workflow, dropped) == Clear(state="implement", attempt=2)


def test_a_clear_that_never_lands_notifies_after_the_retry_limit(workflow):
    """Bounded like a Nudge: past the limit the human is told rather than the
    session Cleared forever, and delivering into an un-cleared context — the
    bug this exists to prevent — is never done on purpose."""
    exhausted = signals(
        "implement", clear_attempts=CLEAR_RETRY_LIMIT, idle_for=CLEAR_CONFIRM_SECONDS
    )

    action = decide(workflow, exhausted)

    assert isinstance(action, Notify)
    silenced = signals(
        "implement",
        clear_attempts=CLEAR_RETRY_LIMIT,
        idle_for=CLEAR_CONFIRM_SECONDS,
        notified=True,
    )
    assert decide(workflow, silenced) is NOTHING


def test_a_confirmed_clear_delivers_rather_than_retrying_however_many_were_typed(workflow):
    """Confirmation wins over the attempt count: a Clear that landed is
    delivered, not re-typed, even if a retry was already in flight."""
    landed = signals(
        "implement", cleared=True, clear_attempts=CLEAR_RETRY_LIMIT, idle_for=CLEAR_CONFIRM_SECONDS
    )

    assert isinstance(decide(workflow, landed), Deliver)


def test_a_clear_is_not_typed_before_a_turn_has_ended(workflow):
    """A Clear types into the session, so it wants the same guard delivery does:
    an agent still working would be Cleared out from under itself."""
    assert decide(workflow, signals("implement", stopped=False)) is NOTHING


def test_nothing_announced_yet_takes_no_action(workflow):
    assert decide(workflow, signals(None, stopped=False)) is NOTHING


# An Adoption: a Run that joined a session already running has
# announced nothing, and what it is owed is the Prompt of the State it was
# adopted at (ADR 0028).


def test_a_run_adopted_at_a_state_is_owed_that_states_prompt(workflow):
    action = decide(workflow, signals(None, opening=Opening(state="grill")))

    assert action == Deliver(
        state="grill",
        prompt="/grill-with-docs {task}",
        next_states=("review",),
    )


def test_the_prompt_an_adoption_is_owed_waits_for_a_turn_to_end(workflow):
    """The never-type-over-a-working-agent rule an Answer already obeys: the
    adopted session is mid-conversation, and its agent is most likely still
    writing when the Supervisor reaches the Entry."""
    owed = signals(None, opening=Opening(state="grill"), stopped=False)

    assert decide(workflow, owed) is NOTHING


def test_an_adoption_types_its_switches_before_that_prompt(switched):
    """The Switches precede Prompt delivery wherever it happens (ADR 0026, 0038).
    A spawned Run wears them as flags on its launch; an adopted Run has no
    launch, so the ticks before its first delivery are where they arrive."""
    action = decide(switched, signals(None, opening=Opening(state="spec")))

    assert action == Switch(state="spec", setting="model", value="sonnet")


def test_an_adoption_delivers_once_its_switches_are_typed(switched):
    action = decide(switched, signals(None, opening=Opening(state="spec"), switches=2))

    assert action == Deliver(
        state="spec",
        prompt="/to-spec {task}",
        next_states=("done",),
    )


def test_the_subject_an_adoption_named_rides_that_delivery(workflow):
    """There is no Announcement to carry it: an Adoption's Subject was named
    when the Entry was made, and the State adopted at may name it (ADR 0009).

    Past a Clear, which is what the Subject is for: the context that could have
    named it has been discarded by the time the Prompt goes out."""
    owed = signals(None, opening=Opening(state="implement", subject="04-x.md"), cleared=True)

    assert decide(workflow, owed).subject == "04-x.md"


def test_a_run_adopted_at_a_gate_state_parks_for_the_human(workflow):
    """The general rule, unchanged: a Gate State has nothing to deliver, so the
    human types into the session and Naiad stands back."""
    action = decide(workflow, signals(None, opening=Opening(state="review")))

    assert isinstance(action, Notify)
    assert "review" in action.reason


def test_a_run_adopted_at_a_state_the_workflow_no_longer_declares_notifies(workflow):
    """The checks were made when the Entry was queued and again at the
    Run was attached; a Workflow edited after that leaves nothing to deliver and
    nobody but a human to say what was meant."""
    action = decide(workflow, signals(None, opening=Opening(state="spek")))

    assert isinstance(action, Notify)
    assert "spek" in action.reason


def test_an_adopted_session_that_produces_no_signal_at_all_is_not_waited_on_forever(workflow):
    """No turn end means no delivery, but a session that died before it could
    end one would otherwise be waited on for good."""
    hung = signals(None, opening=Opening(state="grill"), stopped=False, idle_for=HANG_SECONDS)

    assert isinstance(decide(workflow, hung), Notify)


def test_a_run_adopted_at_a_clearing_state_is_cleared_before_that_prompt(workflow):
    """The one place an Adoption diverges from kickoff. Kickoff ignores the
    first State's Clear because a new session holds nothing to discard; the
    session an Adoption joins holds everything, and the Workflow's declaration
    of a clean start is not Naiad's to overrule (ADR 0028)."""
    action = decide(workflow, signals(None, opening=Opening(state="implement")))

    assert action == Clear(state="implement", attempt=1)


def test_the_prompt_an_adoption_is_owed_follows_only_a_confirmed_clear(workflow):
    """The handshake an announced Clearing State already obeys, unchanged: the
    Prompt does not follow the /clear on faith (ADR 0019)."""
    owed = signals(None, opening=Opening(state="implement"))

    assert isinstance(decide(workflow, owed), Clear)
    landed = signals(None, opening=Opening(state="implement"), cleared=True, clear_attempts=1)
    assert isinstance(decide(workflow, landed), Deliver)


def test_a_clear_an_adoption_owes_is_not_typed_before_a_turn_has_ended(workflow):
    """A Clear types into the session, and the session an Adoption joins is the
    human's own: Clearing one still working discards the conversation the
    feature exists to keep."""
    owed = signals(None, opening=Opening(state="implement"), stopped=False)

    assert decide(workflow, owed) is NOTHING


def test_a_dropped_clear_at_adoption_is_retyped_within_the_bound(workflow):
    """The unconfirmed-Clear path behaves as delivery's already does: a window
    is waited, then the /clear is typed again."""
    waiting = signals(
        None,
        opening=Opening(state="implement"),
        clear_attempts=1,
        idle_for=CLEAR_CONFIRM_SECONDS - 1,
    )
    dropped = signals(
        None, opening=Opening(state="implement"), clear_attempts=1, idle_for=CLEAR_CONFIRM_SECONDS
    )

    assert decide(workflow, waiting) is NOTHING
    assert decide(workflow, dropped) == Clear(state="implement", attempt=2)


def test_a_clear_at_adoption_that_never_lands_tells_the_human(workflow):
    """Past the bound Naiad stops rather than delivering the Prompt into the
    context that never cleared."""
    exhausted = signals(
        None,
        opening=Opening(state="implement"),
        clear_attempts=CLEAR_RETRY_LIMIT,
        idle_for=CLEAR_CONFIRM_SECONDS,
    )

    assert isinstance(decide(workflow, exhausted), Notify)


def test_an_announcement_settles_what_is_owed_rather_than_the_adoption(workflow):
    """From its first Announcement the adopted Run is an ordinary Run: what it
    said it is doing outranks what it was adopted at."""
    announced = signals("implement", cleared=True, opening=Opening(state="grill"))

    assert decide(workflow, announced).state == "implement"


def test_a_state_with_no_prompt_is_not_delivered(workflow):
    """A Gate State: Naiad has nothing to send and the human types instead."""
    assert not isinstance(decide(workflow, signals("review")), Deliver)


def test_delivery_names_the_next_state_in_declared_order(workflow):
    assert decide(workflow, signals("implement", cleared=True)).next_states == ("done",)


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


def test_a_declared_wait_is_not_silence(workflow):
    """The agent said its silence was deliberate, so no reminder is owed
    however long the silence bound has been exceeded (ADR 0021)."""
    waiting = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        idle_for=SILENCE_SECONDS * 3,
        waiting=True,
        wait_reason="2 review agents",
    )

    assert decide(workflow, waiting) is NOTHING


def test_an_expired_wait_resumes_the_silence_rule_naming_the_wait(workflow):
    """Expiry re-arms the one recovery shape rather than inventing another,
    and the Nudge names what was waited on so the agent looks there first."""
    expired = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        idle_for=SILENCE_SECONDS,
        waiting=False,
        wait_reason="2 review agents",
    )

    assert decide(workflow, expired) == Nudge(attempt=1, expired_wait="2 review agents")


def test_an_expired_wait_still_parks_past_the_nudge_limit(workflow):
    """A Wait changes when the silence rule runs, never where it ends."""
    exhausted = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        idle_for=SILENCE_SECONDS,
        nudges=NUDGE_LIMIT,
        waiting=False,
        wait_reason="2 review agents",
    )

    assert isinstance(decide(workflow, exhausted), Notify)


def test_an_announcement_is_delivered_regardless_of_an_outstanding_wait(workflow):
    """Announcing supersedes waiting: the phase is done, whatever the agent
    thought it was still waiting on when it declared."""
    announced = signals(
        "grill", seq=2, handled_seq=1, stopped=True, waiting=True, wait_reason="a check"
    )

    action = decide(workflow, announced)

    assert isinstance(action, Deliver)


def test_a_hold_parks_the_run_at_the_humans_request(workflow):
    """A Hold is a park the human asked for: deliberate, immediate, and worded
    calmly rather than as a failure (ADR 0025)."""
    held = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        holding=True,
        hold_reason="user typed 'pause'",
    )

    assert decide(workflow, held) == Notify(reason="held at your request: user typed 'pause'")


def test_a_hold_has_no_clock(workflow):
    """No expiry, no budget, no Nudges: the silence bound and the nudge count
    say nothing while a Hold stands (ADR 0025)."""
    held = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        notified=True,
        nudges=NUDGE_LIMIT,
        idle_for=SILENCE_SECONDS * 100,
        holding=True,
        hold_reason="user typed 'pause'",
    )

    assert decide(workflow, held) is NOTHING


def test_a_hold_notifies_once_not_every_tick(workflow):
    held = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        notified=True,
        holding=True,
        hold_reason="user typed 'pause'",
    )

    assert decide(workflow, held) is NOTHING


def test_a_hold_wins_over_an_outstanding_wait(workflow):
    """A Hold declared while a Wait stands is the newer signal — the wait
    command releases any Hold, so both standing means the Hold came second."""
    held = signals(
        "grill",
        seq=1,
        handled_seq=1,
        stopped_since_action=True,
        waiting=True,
        wait_reason="a check",
        holding=True,
        hold_reason="user typed 'pause'",
    )

    assert decide(workflow, held) == Notify(reason="held at your request: user typed 'pause'")


def test_an_announcement_is_delivered_regardless_of_an_outstanding_hold(workflow):
    """The agent signalling again is what ends a Hold (ADR 0025), so an
    Announcement is acted on however the hold signals read."""
    announced = signals(
        "grill", seq=2, handled_seq=1, stopped=True, holding=True, hold_reason="user typed 'pause'"
    )

    assert isinstance(decide(workflow, announced), Deliver)


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

    assert (skipped.state, skipped.prompt) == (kept.state, kept.prompt)


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
    assert isinstance(decide(workflow, signals("implement", cleared=True)), Deliver)


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
