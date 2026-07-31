"""The contract the agent actually meets: exit status, resulting file, error text.

Run as a real subprocess against a temporary Naiad directory, because these are
the failures that would otherwise be silent — the agent has no way to notice
that its Announcement went nowhere.
"""

import json
import shutil
import subprocess

import pytest

from naiad.runtime.announcements import STATE_FILENAME
from naiad.runtime.run import RunStore

NAIAD = shutil.which("naiad")

pytestmark = pytest.mark.skipif(
    NAIAD is None, reason="the naiad command is not installed; run `uv sync` or `pip install -e .`"
)

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


def announce(run, *arguments, run_id="a-run"):
    return subprocess.run(
        [NAIAD, "state", *arguments],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "NAIAD_HOME": str(run.root.parents[1]),
            "NAIAD_RUN_ID": run_id,
        },
        cwd=str(run.target_repo),
    )


def state_file(run):
    return json.loads((run.root / STATE_FILENAME).read_text())


def test_announcing_a_state_succeeds_and_records_it(run):
    finished = announce(run, "grill")

    assert finished.returncode == 0, finished.stderr
    assert state_file(run)["state"] == "grill"


def test_successive_announcements_allocate_a_strictly_increasing_sequence(run):
    announce(run, "grill")
    first = state_file(run)["seq"]
    announce(run, "implement")

    assert state_file(run)["seq"] > first


def test_the_same_state_announced_twice_is_two_distinct_announcements(run):
    announce(run, "implement")
    first = state_file(run)["seq"]
    announce(run, "implement")

    assert state_file(run)["seq"] == first + 1


def test_a_state_not_in_the_workflow_is_rejected_with_the_valid_names(run):
    finished = announce(run, "implememt")

    assert finished.returncode != 0
    assert "implememt" in finished.stderr
    for name in ("grill", "implement", "done"):
        assert name in finished.stderr


def test_a_rejected_state_does_not_alter_the_state_file(run):
    announce(run, "grill")
    before = state_file(run)

    announce(run, "implememt")

    assert state_file(run) == before


def test_a_rejected_first_state_writes_no_state_file(run):
    finished = announce(run, "implememt")

    assert finished.returncode != 0
    assert not (run.root / STATE_FILENAME).exists()


def test_announcing_outside_a_run_is_rejected_rather_than_silently_ignored(run):
    finished = announce(run, "grill", run_id="")

    assert finished.returncode != 0
    assert finished.stderr.strip() != ""
