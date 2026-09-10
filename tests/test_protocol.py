"""The Protocol, as text.

Asserted on what the agent must be able to read out of it — the two commands,
the instruction not to ask a human, and which State to announce next — rather
than on exact wording, which is prose and will be tuned.
"""

from naiad.domain.decide import NUDGE_LIMIT
from naiad.domain.protocol import (
    render_adoption,
    render_answer,
    render_compaction,
    render_nudge,
    render_protocol,
)


def test_names_the_command_that_announces_a_state():
    assert "naiad state" in render_protocol(next_states=("spec",))


def test_names_the_command_that_asks_a_question():
    assert "naiad ask" in render_protocol(next_states=("spec",))


def test_names_the_subject_flag_and_says_when_it_is_needed():
    """A Cleared context has only the Protocol to go on, so a flag it is never
    told about is one it will be rejected for omitting (ADR 0009).

    Described by what it is for rather than by the placeholder that requires
    it: the agent never reads the Workflow file, so naming `{subject}` would
    point it at something it cannot inspect."""
    protocol = render_protocol(next_states=("spec",))

    assert "--subject" in protocol
    assert "series" in protocol


def test_teaches_one_question_at_a_time():
    """A second Question would replace the first unanswered — only the latest
    Announcement is kept — so the rule is taught up front, not only in the
    refusal that enforces it."""
    protocol = render_protocol(next_states=("spec",))

    assert "one question at a time" in protocol


def test_an_answer_invites_the_next_question():
    """The serial-ask protocol's memory-free half: an agent whose later
    questions were refused re-asks on the answer's arrival, not from memory."""
    answer = render_answer("use the client")

    assert "Answer: use the client" in answer
    assert "ask the next one now" in answer


def test_names_the_command_that_declares_a_wait():
    """A freshly Cleared context knows only what the Protocol tells it, and an
    agent that cannot declare its wait is read as silent (ADR 0021)."""
    protocol = render_protocol(next_states=("spec",))

    assert "naiad wait" in protocol
    assert "--seconds" in protocol


def test_names_the_command_that_declares_a_hold():
    """The human's pause reaches Naiad only through the agent (ADR 0002), and
    an agent that cannot relay it improvises with bounded waits instead
    (ADR 0025)."""
    protocol = render_protocol(next_states=("spec",))

    assert "naiad hold" in protocol
    assert "pause" in protocol.lower()


def test_instructs_the_agent_never_to_ask_a_human_directly():
    protocol = render_protocol(next_states=("spec",)).lower()

    assert "never" in protocol
    assert "ask" in protocol and "human" in protocol


def test_names_the_expected_next_state():
    assert "spec" in render_protocol(next_states=("spec",))


def test_at_a_fork_every_candidate_is_named():
    """Naming one of two would bias the agent toward whichever the Workflow
    author happened to list first, in precisely the case where its judgment is
    the whole point (ADR 0001). It is also all a Cleared agent has to go on."""
    protocol = render_protocol(next_states=("no-repro", "pull-request"))

    assert "no-repro" in protocol
    assert "pull-request" in protocol


def test_a_fork_is_phrased_as_a_choice_rather_than_an_instruction():
    """Told to announce both, an agent standing at a fork would try to."""
    protocol = render_protocol(next_states=("no-repro", "pull-request")).lower()

    assert "whichever" in protocol or "one of" in protocol


def test_the_commands_are_named_as_the_agent_must_actually_invoke_them():
    """A session's PATH is whatever tmux inherited, which need not hold the
    naiad that is driving the Run. Naming a command the agent cannot run costs
    it the ability to participate at all."""
    protocol = render_protocol(next_states=("spec",), naiad="/opt/naiad/bin/naiad")

    assert "/opt/naiad/bin/naiad state" in protocol
    assert "/opt/naiad/bin/naiad ask" in protocol
    assert "/opt/naiad/bin/naiad wait" in protocol
    assert "/opt/naiad/bin/naiad hold" in protocol


def test_a_run_with_no_next_state_is_told_so_rather_than_left_a_placeholder():
    protocol = render_protocol(next_states=())

    assert "{" not in protocol
    assert "None" not in protocol


def test_a_nudge_tells_the_agent_what_to_run_to_get_the_run_moving():
    assert "naiad state" in render_nudge(attempt=1)


def test_a_nudge_names_the_command_as_the_agent_must_invoke_it():
    assert "/opt/naiad/bin/naiad state" in render_nudge(attempt=1, naiad="/opt/naiad/bin/naiad")


def test_the_second_nudge_is_worded_more_firmly_than_the_first():
    """A second reminder identical to the first is a reminder the agent has
    already ignored once; it says instead that a human is about to be called."""
    first = render_nudge(attempt=1)
    second = render_nudge(attempt=2)

    assert first != second
    assert "human" in second and "human" not in first


def test_the_first_nudge_teaches_the_wait_verb():
    """The Nudge is the teachable moment: it arrives precisely when an
    undeclared wait is being misread as silence (ADR 0021)."""
    assert "naiad wait" in render_nudge(attempt=1)
    assert "naiad wait" not in render_nudge(attempt=2)


def test_the_first_nudge_teaches_the_hold_verb():
    """The other lesson the same moment carries: a human's pause answered with
    silence is misread exactly like an undeclared wait (ADR 0025)."""
    assert "naiad hold" in render_nudge(attempt=1)
    assert "naiad hold" not in render_nudge(attempt=2)


def test_a_nudge_after_an_expired_wait_names_what_was_waited_on():
    """Sent to look at the thing it declared, rather than accused of
    forgetting a Protocol it followed."""
    nudge = render_nudge(attempt=1, expired_wait="2 review agents")

    assert "2 review agents" in nudge
    assert "naiad state" in nudge


