"""The wait command as the agent meets it: exit status, resulting record, error text.

Run as a real subprocess against a temporary Naiad directory, like the
announce and ask commands. The failures here would otherwise be silent — an
agent whose declared Wait went nowhere is read as silent and Nudged into the
very interruption it declared against (ADR 0021).
"""

import json
import subprocess

import pytest

from naiad.domain.decide import WAIT_BUDGET_SECONDS
from naiad.runtime.records import WAITS_FILENAME
from naiad.runtime.run import RunStore
from naiad_command import NAIAD, naiad_environment, requires_installed_naiad

pytestmark = requires_installed_naiad

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

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


def wait(run, *arguments, run_id="a-run"):
    return subprocess.run(
        [NAIAD, "wait", *arguments],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id=run_id),
        cwd=str(run.target_repo),
    )


def waits_file(run):
    return json.loads((run.root / WAITS_FILENAME).read_text())


def test_declaring_a_wait_succeeds_and_records_what_and_until_when(run):
    finished = wait(run, "2 review agents", "--seconds", "300")

    assert finished.returncode == 0, finished.stderr
    recorded = waits_file(run)
    assert recorded["reason"] == "2 review agents"
    assert recorded["until"] - recorded["at"] == pytest.approx(300.0)


def test_the_agent_is_told_what_it_was_granted(run):
    finished = wait(run, "2 review agents", "--seconds", "300")

    assert "2 review agents" in finished.stdout
    assert "300" in finished.stdout


def test_a_wait_without_a_duration_gets_the_default(run):
    finished = wait(run, "a check")

    assert finished.returncode == 0, finished.stderr
    recorded = waits_file(run)
    assert recorded["until"] > recorded["at"]


def test_a_wait_needs_to_say_what_it_is_waiting_on(run):
    finished = wait(run, "   ")

    assert finished.returncode == 2
    assert "waiting on" in finished.stderr
    assert not (run.root / WAITS_FILENAME).exists()


def test_a_non_positive_duration_is_rejected(run):
    finished = wait(run, "a check", "--seconds", "0")

    assert finished.returncode == 2
    assert not (run.root / WAITS_FILENAME).exists()


def test_a_wait_past_the_spent_budget_is_refused_toward_announce_or_ask(run):
    """The refusal must leave the agent a move: announce, or ask (ADR 0021)."""
    (run.root / WAITS_FILENAME).write_text(
        json.dumps(
            {
                "seq": None,
                "count": 3,
                "reason": "an earlier wait",
                "at": 0.0,
                "until": 1.0,
                "granted": 1.0,
                "spent": WAIT_BUDGET_SECONDS,
            }
        )
    )

    finished = wait(run, "yet another check")

    assert finished.returncode == 2
    assert "naiad state" in finished.stderr
    assert "naiad ask" in finished.stderr
    assert waits_file(run)["reason"] == "an earlier wait"


def test_waiting_outside_a_run_is_rejected_rather_than_silently_ignored(run):
    finished = wait(run, "a check", run_id="no-such-run")

    assert finished.returncode == 2
    assert finished.stderr.strip()
