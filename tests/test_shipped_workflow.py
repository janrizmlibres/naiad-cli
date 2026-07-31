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
from naiad.domain.transitions import next_states
from naiad.domain.workflow import load_workflow
from naiad.runtime.run import RunStore

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / "workflows" / "matt-pocock.toml"

# Declared order, with the short branch first: the bug branch, then the feature
# chain, then the tail they share. No Run walks this order end to end — it is
# the order the file reads in, and the order an implicit successor comes from.
STATES = [
    "diagnose",
    "no-repro",
    "grill",
    "review",
    "spec",
    "tickets",
    "implement",
    "pull-request",
    "review-fix",
    "done",
]

# Every State that delivers something, and the skill its Prompt must invoke.
SKILLS = {
    "diagnose": "/diagnosing-bugs",
    "grill": "/grill-with-docs",
    "spec": "/to-spec",
    "tickets": "/to-tickets",
    "implement": "/implement",
    "pull-request": "/hcgps-pr",
    "review-fix": "/fix-review",
}

# The States that declare candidates rather than inheriting the next State in
# the declared order, and what each may announce. Every other successor in the
# Workflow stays implicit.
CANDIDATES = {
    "diagnose": ("no-repro", "pull-request"),
    "no-repro": ("pull-request",),
}

# The feature chain as it stands today, asserted rather than assumed: adding a
# branch must not move a single one of these edges. `done` ends the Run and so
# has nothing after it.
FEATURE_CHAIN = {
    "grill": ("review",),
    "review": ("spec",),
    "spec": ("tickets",),
    "tickets": ("implement",),
    "implement": ("pull-request",),
    "pull-request": ("review-fix",),
    "review-fix": ("done",),
    "done": (),
}

# The two States a Run may be started at directly, each the head of a branch.
BRANCH_HEADS = ["diagnose", "grill"]

TASK = "add dark mode"


@pytest.fixture
def workflow():
    return load_workflow(WORKFLOW_PATH)


def delivered(workflow, state_name):
    """A State's Prompt as the agent actually reads it, with the successor the
    Workflow resolves interpolated — which is what Naiad sends (naiad.runtime.loop)."""
    return render_prompt(
        workflow.state(state_name).prompt,
        task=TASK,
        next_states=next_states(workflow, state_name),
    )


def test_declares_every_state_in_order(workflow):
    assert [state.name for state in workflow.states] == STATES


def test_the_workflow_has_exactly_two_gate_states(workflow):
    """One per branch, and they are different kinds of stop: `review` is a
    routine checkpoint in the declared order, `no-repro` is a destination the
    agent chose. Which is which is asserted below, under gate-skipping."""
    gate_states = [
        state.name for state in workflow.states if state.is_gate_state and not state.terminal
    ]

    assert gate_states == ["no-repro", "review"]


def test_the_no_reproduction_state_delivers_nothing(workflow):
    """No Prompt, so Naiad sends nothing and the operator types into the
    session (ADR 0008)."""
    assert workflow.state("no-repro").prompt is None


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
    """The Workflow file owns the ordering, so a Prompt names its successors by
    interpolation rather than by hand — and the agent is told names it can
    announce rather than an unsubstituted placeholder.

    Every successor, at a fork too: a Prompt naming one exit of two would decide
    the branch in the place that is least visible, and the whole point of the
    fork is that the choice is the agent's."""
    prompt = delivered(workflow, state_name)

    for successor in next_states(workflow, state_name):
        assert f"announce {successor}" in prompt


@pytest.mark.parametrize(("state_name", "candidates"), sorted(CANDIDATES.items()))
def test_each_state_that_declares_candidates_declares_the_right_ones(
    workflow, state_name, candidates
):
    """Only one of these branches: `no-repro` declares a single candidate, and
    declares it because its implicit successor would be the feature chain it
    must not fall into. The rejoin is declared from the short branch, so it sits
    a line from its own head rather than reaching across the file."""
    assert workflow.state(state_name).next_candidates == candidates


def test_nothing_outside_the_bug_branch_declares_candidates(workflow):
    """Every other successor stays implicit, supplied by the declared order —
    which is what leaves the existing feature chain untouched."""
    declared = {state.name for state in workflow.states if state.next_candidates}

    assert declared == set(CANDIDATES)


@pytest.mark.parametrize(("state_name", "successors"), sorted(FEATURE_CHAIN.items()))
def test_the_feature_chain_keeps_every_successor_it_has_today(workflow, state_name, successors):
    """Adding a branch must not move a single edge of the path that already
    works, so each one is asserted rather than assumed."""
    assert next_states(workflow, state_name) == successors


def test_only_the_branch_heads_are_told_the_task(workflow):
    """Every later State reads the work from the Artifacts the earlier ones
    wrote, which is what makes Clearing safe. Both branch heads Clear, so both
    restate the task; Naiad holds it and interpolates it into every Prompt."""
    told = [name for name in SKILLS if TASK in delivered(workflow, name)]

    assert sorted(told) == BRANCH_HEADS


def test_the_implement_loop_clears_and_the_design_phases_do_not(workflow):
    """Each ticket starts fresh; the spec and the tickets are synthesised from
    the grilling conversation and would lose it. The diagnosing State Clears so
    that nothing upstream of it — a classifier's guess at what kind of bug this
    is, most of all — becomes the starting hypothesis."""
    clearing = [state.name for state in workflow.states if state.clear]

    assert clearing == ["diagnose", "implement", "pull-request", "review-fix"]


