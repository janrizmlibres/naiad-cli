"""The one Workflow that ships: the Matt Pocock feature chain.

Asserted as an operator and an agent meet it — the file on disk parses, its
Prompts read as delivered rather than as templates, and a Run starts from it.
How the Workflow behaves under a real agent is manual smoke, in
docs/smoke/matt-pocock.md; what is testable here is that the file is well-formed
and says what the Workflow requires.
"""

from pathlib import Path

import pytest

from naiad.cli.kickoff import start_run
from naiad.domain.prompt import render_prompt
from naiad.domain.transitions import next_state
from naiad.domain.workflow import load_workflow
from naiad.runtime.run import RunStore

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / "workflows" / "matt-pocock.toml"

STATES = ["grill", "review", "spec", "tickets", "implement", "pull-request", "review-fix", "done"]

# Every State that delivers something, and the skill its Prompt must invoke.
SKILLS = {
    "grill": "/grill-with-docs",
    "spec": "/to-spec",
    "tickets": "/to-tickets",
    "implement": "/implement",
    "pull-request": "/hcgps-pr",
    "review-fix": "/fix-review",
}

TASK = "add dark mode"


@pytest.fixture
def workflow():
    return load_workflow(WORKFLOW_PATH)


def delivered(workflow, state_name):
    """A State's Prompt as the agent actually reads it, with the successor the
    Workflow resolves interpolated — which is what Naiad sends (naiad.runtime.loop)."""
    successor = next_state(workflow, state_name)
    return render_prompt(
        workflow.state(state_name).prompt,
        task=TASK,
        next_state=successor.name if successor else None,
    )


def test_declares_every_state_in_order(workflow):
    assert [state.name for state in workflow.states] == STATES


def test_the_review_state_is_the_only_gate_state(workflow):
    gate_states = [
        state.name for state in workflow.states if state.is_gate_state and not state.terminal
    ]

    assert gate_states == ["review"]


def test_the_last_state_is_the_only_terminal_one(workflow):
    terminal = [state.name for state in workflow.states if state.terminal]

    assert terminal == ["done"]


@pytest.mark.parametrize(("state_name", "skill"), sorted(SKILLS.items()))
def test_each_prompt_opens_by_invoking_its_skill(workflow, state_name, skill):
    """The slash command opens the Prompt because Claude Code reads one only at
    the start of a message: prose in front of it would send the skill's name as
    chat rather than invoking it."""
    assert delivered(workflow, state_name).startswith(skill)


@pytest.mark.parametrize("state_name", sorted(SKILLS))
def test_each_prompt_names_the_state_to_announce_next(workflow, state_name):
    """The Workflow file owns the ordering, so a Prompt names its successor by
    interpolation rather than by hand — and the agent is told a name it can
    announce rather than an unsubstituted placeholder."""
    successor = next_state(workflow, state_name)

    assert f"announce {successor.name}" in delivered(workflow, state_name)


def test_only_the_kickoff_state_is_told_the_task(workflow):
    """Every later State reads the work from the Artifacts the earlier ones
    wrote, which is what makes Clearing safe."""
    told = [name for name in SKILLS if TASK in delivered(workflow, name)]

    assert told == ["grill"]


def test_the_implement_loop_clears_and_the_design_phases_do_not(workflow):
    """Each ticket starts fresh; the spec and the tickets are synthesised from
    the grilling conversation and would lose it."""
    clearing = [state.name for state in workflow.states if state.clear]

    assert clearing == ["implement", "pull-request", "review-fix"]


def test_the_implement_loop_tells_the_agent_to_re_announce_itself(workflow):
    """One State, announced once per ticket. The interpolated successor is the
    State after the loop, so the loop's own name has to be in the Prompt or the
    agent has nothing to announce for the second ticket."""
    assert "announce implement" in delivered(workflow, "implement")


def test_no_prompt_after_a_clearing_state_refers_back_to_the_cleared_context(workflow):
    """The symptom deferred issue 02 warns about, caught where it is cheap: a
    Prompt delivered into a wiped context that says 'you just' is naming
    something the agent can no longer remember."""
    clearing = [state.name for state in workflow.states if state.clear]

    for state_name in clearing:
        assert "you just" not in delivered(workflow, state_name)


def test_a_run_can_be_started_from_it(tmp_path, sessions):
    repo = tmp_path / "repo"
    repo.mkdir()

    start_run(
        workflow_path=WORKFLOW_PATH,
        task=TASK,
        target_repo=repo,
        store=RunStore(tmp_path / "runs"),
        sessions=sessions,
        run_id="20260720-120000-matt-pocock",
        claude_session_id="11111111-1111-1111-1111-111111111111",
        created_at="2026-07-20T12:00:00Z",
    )

    (spawn,) = sessions.spawned
    assert spawn.initial_prompt.startswith(f"/grill-with-docs {TASK}")
    assert "announce review" in spawn.initial_prompt


def test_an_unattended_run_resolves_past_the_review_gate_state(workflow):
    """The same file run with --skip-gates: the grilling State's Prompt names
    the spec rather than the Gate State nobody is there to release."""
    assert next_state(workflow, "grill", skip_gates=True).name == "spec"
    assert next_state(workflow, "grill").name == "review"
