"""The contract the agent actually meets: exit status, resulting file, error text.

Run as a real subprocess against a temporary Naiad directory, because these are
the failures that would otherwise be silent — the agent has no way to notice
that its Announcement went nowhere.
"""

import json
import subprocess

import pytest

from naiad.domain.decide import Deliver
from naiad.runtime.announcements import STATE_FILENAME
from naiad.runtime.answers import AnswerLog
from naiad.runtime.log import RunLog
from naiad.runtime.records import Handled
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

# A Workflow whose head Prompt carries {branch}, behind a pre-head State that
# does not — the shape the undeclared-branch guard is measured against
# (ADR 0022): the guard fires only once a {branch}-carrying Prompt has gone out.
BRANCH_WORKFLOW = """
name = "feature"

[[states]]
name = "classify"
prompt = "classify {task}"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task} on {branch}"

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
        [NAIAD, "announce", *arguments],
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
    assert "naiad announce implement" in finished.stderr


def test_the_old_verb_is_no_longer_a_command_and_no_alias_is_kept(run):
    """`naiad state` is the authoring noun's, so the old spelling of an
    announcement must fail rather than quietly work."""
    finished = subprocess.run(
        [NAIAD, "state", "grill"],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id="a-run"),
        cwd=str(run.target_repo),
    )

    assert finished.returncode != 0
    assert "invalid choice: 'state'" in finished.stderr
    assert not (run.root / STATE_FILENAME).exists()


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


def ask(run, question, option, run_id="a-run"):
    return subprocess.run(
        [NAIAD, "ask", question, "--option", option],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id=run_id),
        cwd=str(run.target_repo),
    )


def test_announcing_over_an_unanswered_question_records_it_abandoned(run):
    """The agent abandoning its own Question is its judgment (ADR 0001), but a
    log holding only the Questions that were settled would show an unattended
    Run as tidier than it was — the Answer log's own founding argument."""
    ask(run, "Which module owns retries?", "the client")

    finished = announce(run, "done")

    assert finished.returncode == 0, finished.stderr
    entry = AnswerLog(run.root).entries()[0]
    assert entry.question == "Which module owns retries?"
    assert entry.options == ("the client",)
    assert entry.abandoned is True
    assert "done" in entry.answer


def test_announcing_over_an_answered_question_records_no_abandonment(run):
    ask(run, "Which module owns retries?", "the client")
    Handled(run.root).record(state_file(run)["seq"])

    announce(run, "done")

    assert AnswerLog(run.root).entries() == []


def test_announcing_outside_a_run_is_rejected_rather_than_silently_ignored(run):
    finished = announce(run, "grill", run_id="")

    assert finished.returncode != 0
    assert finished.stderr.strip() != ""


def branch_workflow_run(tmp_path, *, start_state=None, working_branch=None):
    repo = tmp_path / "repo"
    repo.mkdir()
    workflow = repo / "workflow.toml"
    workflow.write_text(BRANCH_WORKFLOW)
    return RunStore(tmp_path / "naiad" / "runs").create(
        run_id="a-run",
        workflow_path=workflow,
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
        start_state=start_state,
        working_branch=working_branch,
    )


def test_a_branchless_run_handed_a_branch_carrying_head_prompt_refuses_the_next_announcement(
    tmp_path,
):
    """Forgetting to declare is loud, not silent (ADR 0022). The Run began at
    the head State, so its {branch}-carrying Prompt went out at kickoff; the
    next Announcement with the branch still absent is refused, with the fix in
    the message."""
    run = branch_workflow_run(tmp_path, start_state="grill")

    finished = announce(run, "implement", "--subject", "01-a.md")

    assert finished.returncode != 0
    assert "naiad branch" in finished.stderr


def test_the_undeclared_branch_refusal_does_not_alter_the_state_file(tmp_path):
    run = branch_workflow_run(tmp_path, start_state="grill")

    announce(run, "implement", "--subject", "01-a.md")

    assert not (run.root / STATE_FILENAME).exists()


def test_announcing_before_any_branch_carrying_prompt_was_delivered_is_not_refused(tmp_path):
    """A pre-head State announces freely on a branchless Run: the Run began at
    classify, whose Prompt does not carry {branch}, and no other Prompt has
    been delivered yet."""
    run = branch_workflow_run(tmp_path)

    finished = announce(run, "grill")

    assert finished.returncode == 0, finished.stderr


def test_a_branch_carrying_prompt_delivered_mid_run_arms_the_guard(tmp_path):
    """Whether a {branch}-carrying Prompt went out is derivable from the
    Workflow file and the delivery history: a Run that began before the head
    State is guarded from the moment the head Prompt is delivered."""
    run = branch_workflow_run(tmp_path)
    RunLog(run.root).record(
        Deliver(state="grill", prompt="/grill-with-docs {task} on {branch}", next_states=("implement",))
    )

    finished = announce(run, "implement", "--subject", "01-a.md")

    assert finished.returncode != 0
    assert "naiad branch" in finished.stderr


def test_after_declaring_the_same_announcement_succeeds(tmp_path):
    run = branch_workflow_run(tmp_path, start_state="grill")
    declared = subprocess.run(
        [NAIAD, "branch", "feat/dark-mode"],
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id="a-run"),
        cwd=str(run.target_repo),
    )
    assert declared.returncode == 0, declared.stderr

    finished = announce(run, "implement", "--subject", "01-a.md")

    assert finished.returncode == 0, finished.stderr
    assert state_file(run)["state"] == "implement"


def test_a_run_whose_branch_was_given_is_never_touched_by_the_guard(tmp_path):
    run = branch_workflow_run(tmp_path, start_state="grill", working_branch="feat/named")

    finished = announce(run, "implement", "--subject", "01-a.md")

    assert finished.returncode == 0, finished.stderr
