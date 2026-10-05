"""What fits on the operator's screen: the width a line is cut to, and the clause
of an answer it keeps."""

from naiad.cli.terminal import first_clause, terminal_width


def test_a_terminal_reports_its_own_width(monkeypatch):
    monkeypatch.setenv("COLUMNS", "132")

    assert terminal_width() == 132


def test_a_piped_output_is_eighty_columns_wide(monkeypatch):
    """Under a test runner stdout is captured, which is what a pipe looks like."""
    monkeypatch.delenv("COLUMNS", raising=False)

    assert terminal_width() == 80


def test_the_first_clause_of_an_answer_stops_at_the_first_punctuation():
    assert first_clause("Yes: stop PID 37420, run the build") == "Yes"
    assert first_clause("the client, because it retries") == "the client"
    assert first_clause("Use the queue; skip the cache") == "Use the queue"
    assert first_clause("Do it. Then stop") == "Do it"
    assert first_clause("Yes — rebuild and restart") == "Yes"


def test_an_answer_of_one_clause_is_kept_whole():
    assert first_clause("the client") == "the client"
    assert first_clause("v1.2 is fine") == "v1.2 is fine"
