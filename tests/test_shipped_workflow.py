"""The one Workflow that ships, asserted only for what any Workflow file must
hold: it loads under its own name, its Prompts render with no slot left, every
exit is named to the agent, and a Run can start from it (ADR 0043).

Nothing here reads the file's meaning — which States it declares, what its
Prompts pin, which settings it chooses — so editing the file never breaks a
test. What the Workflow says is reviewed in the file itself, against the
decisions docs/workflow-authoring.md indexes per State, and exercised by manual
smoke (docs/smoke/matt-pocock.md).

Every parametrised list below is derived from the loaded file rather than
written out, which is what keeps a State added or removed from touching this
file at all.
"""

import re
from pathlib import Path

import pytest

from naiad.cli.kickoff import start_run
from naiad.cli.refusals import MissingSubject
from naiad.domain.prompt import SUBJECT_PLACEHOLDER, render_prompt
from naiad.domain.transitions import deviation, next_states
from naiad.domain.workflow import load_workflow
from naiad.runtime.run import RunStore

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / "workflows" / "matt-pocock.toml"

# Sample interpolations, arbitrary by design: every assertion holds for any
# values, so none of these encodes anything about the file's content.
TASK = "add dark mode"
SUBJECT = ".scratch/dark-mode/issues/04-toggle.md"
BRANCH = "MC-AGENT-8546"
PREDECESSOR = "MC-AGENT-8500"

# The renderer's closed set (naiad.domain.prompt): a slot spelled any other
# way is delivered to the agent verbatim.
PLACEHOLDERS = ("{task}", "{next_state}", "{subject}", "{branch}", "{predecessor}")

# What a slot looks like when an author writes one. Deliberately narrow — a
# Prompt may carry code, and code's braces are not slots — but wide enough to
# catch the misspellings of the five names above.
PLACEHOLDER_SHAPED = re.compile(r"\{[a-z_]+\}")

# Loaded at module level because the parametrised lists below are read at
# collection time. A file that fails to load fails every test here at once,
# which is the right size for that mistake.
WORKFLOW = load_workflow(WORKFLOW_PATH)

DELIVERING = [state.name for state in WORKFLOW.states if state.prompt is not None]
CLEARING = [state.name for state in WORKFLOW.states if state.clear and state.prompt is not None]
BRANCHING = [state.name for state in WORKFLOW.states if state.next_candidates]
NEEDING_A_SUBJECT = [
    state.name
    for state in WORKFLOW.states
    if state.prompt is not None and SUBJECT_PLACEHOLDER in state.prompt
]
STARTABLE_BARE = [name for name in DELIVERING if name not in NEEDING_A_SUBJECT]


def delivered(state_name, subject=SUBJECT, branch=BRANCH, predecessor=PREDECESSOR):
    """A State's Prompt as the agent reads it, with the successors the Workflow
    resolves interpolated — which is what Naiad sends (naiad.runtime.loop).

    Every value is supplied to every State whether or not its Prompt has the
    slot: a Prompt without one is unaffected, and passing them everywhere means
    no assertion here silently depends on which States use which."""
    return render_prompt(
        WORKFLOW.state(state_name).prompt,
        task=TASK,
        next_states=next_states(WORKFLOW, state_name),
        subject=subject,
        branch=branch,
        predecessor=predecessor,
    )


def test_the_declared_name_matches_the_files_stem():
    """The library refuses a file whose declared name disagrees with its stem,
    and this is the file Naiad makes the library entry for — so the mismatch
    would be caught at install, which is later and further from the edit."""
    assert WORKFLOW.name == WORKFLOW_PATH.stem


@pytest.mark.parametrize("state_name", DELIVERING)
def test_every_slot_a_prompt_writes_is_one_the_renderer_fills(state_name):
    """The renderer substitutes its closed set and leaves everything else
    alone, because a Prompt is prose that may carry code rather than a format
    string (naiad.domain.prompt). So a misspelled slot is an error nowhere at
    runtime — it reaches the agent verbatim — and is caught here instead."""
    raw = WORKFLOW.state(state_name).prompt

    for token in PLACEHOLDER_SHAPED.findall(raw):
        assert token in PLACEHOLDERS, f"{state_name} writes {token}, which no renderer fills"


