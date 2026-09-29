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


def test_the_consultation_asks_for_the_decision_rather_than_a_plan():
    """The Answerer settles questions for an agent that is working in the same
    repository and can pick its own file paths, follow its own precedents and
    sequence its own work. Told only to make the answer actionable, it wrote
    implementation plans and restated the agent's own survey back to it."""
    consultation = render_consultation(RETRIES, task="add dark mode").lower()

    assert "own judgement" in consultation
    assert "implementation plan" in consultation


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


def test_the_consultation_asks_for_one_marker_and_forbids_both():
    """Printed as a pair to fill in, the markers get filled in as a pair — a
    real Answerer settled a question and then added 'ESCALATE: Nothing', which
    read by position discarded the answer."""
    consultation = render_consultation(RETRIES, task="add dark mode").lower()

    assert "never both" in consultation


def _marked_lines(consultation: str, marker: str) -> list[str]:
    return [line.strip() for line in consultation.splitlines() if line.strip().startswith(marker)]


def test_the_brief_and_the_parser_agree_on_the_reply_format():
    """The brief and parse_outcome are two halves of one protocol, written in
    two places with nothing spanning them: the brief printed both markers as a
    block to fill in, while the parser assumed a reply carried one and read the
    last. A reply that filled the block in therefore lost its answer.

    So the brief's own example lines are the fixture here — an edit to either
    half is checked against the other, rather than each staying self-consistent
    while the pair stops agreeing."""
    consultation = render_consultation(RETRIES, task="add dark mode")
    answers = _marked_lines(consultation, ANSWER_MARKER)
    escalations = _marked_lines(consultation, ESCALATE_MARKER)

    assert len(answers) == 1, "the brief must show each marker exactly once"
    assert len(escalations) == 1

    # Each line alone, replied as the brief shows it.
    assert isinstance(parse_outcome(f"my reasoning\n{answers[0]}"), Answered)
    assert isinstance(parse_outcome(f"my reasoning\n{escalations[0]}"), Escalated)

    # And both together, which is what an Answerer reading it as a template
    # actually sent. It settled the question, so it must read as settled.
    assert isinstance(parse_outcome(f"my reasoning\n{answers[0]}\n{escalations[0]}"), Answered)


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


def test_an_answer_wins_over_an_escalation_in_the_same_reply():
    """The brief prints the two markers as a template, so a reply that fills it
    in carries both lines with the escalation last. Read by position alone that
    discards a settled answer and wakes the operator to be told nothing needs
    them — which is what happened to a real consultation.

    An Escalation means 'I cannot settle this'. A reply that also states an
    answer has settled it, and the answer is the recoverable half: a needless
    Escalation stalls the Run in silence, while an answer the agent disagrees
    with it can argue back against."""
    reply = (
        "Reasoning about the ledger.\n"
        f"{ANSWER_MARKER} Option C, TTL 15 minutes\n"
        f"{ESCALATE_MARKER} Nothing. Both halves are settled in-repo."
    )
    outcome = parse_outcome(reply)

    assert isinstance(outcome, Answered)
    assert outcome.text.startswith("Option C, TTL 15 minutes")


def test_an_escalation_beside_an_answer_is_carried_into_the_answer():
    """Not every escalation beside an answer is redundant. A real one read
    'Option A ... run a pre-flight count' and escalated *conditionally* — stop
    and wake a human only if that count comes back non-zero, because choosing
    between conflicting PHI rows is a compliance call. The answer carried the
    instruction and the escalation carried the consequence, so dropping the
    escalation would have sent the agent to run a check with no reason to stop.

    Carried into the answer rather than escalated: the Run keeps moving, and a
    condition the agent can only evaluate by working is one it should be told
    about rather than one the operator should be woken for."""
    reply = (
        f"{ANSWER_MARKER} Option A, and run a pre-flight count\n"
        f"{ESCALATE_MARKER} Only if that count is non-zero: it is a HIPAA call."
    )
    outcome = parse_outcome(reply)

    assert isinstance(outcome, Answered)
    assert "Option A, and run a pre-flight count" in outcome.text
    assert "Only if that count is non-zero: it is a HIPAA call." in outcome.text


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
    reading Claude Code's internals."""
    argv = command_for(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=False)
    )

    assert "--session-id" in argv
    assert "--resume" not in argv
    assert argv[argv.index("--session-id") + 1] == "an-id"


def test_the_answerers_model_and_effort_ride_as_flags(tmp_path):
    """Declared in the Workflow's [answerer] table and passed at invocation —
    a headless session starts clean, so flags are the whole delivery."""
    argv = command_for(
        ConsultationSpec(
            cwd=tmp_path,
            claude_session_id="an-id",
            text="ask",
            resume=False,
            model="haiku",
            effort="low",
        )
    )

    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--effort") + 1] == "low"
    assert argv[-1] == "ask"


def test_the_answerers_fallback_rides_as_the_platforms_own_flag(tmp_path):
    """An unavailable model otherwise comes back as error text with exit 0 —
    a wrong answer, not a loud failure. The platform's --fallback-model does
    the detection and the degrading, so Naiad builds neither."""
    argv = command_for(
        ConsultationSpec(
            cwd=tmp_path,
            claude_session_id="an-id",
            text="ask",
            resume=False,
            model="fable",
            fallback="opus,sonnet",
        )
    )

    assert argv[argv.index("--fallback-model") + 1] == "opus,sonnet"
    assert argv[-1] == "ask"


def test_an_answerer_with_nothing_declared_passes_no_flags(tmp_path):
    argv = command_for(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=False)
    )

    assert "--model" not in argv
    assert "--effort" not in argv
    assert "--fallback-model" not in argv


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


def test_an_answerer_without_claude_on_path_escalates_with_a_sentence(tmp_path, monkeypatch):
    """Not the exception's text: whoever is woken by this reason is told what
    is missing, and it is the same thing the doctor names."""
    monkeypatch.setenv("PATH", str(tmp_path))

    outcome = adapter.HeadlessAnswerer().consult(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=False)
    )

    assert outcome == Escalated(reason="the Answerer could not be run: `claude` is not on PATH")


def test_an_answerer_that_cannot_launch_escalates_with_the_launch_failure(tmp_path, monkeypatch):
    """`claude` is there but the system refused to start it: not a PATH problem,
    and saying so would send the operator looking in the wrong place."""
    (tmp_path / "claude").write_text("#!/bin/sh\n")
    (tmp_path / "claude").chmod(0o644)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(adapter, "CLAUDE", str(tmp_path / "claude"))

    outcome = adapter.HeadlessAnswerer().consult(
        ConsultationSpec(cwd=tmp_path, claude_session_id="an-id", text="ask", resume=False)
    )

    assert isinstance(outcome, Escalated)
    assert outcome.reason.startswith("the Answerer could not be run: ")
    assert "Errno" not in outcome.reason
    assert "PATH" not in outcome.reason
