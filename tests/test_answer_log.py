"""The Answer log: what the operator reads at a Gate to judge an unattended Run.

Written by Naiad rather than by the agent, because Naiad holds both halves —
the agent cannot fail to log an answer it never saw.
"""

from naiad.domain.question import Question
from naiad.runtime.answers import AnswerLog

RETRIES = Question(text="Which module owns retries?", options=("the client", "the caller"))
VENDOR = Question(text="Which SMS vendor?", options=("Twilio", "Vonage"))


def test_an_empty_log_reads_as_nothing_rather_than_failing(tmp_path):
    """A Run that has raised no Question has no log file, and reading one is
    what a Run summary does."""
    assert AnswerLog(tmp_path).entries() == []


def test_a_recorded_answer_shows_the_question_its_options_and_the_answer(tmp_path):
    log = AnswerLog(tmp_path)

    log.record(question=RETRIES, answer="the client")

    entry = log.entries()[0]
    assert entry.question == "Which module owns retries?"
    assert entry.options == ("the client", "the caller")
    assert entry.answer == "the client"
    assert entry.escalated is False


def test_entries_read_back_in_the_order_they_occurred(tmp_path):
    """The operator reads the log as one narrative of the Run's judgment."""
    log = AnswerLog(tmp_path)

    log.record(question=RETRIES, answer="the client")
    log.record(question=VENDOR, answer="not in this repository", escalated=True)

    assert [entry.question for entry in log.entries()] == [RETRIES.text, VENDOR.text]


def test_an_escalation_is_recorded_beside_the_questions_that_were_answered(tmp_path):
    """An Escalation is what became of that Question. Logging only the answered
    ones would show an unattended Run as tidier than it was."""
    log = AnswerLog(tmp_path)

    log.record(question=VENDOR, answer="picking a vendor is not in this repository", escalated=True)

    entry = log.entries()[0]
    assert entry.escalated is True
    assert entry.options == ("Twilio", "Vonage")


def test_a_second_answer_does_not_replace_the_first(tmp_path):
    """The log is the audit trail; an overwrite would lose the Run's history."""
    log = AnswerLog(tmp_path)

    log.record(question=RETRIES, answer="the client")
    log.record(question=RETRIES, answer="the caller")

    assert [entry.answer for entry in log.entries()] == ["the client", "the caller"]
