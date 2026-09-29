"""The Question command as the agent meets it: exit status, resulting file, error text.

Run as a real subprocess against a temporary Naiad directory. These are the
failures that would otherwise be silent — an agent whose Question went nowhere
waits for an answer that is never coming, and the Run dies having done nothing.
"""

import json
import subprocess

import pytest

from naiad.domain.answerer import Escalated
from naiad.runtime.announcements import Announcements, STATE_FILENAME
from naiad.runtime.records import Consultations, Handled
from naiad.runtime.run import RunStore
from naiad_command import NAIAD, naiad_environment, requires_installed_naiad

pytestmark = requires_installed_naiad

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "implement"
prompt = "/implement"
clear = true

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def run(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    workflow = repo / "workflow.toml"
    workflow.write_text(WORKFLOW)
    return RunStore(tmp_path / "naiad" / "runs").create(
        run_id="a-run",
        workflow_path=workflow,
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
    )


def naiad(run, *arguments, run_id="a-run"):
    return subprocess.run(
        [NAIAD, *arguments],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id=run_id),
        cwd=str(run.target_repo),
    )


def ask(run, question, *options, run_id="a-run"):
    arguments = ["ask", question]
    for option in options:
        arguments += ["--option", option]
    return naiad(run, *arguments, run_id=run_id)


def state_file(run):
    return json.loads((run.root / STATE_FILENAME).read_text())


def test_asking_a_question_succeeds_and_records_it_with_every_option(run):
    finished = ask(run, "Which module owns retries?", "the client", "the caller")

    assert finished.returncode == 0, finished.stderr
    recorded = state_file(run)
    assert recorded["question"]["text"] == "Which module owns retries?"
    assert recorded["question"]["options"] == ["the client", "the caller"]


def test_a_question_with_no_options_is_rejected_and_told_why(run):
    """A Question Naiad cannot see does not exist (ADR 0002), and one without
    its options leaves whoever answers guessing at what was on offer.

    The reason is asserted, not just the word 'option': argparse's own
    `required` would satisfy a laxer check while telling the agent nothing
    about why every option is wanted, and the agent has to fix the call itself.
    """
    finished = ask(run, "Which module owns retries?")

    assert finished.returncode != 0
    assert "--option" in finished.stderr
    assert "weighing" in finished.stderr
    assert "same alternatives" in finished.stderr


def test_a_question_with_no_text_is_rejected(run):
    """An empty Question reaches the Answerer as an empty Question, and it has
    nothing to answer."""
    finished = ask(run, "   ", "the client")

    assert finished.returncode != 0
    assert finished.stderr.strip() != ""


def test_a_rejected_question_writes_no_state_file(run):
    ask(run, "Which module owns retries?")

    assert not (run.root / STATE_FILENAME).exists()


def test_a_question_takes_its_number_from_the_same_sequence_as_states(run):
    """A Question and a State are ordered against each other, so the Answer log
    reads in the order things actually happened."""
    naiad(run, "announce", "implement")
    announced = state_file(run)["seq"]

    ask(run, "Which module owns retries?", "the client")

    assert state_file(run)["seq"] == announced + 1


def test_a_question_names_the_state_the_agent_is_standing_in(run):
    """It is where the agent carries on once the answer arrives."""
    naiad(run, "announce", "implement")

    ask(run, "Which module owns retries?", "the client")

    assert state_file(run)["state"] == "implement"


def test_a_question_asked_before_any_announcement_names_the_state_the_run_began_at(run):
    """The agent was handed that State's Prompt at kickoff without announcing
    it, so it is genuinely where it stands."""
    ask(run, "Which module owns retries?", "the client")

    assert state_file(run)["state"] == "grill"


def test_an_announcement_after_a_question_leaves_no_question_behind(run):
    """Naiad acts once per Announcement. A Question left clinging to the next
    State would be consulted a second time, after it was already answered."""
    ask(run, "Which module owns retries?", "the client")

    naiad(run, "announce", "done")

    assert state_file(run).get("question") is None


def test_asking_outside_a_run_is_rejected_rather_than_silently_ignored(run):
    finished = ask(run, "Which module owns retries?", "the client", run_id="")

    assert finished.returncode != 0
    assert finished.stderr.strip() != ""


def test_a_second_question_while_one_is_unanswered_is_refused(run):
    """Only the latest Announcement is kept, so a second Question would replace
    the first unanswered — the agent told 'the answer will arrive' four times
    would wait on three answers that can never come. Refused with the protocol
    in the refusal: hold the rest, re-ask as each answer arrives."""
    ask(run, "Which module owns retries?", "the client", "the caller")

    refused = ask(run, "Which store owns sessions?", "the run", "the queue")

    assert refused.returncode != 0
    assert "still being answered" in refused.stderr
    assert "one question at a time" in refused.stderr
    assert "ask it again" in refused.stderr


def test_a_refused_question_does_not_alter_the_state_file(run):
    ask(run, "Which module owns retries?", "the client")
    before = state_file(run)

    ask(run, "Which store owns sessions?", "the run")

    assert state_file(run) == before


def test_a_question_may_follow_one_that_was_answered(run):
    """Answered means Naiad acted on it: the Respond that sent the answer
    recorded the Question's seq as handled."""
    ask(run, "Which module owns retries?", "the client")
    Handled(run.root).record(state_file(run)["seq"])

    second = ask(run, "Which store owns sessions?", "the run")

    assert second.returncode == 0, second.stderr
    assert state_file(run)["question"]["text"] == "Which store owns sessions?"


def test_a_question_may_follow_one_that_was_escalated(run):
    """An Escalation is what became of the Question — the human was called and
    the agent may have been redirected — so it blocks nothing further."""
    ask(run, "Which cloud account pays for this?", "mine", "the client's")
    Consultations(run.root).record(
        Announcements(run.root).latest(), Escalated(reason="not the repo's to settle")
    )

    second = ask(run, "Which store owns sessions?", "the run")

    assert second.returncode == 0, second.stderr
    assert state_file(run)["question"]["text"] == "Which store owns sessions?"
