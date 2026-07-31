"""What the Answerer is asked and what its reply means. Pure: no session is run."""

import naiad.adapters.answerer as adapter
from naiad.adapters.answerer import command_for
from naiad.domain.answerer import (
    ANSWER_MARKER,
    ESCALATE_MARKER,
    Answered,
    ConsultationSpec,
    Escalated,
    parse_outcome,
    render_consultation,
)
from naiad.domain.question import Question

RETRIES = Question(text="Which module owns retries?", options=("the client", "the caller"))


def test_the_consultation_states_the_authority_boundary_as_repository_discoverability():
    """The boundary is the whole of the Answerer's mandate. Stated as a list of
    forbidden topics it would not generalise; stated as a test the Answerer can
    apply, it does."""
    consultation = render_consultation(RETRIES, task="add dark mode").lower()

    assert "discoverable in this repository" in consultation


def test_the_consultation_names_what_is_inferable_and_what_must_be_escalated():
    consultation = render_consultation(RETRIES, task="add dark mode").lower()

    for inferable in ("architecture", "conventions", "naming"):
        assert inferable in consultation
    for invented in ("credentials", "spend", "priorities"):
        assert invented in consultation


def test_the_consultation_carries_the_question_and_every_option():
    """The Answerer chooses between the alternatives the agent faced."""
    consultation = render_consultation(RETRIES, task="add dark mode")

    assert RETRIES.text in consultation
    for option in RETRIES.options:
        assert option in consultation


def test_the_consultation_carries_the_task_the_run_is_working_on():
    """A question about retries is answered differently for a caching change
    than for a dark mode one."""
    assert "add dark mode" in render_consultation(RETRIES, task="add dark mode")


def test_a_marked_answer_is_read_as_an_answer():
    reply = f"Looking at the client, it already retries.\n{ANSWER_MARKER} the client"

    assert parse_outcome(reply) == Answered(text="the client")


def test_a_marked_escalation_is_read_as_an_escalation():
    reply = f"Nothing here names a vendor.\n{ESCALATE_MARKER} vendor choice is not in the repo"

    assert parse_outcome(reply) == Escalated(reason="vendor choice is not in the repo")


def test_the_last_marked_line_wins():
    """A reply that quotes the instructions before answering must be read by
    its answer rather than by the quotation."""
    reply = f"I must end with {ANSWER_MARKER} <x>\nActually:\n{ANSWER_MARKER} the caller"

    assert parse_outcome(reply) == Answered(text="the caller")


def test_a_reply_with_no_marked_line_escalates_rather_than_guessing():
    """Naiad cannot tell an unparseable answer from a wrong one, and sending
    something it does not understand into the session is worse than waking the
    operator — who is exactly who an Escalation calls."""
    assert isinstance(parse_outcome("I think probably the client, but it depends."), Escalated)


def test_an_empty_reply_escalates():
    assert isinstance(parse_outcome(""), Escalated)


def test_a_marked_answer_with_nothing_after_it_escalates():
    """An empty answer sent into the session tells the agent nothing and it
    would ask again, forever."""
    assert isinstance(parse_outcome(f"{ANSWER_MARKER}   "), Escalated)


def test_the_first_consultation_pins_a_new_session_id(tmp_path):
    """Pinned rather than discovered afterwards: discovering it would mean
    reading Claude Code's internals (ADR 0002)."""
    argv = command_for(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=False)
    )

    assert "--session-id" in argv
    assert "--resume" not in argv
    assert argv[argv.index("--session-id") + 1] == "an-id"


def test_a_later_consultation_resumes_that_session_rather_than_starting_another(tmp_path):
    """One Answerer per Run: a fresh session would re-derive the architecture
    and disagree with what it already told the agent."""
    argv = command_for(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=True)
    )

    assert "--session-id" not in argv
    assert argv[argv.index("--resume") + 1] == "an-id"


def test_the_consultation_runs_headless_and_carries_the_prompt(tmp_path):
    argv = command_for(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=False)
    )

    assert "-p" in argv
    assert argv[-1] == "ask"


def test_an_answerer_that_cannot_be_run_escalates_rather_than_raising(tmp_path, monkeypatch):
    """A consultation that could not be run is precisely 'nobody here can
    settle this', which is what an Escalation already means — and it keeps the
    Run alive, where raising would kill the tick loop mid-Run."""
    monkeypatch.setattr(adapter, "CLAUDE", str(tmp_path / "no-such-claude"))

    outcome = adapter.HeadlessAnswerer().consult(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=False)
    )

    assert isinstance(outcome, Escalated)


def test_an_answerer_that_fails_escalates_with_what_it_said(tmp_path, monkeypatch):
    """The operator is woken by this reason, so it has to carry the failure."""
    monkeypatch.setattr(adapter, "CLAUDE", "sh")
    monkeypatch.setattr(
        adapter, "command_for", lambda spec: ["sh", "-c", "echo it-broke >&2; exit 1"]
    )

    outcome = adapter.HeadlessAnswerer().consult(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=False)
    )

    assert isinstance(outcome, Escalated)
    assert "it-broke" in outcome.reason