def test_the_second_nudge_after_an_expired_wait_still_warns_of_the_human():
    second = render_nudge(attempt=2, expired_wait="2 review agents")

    assert "2 review agents" in second
    assert "human" in second


def test_no_nudge_is_left_holding_a_placeholder():
    for expired_wait in (None, "2 review agents"):
        for attempt in (1, 2):
            assert "{" not in render_nudge(attempt=attempt, expired_wait=expired_wait)


def test_there_is_a_wording_for_every_nudge_naiad_is_willing_to_send():
    """The bound lives in the decision function and the words live here; if
    they drift apart, a nudged agent gets a traceback instead of a reminder."""
    for attempt in range(1, NUDGE_LIMIT + 1):
        assert render_nudge(attempt=attempt)
        assert render_nudge(attempt=attempt, expired_wait="a check")


# The Adoption output: what a hitherto-undriven agent is taught at the moment it
# hands its session over (ADR 0028). It is the Protocol plus what only an
# Adoption has to say — settle the branch, end the turn, and relay a warning
# when nothing is supervising.


def adoption(**overrides):
    fields = dict(next_states=("spec",), working_branch="MC-AGENT-8546", supervised=True)
    fields.update(overrides)
    return render_adoption(**fields)


def test_an_adoption_teaches_the_whole_protocol():
    """The manual session never met the SessionStart injection and no Clear
    will fire before the agent must announce, so this output is the only place
    it learns the verbs."""
    taught = adoption()

    assert "naiad state" in taught
    assert "naiad ask" in taught
    assert "naiad wait" in taught
    assert "naiad hold" in taught


def test_an_adoption_names_the_state_expected_after_the_one_it_starts_at():
    assert "spec" in adoption(next_states=("spec",))


def test_an_adoption_tells_the_agent_to_end_its_turn():
    """Nothing arrives while the turn runs: delivery waits for the Turn to end,
    so an agent that carries on working is an agent nothing reaches."""
    assert "end your turn" in adoption().lower()


def test_an_adoption_says_the_prompt_arrives_once_the_lane_is_free():
    """An Adoption waits its Lane turn like any Entry, so an agent told only to
    end its turn would read the silence that follows as a failure."""
    taught = adoption().lower()

    assert "lane" in taught
    assert "prompt" in taught


def test_an_adoption_carrying_a_branch_names_it_rather_than_asking_for_one():
    """The human already made it and the Entry claims it, so an agent told to
    derive one here would create a second branch for the same work."""
    taught = adoption(working_branch="MC-AGENT-8546")

    assert "MC-AGENT-8546" in taught
    assert "naiad branch" not in taught


def test_an_adoption_carrying_no_branch_asks_the_agent_to_derive_and_declare_one():
    """Both Workflow branch heads are skipped by a mid-Workflow start, so the
    ADR 0022 discipline moves into the act of adopting."""
    taught = adoption(working_branch=None)

    assert "naiad branch" in taught
    assert "None" not in taught


def test_an_adoption_with_nothing_supervising_quotes_the_command_that_starts_one():
    """A queued Adoption nobody will ever take is the failure this warning
    exists to prevent; the agent relays it to the human."""
    taught = adoption(supervised=False)

    assert "naiad queue watch" in taught


def test_an_adoption_a_supervisor_will_take_carries_no_warning():
    """The remedy is only a remedy when there is something to remedy; quoted
    always, it would be relayed always."""
    assert "naiad queue watch" not in adoption(supervised=True)


def test_an_adoption_names_the_commands_as_the_agent_must_invoke_them():
    """A session's PATH is whatever the human's shell held, which need not hold
    the naiad that will drive the Run."""
    taught = render_adoption(
        next_states=("spec",),
        working_branch=None,
        supervised=False,
        naiad="/opt/naiad/bin/naiad",
    )

    assert "/opt/naiad/bin/naiad state" in taught
    assert "/opt/naiad/bin/naiad branch" in taught
    assert "/opt/naiad/bin/naiad queue watch" in taught


def test_no_adoption_is_left_holding_a_placeholder():
    for working_branch in (None, "MC-AGENT-8546"):
        for supervised in (True, False):
            assert "{" not in adoption(working_branch=working_branch, supervised=supervised)


def compaction(**overrides):
    fields = dict(state="implement", subject=".scratch/x/issues/04-toggle.md", question=None)
    fields.update(overrides)
    return render_compaction(**fields)


def test_after_a_compaction_the_agent_is_told_which_state_it_stands_in():
    """A summary can lose the phase the agent was in, and a Protocol alone —
    'when this phase is done announce X' — invites a fresh start on a half-done
    ticket, which is the Clear failure in different clothes (ADR 0047)."""
    told = compaction()

    assert "implement" in told
    assert ".scratch/x/issues/04-toggle.md" in told


def test_after_a_compaction_the_agent_is_told_to_carry_on_rather_than_start_over():
    assert "carry on" in compaction().lower()


def test_a_state_with_no_subject_is_named_without_one():
    told = compaction(subject=None)

    assert "implement" in told
    assert "None" not in told


def test_an_unanswered_question_is_repeated_so_it_is_not_asked_again():
    """An agent whose summary lost its own Question would ask it again into a
    refusal — one Question at a time — so the text is handed back with the
    instruction not to."""
    told = compaction(question="Which module owns retries?")

    assert "Which module owns retries?" in told
    assert "not ask it again" in told.lower()


def test_with_no_question_open_none_is_mentioned():
    assert "question" not in compaction().lower()


def test_no_compaction_reminder_is_left_holding_a_placeholder():
    for told in (compaction(), compaction(subject=None, question="Why?")):
        assert "{" not in told and "}" not in told
