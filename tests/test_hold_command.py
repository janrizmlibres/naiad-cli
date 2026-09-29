"""The hold command as the agent meets it: exit status, resulting record, error text.

Run as a real subprocess against a temporary Naiad directory, like the wait
command. The failure here would otherwise be the worst kind — a human who
asked for a pause, an agent that relayed it, and a Run that got nudged into
the very interruption the human ordered against.
"""

import json
import subprocess

import pytest

from naiad.runtime.records import HOLDS_FILENAME
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
        created_at="2026-07-31T12:00:00Z",
    )


def hold(run, *arguments, run_id="a-run"):
    return subprocess.run(
        [NAIAD, "hold", *arguments],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id=run_id),
        cwd=str(run.target_repo),
    )


def holds_file(run):
    return json.loads((run.root / HOLDS_FILENAME).read_text())


def test_declaring_a_hold_succeeds_and_records_the_humans_instruction(run):
    finished = hold(run, "user typed 'pause' — holding until they resume")

    assert finished.returncode == 0, finished.stderr
    recorded = holds_file(run)
    assert recorded["held"] is True
    assert recorded["reason"] == "user typed 'pause' — holding until they resume"


def test_the_agent_is_told_the_run_is_parked_until_the_human_returns(run):
    finished = hold(run, "user typed 'pause'")

    assert "held" in finished.stdout
    assert "end your turn" in finished.stdout


def test_a_hold_needs_to_say_why(run):
    finished = hold(run, "   ")

    assert finished.returncode == 2
    assert finished.stderr.strip()
    assert not (run.root / HOLDS_FILENAME).exists()


def test_holding_outside_a_run_is_rejected_rather_than_silently_ignored(run):
    finished = hold(run, "user typed 'pause'", run_id="no-such-run")

    assert finished.returncode == 2
    assert finished.stderr.strip()
