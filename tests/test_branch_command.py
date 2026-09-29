"""The branch declaration as the agent meets it: exit status, resulting record,
error text.

Run as a real subprocess against a temporary Naiad directory, like the announce
and wait commands. The failures here would otherwise be silent — a declaration
that went nowhere leaves the Run branchless, and the next Entry's Predecessor
stands on what was declared.
"""

import json
import subprocess

import pytest

from naiad.domain.entry import Entry
from naiad.runtime.log import RunLog
from naiad.runtime.queue import Queue
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


def declare(run, *arguments, run_id="a-run"):
    return subprocess.run(
        [NAIAD, "branch", *arguments],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id=run_id),
        cwd=str(run.target_repo),
    )


def recorded_branch(run):
    return json.loads((run.root / "run.json").read_text())["working_branch"]


def naiad_home(run):
    return run.root.parents[1]


def hold(run, *, entry_id, target_repo, working_branch, run_id=None):
    """Another Entry in the Queue this declaration is checked against."""
    entry = Entry(
        id=entry_id,
        workflow_path=run.workflow_path,
        task="other work",
        target_repo=target_repo,
        working_branch=working_branch,
        created_at="2026-07-19T11:00:00Z",
        run_id=run_id,
    )
    return Queue(naiad_home(run) / "queue").add(entry)


def test_declaring_on_a_branchless_run_records_the_name(run):
    finished = declare(run, "feat/dark-mode")

    assert finished.returncode == 0, finished.stderr
    assert recorded_branch(run) == "feat/dark-mode"


def test_the_agent_is_told_what_was_declared(run):
    finished = declare(run, "feat/dark-mode")

    assert "feat/dark-mode" in finished.stdout


def test_a_subsequent_enqueue_sees_the_claim(run):
    """The declared name resolves through the Run, so an operator's
    `--branch` cannot collide with a Derived branch invisibly."""
    hold(
        run,
        entry_id="the-entry-that-started-this-run",
        target_repo=run.target_repo,
        working_branch=None,
        run_id="a-run",
    )
    declare(run, "feat/dark-mode")

    enqueued = subprocess.run(
        [
            NAIAD,
            "queue",
            "add",
            str(run.workflow_path),
            "more work",
            "--branch",
            "feat/dark-mode",
        ],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id="a-run"),
        cwd=str(run.target_repo),
    )

    assert enqueued.returncode == 2
    assert "feat/dark-mode" in enqueued.stderr


def test_a_second_declaration_is_refused_and_changes_nothing(run):
    declare(run, "feat/dark-mode")

    finished = declare(run, "feat/second-thoughts")

    assert finished.returncode == 2
    assert "feat/dark-mode" in finished.stderr
    assert recorded_branch(run) == "feat/dark-mode"


def test_a_run_whose_branch_was_given_refuses_a_declaration(run, tmp_path):
    given = RunStore(naiad_home(run) / "runs").create(
        run_id="a-given-run",
        workflow_path=run.workflow_path,
        task="named work",
        target_repo=run.target_repo,
        created_at="2026-07-19T12:00:00Z",
        working_branch="feat/named-at-the-terminal",
    )

    finished = declare(given, "feat/derived-anyway", run_id="a-given-run")

    assert finished.returncode == 2
    assert "feat/named-at-the-terminal" in finished.stderr
    assert recorded_branch(given) == "feat/named-at-the-terminal"


def test_a_name_another_entry_holds_in_the_same_repository_is_refused(run):
    """The two-Entries-one-branch refusal, relocated to declaration time: the
    holder is named so the agent can derive another name and retry."""
    hold(
        run,
        entry_id="the-holder",
        target_repo=run.target_repo,
        working_branch="feat/dark-mode",
    )

    finished = declare(run, "feat/dark-mode")

    assert finished.returncode == 2
    assert "the-holder" in finished.stderr
    assert recorded_branch(run) is None


def test_the_same_name_in_another_repository_is_accepted(run, tmp_path):
    """A branch name from another repository is not a fact about this one."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    hold(
        run,
        entry_id="the-holder",
        target_repo=elsewhere,
        working_branch="feat/dark-mode",
    )

    finished = declare(run, "feat/dark-mode")

    assert finished.returncode == 0, finished.stderr
    assert recorded_branch(run) == "feat/dark-mode"


def test_the_declaration_appears_in_the_run_log(run):
    """So a human reading the log can answer where the branch name came from."""
    declare(run, "feat/dark-mode")

    entries = RunLog(run.root).entries()
    assert any(
        entry.kind == "declared" and "feat/dark-mode" in (entry.detail or "")
        for entry in entries
    )


def test_a_blank_name_is_rejected_without_recording_anything(run):
    finished = declare(run, "   ")

    assert finished.returncode == 2
    assert recorded_branch(run) is None


def test_declaring_outside_a_run_is_rejected_rather_than_silently_ignored(run):
    finished = declare(run, "feat/dark-mode", run_id="no-such-run")

    assert finished.returncode == 2
    assert finished.stderr.strip()