@pytest.mark.parametrize("state_name", DELIVERING)
def test_every_prompt_names_each_state_it_may_announce(state_name):
    """The Workflow file owns the ordering, and the agent can only announce a
    name it has been given. Every successor, at a fork too: a Prompt naming one
    exit of two would decide the branch in the place that is least visible."""
    prompt = delivered(state_name)

    for successor in next_states(WORKFLOW, state_name):
        assert successor in prompt


def test_every_non_terminal_state_leads_somewhere():
    """A non-terminal State with nothing after it strands the Run: the agent
    announces, and the Protocol has no name to expect next. The loader refuses
    a file with no terminal State at all; where each State leads is only
    resolvable per State, so it is asserted here."""
    for state in WORKFLOW.states:
        if state.terminal:
            assert state.next_candidates == ()
        else:
            assert next_states(WORKFLOW, state.name) != ()


@pytest.mark.parametrize("state_name", BRANCHING)
def test_announcing_any_declared_candidate_is_never_a_deviation(state_name):
    """Choosing correctly at a fork is not recorded as having left the path,
    whichever way the choice goes. The off-path case is asserted alongside it
    because an empty expectation also reports no Deviation: without it this
    passes just as well against a Workflow with no candidates anywhere."""
    candidates = WORKFLOW.state(state_name).next_candidates

    for candidate in candidates:
        assert deviation(WORKFLOW, announced=candidate, previous_state=state_name) == ()
    assert (
        deviation(WORKFLOW, announced="a-state-this-file-never-declares", previous_state=state_name)
        == candidates
    )


@pytest.mark.parametrize("state_name", CLEARING)
def test_no_prompt_after_a_clear_refers_back_to_the_cleared_context(state_name):
    """The symptom deferred issue 02 warns about, caught where it is cheap: a
    Prompt delivered into a wiped context that says 'you just' is naming
    something the agent can no longer remember."""
    assert "you just" not in delivered(state_name)


def kickoff(tmp_path, sessions, **options):
    repo = tmp_path / "repo"
    repo.mkdir()

    start_run(
        workflow_path=WORKFLOW_PATH,
        task=TASK,
        target_repo=repo,
        working_branch=BRANCH,
        store=RunStore(tmp_path / "runs"),
        sessions=sessions,
        run_id="20260720-120000-matt-pocock",
        claude_session_id="11111111-1111-1111-1111-111111111111",
        created_at="2026-07-20T12:00:00Z",
        **options,
    )

    (spawn,) = sessions.spawned
    return spawn.initial_prompt


def test_a_run_started_with_no_state_named_begins_at_the_first_state(tmp_path, sessions):
    """The operator names nothing and receives the first State's Prompt,
    rendered exactly as `delivered` renders it — asserted as equality so the
    kickoff path and the rendering path cannot quietly disagree."""
    first = WORKFLOW.states[0]
    if first.prompt is None or SUBJECT_PLACEHOLDER in first.prompt:
        pytest.skip("the file's first state does not deliver a bare prompt")

    prompt = kickoff(tmp_path, sessions)

    assert prompt == delivered(first.name, subject=None, predecessor=None)


@pytest.mark.parametrize("state_name", STARTABLE_BARE)
def test_a_run_can_start_at_any_state_that_delivers(tmp_path, sessions, state_name):
    """The escape hatch for an operator who already knows where the work
    starts, held open for every delivering State rather than the ones some
    table blesses."""
    prompt = kickoff(tmp_path, sessions, start_state=state_name)

    assert prompt == delivered(state_name, subject=None, predecessor=None)


@pytest.mark.parametrize("state_name", NEEDING_A_SUBJECT)
def test_a_state_whose_prompt_names_a_subject_refuses_to_start_without_one(
    tmp_path, sessions, state_name
):
    """Refused rather than rendered empty (ADR 0009): a Prompt with a Subject
    slot and nothing to fill it would tell the agent to trust a decision about
    an item that was never named."""
    with pytest.raises(MissingSubject):
        kickoff(tmp_path, sessions, start_state=state_name)

    assert sessions.spawned == []


@pytest.mark.parametrize("state_name", NEEDING_A_SUBJECT)
def test_a_run_started_with_a_subject_is_delivered_that_subject(tmp_path, sessions, state_name):
    """The other half of the refusal: named, the Subject reaches the Prompt,
    which is what makes refusing the bare form a correction rather than a
    removal."""
    prompt = kickoff(tmp_path, sessions, start_state=state_name, subject=SUBJECT)

    assert prompt == delivered(state_name, predecessor=None)
    assert SUBJECT in prompt
