"""The command the SessionStart hook runs, as a real subprocess.

This is the contract the agent meets in every fresh context, and its failures
are the silent ones: a Protocol that does not print leaves the agent unable to
participate, after which the Run dies quietly.
"""

import json
import subprocess

import pytest

from naiad.runtime.announcements import Announcements
from naiad.runtime.run import RunStore
from naiad_command import NAIAD, naiad_environment, requires_installed_naiad

pytestmark = requires_installed_naiad

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "review"

[[states]]
name = "spec"
prompt = "/to-spec"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "naiad" / "runs")


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    (path / "workflow.toml").write_text(WORKFLOW)
    return path


def make_run(store, repo, **options):
    return store.create(
        run_id="a-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
        **options,
    )


def protocol(run, *, run_id="a-run"):
    return subprocess.run(
        [NAIAD, "protocol"],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id=run_id),
        cwd=str(run.target_repo),
    )


def injected(finished):
    """What the hook asks Claude Code to add to the fresh context."""
    document = json.loads(finished.stdout)
    assert document["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    return document["hookSpecificOutput"]["additionalContext"]


def test_prints_the_protocol_for_injection_into_a_fresh_context(store, repo):
    finished = protocol(make_run(store, repo))

    assert finished.returncode == 0, finished.stderr
    assert "naiad state" in injected(finished)
    assert "naiad ask" in injected(finished)


def test_before_anything_is_announced_it_names_the_state_after_the_starting_one(store, repo):
    finished = protocol(make_run(store, repo))

    assert "announce: review" in injected(finished)


def test_after_an_announcement_it_names_the_state_after_the_announced_one(store, repo):
    run = make_run(store, repo)
    Announcements(run.root).announce("review")

    assert "announce: spec" in injected(protocol(run))


def test_a_run_with_gates_skipped_is_told_the_next_state_that_has_a_prompt(store, repo):
    finished = protocol(make_run(store, repo, skip_gates=True))

    assert "announce: spec" in injected(finished)


def test_a_run_started_at_a_named_state_is_told_what_follows_that_state(store, repo):
    finished = protocol(make_run(store, repo, start_state="review"))

    assert "announce: spec" in injected(finished)


def test_no_run_attached_prints_nothing_and_succeeds(store, repo):
    """Hooks are installed independently of any Run, so a session that is not
    being driven must be left exactly as it was — not failed, not written to."""
    finished = protocol(make_run(store, repo), run_id="")

    assert finished.returncode == 0
    assert finished.stdout == ""


def test_a_workflow_carrying_no_protocol_text_still_yields_the_full_protocol(store, repo):
    """The Protocol is Naiad's responsibility and never the Workflow author's.
    The fixture Workflow's Prompts are bare — were an author obliged to paste
    the contract into each one, a single omission would produce a State that
    silently never advances."""
    assert "naiad" not in WORKFLOW

    finished = protocol(make_run(store, repo))

    assert "naiad state" in injected(finished)
    assert "naiad ask" in injected(finished)
    assert "announce: review" in injected(finished)


def test_a_workflow_edited_out_from_under_the_run_does_not_break_the_session(store, repo):
    """A hook that raises interrupts the agent for a Run it cannot even
    describe; printing the contract without an expectation is the lesser harm."""
    run = make_run(store, repo, start_state="review")
    (repo / "workflow.toml").write_text(
        'name = "feature"\n[[states]]\nname = "other"\nterminal = true\n'
    )

    finished = protocol(run)

    assert finished.returncode == 0
    assert "naiad state" in injected(finished)
