"""The contract the agent actually meets: exit status, resulting file, error text.

Run as a real subprocess against a temporary Naiad directory, because these are
the failures that would otherwise be silent — the agent has no way to notice
that its Announcement went nowhere.
"""

import json
import subprocess

import pytest

from naiad.runtime.announcements import STATE_FILENAME
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
prompt = "/implement the ticket at {subject}"
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
        env=naiad_environment(run, run_id=run_id),
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
    announce(run, "implement", "--subject", "01-a.md")

    assert state_file(run)["seq"] > first


def test_the_same_state_announced_twice_is_two_distinct_announcements(run):
    announce(run, "implement", "--subject", "01-a.md")
    first = state_file(run)["seq"]
    announce(run, "implement", "--subject", "02-b.md")

    assert state_file(run)["seq"] == first + 1


def test_a_subject_is_recorded_against_the_announcement(run):
    finished = announce(run, "implement", "--subject", ".scratch/f/issues/04-x.md")

    assert finished.returncode == 0, finished.stderr
    assert state_file(run)["subject"] == ".scratch/f/issues/04-x.md"


def test_a_prompt_needing_a_subject_announced_without_one_is_rejected(run):
    """The Prompt cannot be rendered, and the mistake is the agent's to
    correct — so it is caught here, inside the agent's own turn, rather than at
    delivery where only a human could answer it (ADR 0009)."""
    finished = announce(run, "implement")

    assert finished.returncode != 0
    assert "subject" in finished.stderr


def test_an_empty_subject_is_rejected_like_a_missing_one(run):
    """A blank Subject renders exactly as an absent one and reaches the session
    just as unrecoverably, so the guard is on what the Prompt would say rather
    than on whether the flag was typed. An agent building the invocation from a
    scanned path that came up empty produces this rather than omitting it."""
    finished = announce(run, "implement", "--subject", "")

    assert finished.returncode != 0
    assert "subject" in finished.stderr


def test_a_rejected_empty_subject_does_not_alter_the_state_file(run):
    announce(run, "grill")
    before = state_file(run)

    announce(run, "implement", "--subject", "")

    assert state_file(run) == before


def test_a_rejected_subjectless_announcement_names_the_correct_invocation(run):
    """The same courtesy an unknown State name gets: the agent is told what to
    type instead, so it can fix itself rather than stall."""
    finished = announce(run, "implement")

    assert "--subject" in finished.stderr
    assert "implement" in finished.stderr


def test_a_rejected_subjectless_announcement_does_not_alter_the_state_file(run):
    announce(run, "grill")
    before = state_file(run)

    announce(run, "implement")

    assert state_file(run) == before


def test_a_subject_given_to_a_state_with_no_slot_for_one_is_accepted(run):
    """A Subject belongs to the Announcement, not the Prompt. The Gate State
    this loop hands work to has no Prompt at all, and its Subject — read by the
    human out of the Run log — is the most useful one in the Run (ADR 0009)."""
    finished = announce(run, "grill", "--subject", "05-y.md")

    assert finished.returncode == 0, finished.stderr
    assert state_file(run)["subject"] == "05-y.md"


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
