"""The Workflow files that ship, asserted only for what any Workflow file must
hold: it loads under its own name, its Prompts render with no slot left, every
exit is named to the agent, and a Run can start from it.

Two files ship: the starter inside the package, and the personal Workflow in
`workflows/`, which stays a tracked file anyone can read. Every
invariant runs over both, because none of them reads content.

Nothing here reads the file's meaning — which States it declares, what its
Prompts pin, which settings it chooses — so editing the file never breaks a
test. What the Workflow says is reviewed in the file itself and exercised by
manual smoke.

Every parametrised list below is derived from the loaded files rather than
written out, which is what keeps a State added or removed from touching this
file at all.
"""

import re
from importlib.resources import files
from pathlib import Path

import pytest

from naiad.cli.kickoff import start_run
from naiad.cli.refusals import MissingSubject
from naiad.domain.prompt import (
    BRANCH_PLACEHOLDER,
    CHILDREN_PLACEHOLDER,
    SUBJECT_PLACEHOLDER,
    render_prompt,
)
from naiad.domain.transitions import deviation, next_states
from naiad.domain.workflow import load_workflow
from naiad.runtime.run import RunStore

SHIPPED_PATHS = (
    Path(str(files("naiad.workflows").joinpath("starter.toml"))),
    Path(__file__).resolve().parents[1] / "workflows" / "matt-pocock.toml",
)

# Sample interpolations, arbitrary by design: every assertion holds for any
# values, so none of these encodes anything about the file's content.
TASK = "add dark mode"
SUBJECT = "tickets/dark-mode/issues/04-toggle.md"
BRANCH = "TASK-8546"
PREDECESSOR = "TASK-8500"

# The renderer's closed set (naiad.domain.prompt): a slot spelled any other
# way is delivered to the agent verbatim.
PLACEHOLDERS = (
    "{task}",
    "{next_state}",
    SUBJECT_PLACEHOLDER,
    BRANCH_PLACEHOLDER,
    "{predecessor}",
    CHILDREN_PLACEHOLDER,
)

# What a slot looks like when an author writes one. Deliberately narrow — a
# Prompt may carry code, and code's braces are not slots — but wide enough to
# catch the misspellings of the names above.
PLACEHOLDER_SHAPED = re.compile(r"\{[a-z_]+\}")

# Loaded at module level because the parametrised lists below are read at
# collection time. A file that fails to load fails every test here at once,
# which is the right size for that mistake.
WORKFLOWS = {path: load_workflow(path) for path in SHIPPED_PATHS}


def each_workflow():
    return [pytest.param(path, id=path.stem) for path in SHIPPED_PATHS]


def each_state(keep):
    """Every (file, State name) the predicate keeps, derived from the loaded
    files so that adding a State to either touches nothing here."""
    return [
        pytest.param(path, state.name, id=f"{path.stem}:{state.name}")
        for path, workflow in WORKFLOWS.items()
        for state in workflow.states
        if keep(state)
    ]


def delivers(state):
    return state.prompt is not None


def names_a_subject(state):
    return state.prompt is not None and SUBJECT_PLACEHOLDER in state.prompt


DELIVERING = each_state(delivers)
CLEARING = each_state(lambda state: state.clear and delivers(state))
BRANCHING = each_state(lambda state: bool(state.next_candidates))
NEEDING_A_SUBJECT = each_state(names_a_subject)
STARTABLE_BARE = each_state(lambda state: delivers(state) and not names_a_subject(state))


def delivered(path, state_name, subject=SUBJECT, branch=BRANCH, predecessor=PREDECESSOR):
    """A State's Prompt as the agent reads it, with the successors the Workflow
    resolves interpolated — which is what Naiad sends (naiad.runtime.loop).

    Every value is supplied to every State whether or not its Prompt has the
    slot: a Prompt without one is unaffected, and passing them everywhere means
    no assertion here silently depends on which States use which."""
    workflow = WORKFLOWS[path]
    return render_prompt(
        workflow.state(state_name).prompt,
        task=TASK,
        next_states=next_states(workflow, state_name),
        subject=subject,
        branch=branch,
        predecessor=predecessor,
    )


@pytest.mark.parametrize("path", each_workflow())
def test_the_declared_name_matches_the_files_stem(path):
    """The library refuses a file whose declared name disagrees with its stem,
    and a shipped file is one an operator puts there — so the mismatch would be
    caught when it is first run by name, which is later and further from the
    edit."""
    assert WORKFLOWS[path].name == path.stem


@pytest.mark.parametrize(("path", "state_name"), DELIVERING)
def test_every_slot_a_prompt_writes_is_one_the_renderer_fills(path, state_name):
    """The renderer substitutes its closed set and leaves everything else
    alone, because a Prompt is prose that may carry code rather than a format
    string (naiad.domain.prompt). So a misspelled slot is an error nowhere at
    runtime — it reaches the agent verbatim — and is caught here instead."""
    raw = WORKFLOWS[path].state(state_name).prompt

    for token in PLACEHOLDER_SHAPED.findall(raw):
        assert token in PLACEHOLDERS, f"{state_name} writes {token}, which no renderer fills"