def test_the_diagnosing_state_runs_the_whole_discipline_in_one_state(workflow):
    """One State, all six phases, fix and post-mortem included. There is no
    fixing State to announce and no diagnosis Artifact to write: the only
    honest cut is mid-discipline, and the review it would enable is not wanted
    on the path where the hypothesis is confirmed (ADR 0008)."""
    assert [state.name for state in workflow.states if "fix" in state.name] == ["review-fix"]
    assert "end to end" in delivered(workflow, "diagnose")


def test_the_diagnosing_state_states_the_criterion_for_choosing_its_exit(workflow):
    """The Workflow supplies the candidate names; the Prompt supplies when each
    applies. Naiad decides nothing about which branch is right, so if the
    criterion is not in the Prompt it is nowhere."""
    prompt = delivered(workflow, "diagnose")

    assert "no-repro" in prompt
    assert "feedback loop" in prompt


def test_the_diagnosing_state_restates_the_task_because_it_clears(workflow):
    assert workflow.state("diagnose").clear
    assert TASK in delivered(workflow, "diagnose")


def test_the_implement_loop_tells_the_agent_to_re_announce_itself(workflow):
    """One State, announced once per ticket. The interpolated successor is the
    State after the loop, so the loop's own name has to be in the Prompt or the
    agent has nothing to announce for the second ticket."""
    assert "announce implement" in delivered(workflow, "implement")


def test_the_pull_request_state_waits_for_the_review_before_announcing(workflow):
    """The review-fix State has nothing to work from until Claude Code Review
    has posted its findings, so the wait belongs before the Announcement rather
    than after it — announcing early delivers /fix-review an empty pull request.

    The wait happens inside the turn, because nothing wakes an agent that ends
    one: a turn that ends without an Announcement is Nudged twice and then parks
    the Run for a human (naiad.domain.decide). Naiad gains nothing for this —
    the Prompt carries it (ADR 0006).
    """
    prompt = delivered(workflow, "pull-request")

    assert "Claude Code Review" in prompt
    assert "single long-running command" in prompt


def test_the_pull_request_state_waits_in_one_command_within_the_tool_timeout(workflow):
    """The cost of the wait is the Prompt's business, and one blocking command
    is what makes it cheap: a loop of separate checks re-sends the accumulated
    context every time round. Ten minutes because that is the Bash tool's
    ceiling, so the budget and the cap are one number rather than two."""
    assert "ten-minute timeout" in delivered(workflow, "pull-request")


def test_the_pull_request_state_waits_only_on_the_review_check(workflow):
    """Waiting on every check would overrun the budget for a reason that has
    nothing to do with the review: the build checks on an HCGPS pull request run
    far longer than the review, which finishes in about three minutes."""
    prompt = delivered(workflow, "pull-request")

    assert "not every check" in prompt


def test_the_pull_request_state_announces_even_if_no_review_arrives(workflow):
    """A repository that runs no review would otherwise hold the Run at a State
    waiting for something that is never coming."""
    assert "if no review" in delivered(workflow, "pull-request").lower()


def test_the_review_fix_state_tolerates_a_pull_request_with_no_findings(workflow):
    """The timeout path announces review-fix anyway, and Clearing means the
    Prompt arrives in a context that never heard the timeout announced. Without
    this the State is told to fetch findings that are not there, and /fix-review
    — whose contract is that its findings are handed to it — is the State most
    likely to stop and ask a human nobody is awake to be."""
    assert "no review findings" in delivered(workflow, "review-fix")


def test_no_prompt_after_a_clearing_state_refers_back_to_the_cleared_context(workflow):
    """The symptom deferred issue 02 warns about, caught where it is cheap: a
    Prompt delivered into a wiped context that says 'you just' is naming
    something the agent can no longer remember."""
    clearing = [state.name for state in workflow.states if state.clear]

    for state_name in clearing:
        assert "you just" not in delivered(workflow, state_name)


def kickoff(tmp_path, sessions, **options):
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
        **options,
    )

    (spawn,) = sessions.spawned
    return spawn.initial_prompt


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_a_run_can_be_started_at_either_branch_head(workflow, tmp_path, sessions, head):
    """An operator who already knows which kind of work they have starts the
    Run at the branch head, and the head's Prompt arrives with the task in it."""
    prompt = kickoff(tmp_path, sessions, start_state=head)

    assert prompt.startswith(f"{SKILLS[head]} {TASK}")
    for successor in next_states(workflow, head):
        assert f"announce {successor}" in prompt


def test_a_run_started_with_no_state_named_begins_at_the_first_declared_one(tmp_path, sessions):
    """Which is the diagnosing State, because the bug branch is declared first.
    Asserted against the shipped file rather than a fixture: an operator who
    names nothing gets this Prompt, and until the classifying State is declared
    in front of it a feature Run has to name `grill` itself."""
    assert kickoff(tmp_path, sessions).startswith(f"/diagnosing-bugs {TASK}")


def test_an_unattended_run_tells_the_two_kinds_of_gate_state_apart(workflow):
    """The same file run with --skip-gates, asserted at both Gates together so
    they cannot later be conflated (ADR 0007).

    The grilling State's Prompt names the spec rather than the Gate State
    nobody is there to release: `review` is a routine checkpoint in the declared
    order, and an unattended Run may decline that review. The diagnosing State
    keeps `no-repro`, because a Gate State named as a candidate is a destination
    the agent chose — deleting it would tell a Run that could not reproduce the
    bug to open a pull request for a fix built on no diagnosis.
    """
    assert next_states(workflow, "grill", skip_gates=True) == ("spec",)
    assert next_states(workflow, "grill") == ("review",)

    assert next_states(workflow, "diagnose", skip_gates=True) == ("no-repro", "pull-request")
    assert next_states(workflow, "diagnose") == ("no-repro", "pull-request")