@pytest.mark.parametrize(("path", "state_name"), DELIVERING)
def test_every_prompt_names_each_state_it_may_announce(path, state_name):
    """The Workflow file owns the ordering, and the agent can only announce a
    name it has been given. Every successor, at a fork too: a Prompt naming one
    exit of two would decide the branch in the place that is least visible."""
    prompt = delivered(path, state_name)

    for successor in next_states(WORKFLOWS[path], state_name):
        assert successor in prompt


@pytest.mark.parametrize("path", each_workflow())
def test_every_non_terminal_state_leads_somewhere(path):
    """A non-terminal State with nothing after it strands the Run: the agent
    announces, and the Protocol has no name to expect next. The loader refuses
    a file with no terminal State at all; where each State leads is only
    resolvable per State, so it is asserted here."""
    workflow = WORKFLOWS[path]
    for state in workflow.states:
        if state.terminal:
            assert state.next_candidates == ()
        else:
            assert next_states(workflow, state.name) != ()


@pytest.mark.parametrize(("path", "state_name"), BRANCHING)
def test_announcing_any_declared_candidate_is_never_a_deviation(path, state_name):
    """Choosing correctly at a fork is not recorded as having left the path,
    whichever way the choice goes. The off-path case is asserted alongside it
    because an empty expectation also reports no Deviation: without it this
    passes just as well against a Workflow with no candidates anywhere."""
    workflow = WORKFLOWS[path]
    candidates = workflow.state(state_name).next_candidates

    for candidate in candidates:
        assert deviation(workflow, announced=candidate, previous_state=state_name) == ()
    assert (
        deviation(workflow, announced="a-state-this-file-never-declares", previous_state=state_name)
        == candidates
    )


@pytest.mark.parametrize(("path", "state_name"), CLEARING)
def test_no_prompt_after_a_clear_refers_back_to_the_cleared_context(path, state_name):
    """The symptom deferred issue 02 warns about, caught where it is cheap: a
    Prompt delivered into a wiped context that says 'you just' is naming
    something the agent can no longer remember."""
    assert "you just" not in delivered(path, state_name)


def kickoff(path, tmp_path, sessions, **options):
    repo = tmp_path / "repo"
    repo.mkdir()

    start_run(
        workflow_path=path,
        task=TASK,
        target_repo=repo,
        working_branch=BRANCH,
        store=RunStore(tmp_path / "runs"),
        sessions=sessions,
        run_id=f"20260720-120000-{path.stem}",
        claude_session_id="11111111-1111-1111-1111-111111111111",
        created_at="2026-07-20T12:00:00Z",
        **options,
    )

    (spawn,) = sessions.spawned
    return spawn.initial_prompt


@pytest.mark.parametrize("path", each_workflow())
def test_a_run_started_with_no_state_named_begins_at_the_first_state(path, tmp_path, sessions):
    """The operator names nothing and receives the first State's Prompt,
    rendered exactly as `delivered` renders it — asserted as equality so the
    kickoff path and the rendering path cannot quietly disagree."""
    first = WORKFLOWS[path].states[0]
    if first.prompt is None or SUBJECT_PLACEHOLDER in first.prompt:
        pytest.skip("the file's first state does not deliver a bare prompt")

    prompt = kickoff(path, tmp_path, sessions)

    assert prompt == delivered(path, first.name, subject=None, predecessor=None)


@pytest.mark.parametrize(("path", "state_name"), STARTABLE_BARE)
def test_a_run_can_start_at_any_state_that_delivers(path, tmp_path, sessions, state_name):
    """The escape hatch for an operator who already knows where the work
    starts, held open for every delivering State rather than the ones some
    table blesses."""
    prompt = kickoff(path, tmp_path, sessions, start_state=state_name)

    assert prompt == delivered(path, state_name, subject=None, predecessor=None)


@pytest.mark.parametrize(("path", "state_name"), NEEDING_A_SUBJECT)
def test_a_state_whose_prompt_names_a_subject_refuses_to_start_without_one(
    path, tmp_path, sessions, state_name
):
    """Refused rather than rendered empty: a Prompt with a Subject
    slot and nothing to fill it would tell the agent to trust a decision about
    an item that was never named."""
    with pytest.raises(MissingSubject):
        kickoff(path, tmp_path, sessions, start_state=state_name)

    assert sessions.spawned == []


@pytest.mark.parametrize(("path", "state_name"), NEEDING_A_SUBJECT)
def test_a_run_started_with_a_subject_is_delivered_that_subject(
    path, tmp_path, sessions, state_name
):
    """The other half of the refusal: named, the Subject reaches the Prompt,
    which is what makes refusing the bare form a correction rather than a
    removal."""
    prompt = kickoff(path, tmp_path, sessions, start_state=state_name, subject=SUBJECT)

    assert prompt == delivered(path, state_name, predecessor=None)
    assert SUBJECT in prompt
