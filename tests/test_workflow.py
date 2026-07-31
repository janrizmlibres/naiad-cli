import pytest

from naiad.domain.workflow import WorkflowError, parse_workflow

WELL_FORMED = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"
clear = false

[[states]]
name = "review"

[[states]]
name = "spec"
prompt = "/to-spec"
clear = true

[[states]]
name = "done"
terminal = true
"""


def test_parses_states_in_declared_order():
    workflow = parse_workflow(WELL_FORMED)

    assert [s.name for s in workflow.states] == ["grill", "review", "spec", "done"]


def test_parses_prompts_clear_flags_and_terminal_marking():
    workflow = parse_workflow(WELL_FORMED)
    grill, review, spec, done = workflow.states

    assert grill.prompt == "/grill-with-docs {task}"
    assert grill.clear is False
    assert grill.terminal is False
    assert spec.clear is True
    assert done.terminal is True
    assert review.prompt is None


def test_a_state_without_a_prompt_is_a_gate_state():
    workflow = parse_workflow(WELL_FORMED)

    assert workflow.state("review").is_gate_state is True
    assert workflow.state("grill").is_gate_state is False


def test_a_state_may_declare_multiple_candidate_successors():
    workflow = parse_workflow(
        """
        name = "branching"

        [[states]]
        name = "classify"
        prompt = "decide"
        next = ["bug", "feature"]

        [[states]]
        name = "bug"
        prompt = "fix it"

        [[states]]
        name = "feature"
        prompt = "build it"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("classify").next_candidates == ("bug", "feature")
    assert workflow.state("bug").next_candidates == ()


@pytest.mark.parametrize(
    "source, expected",
    [
        pytest.param("name = ", "not valid TOML", id="unparseable"),
        pytest.param('name = "w"', "declares no states", id="no states"),
        pytest.param(
            'name = "w"\n[[states]]\nprompt = "hi"',
            "state 1 has no name",
            id="nameless state",
        ),
        pytest.param(
            '[[states]]\nname = "a"\nterminal = true',
            "no name",
            id="nameless workflow",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nname = "a"\n[[states]]\nname = "a"\nterminal = true',
            "duplicate state name 'a'",
            id="duplicate names",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nname = "a"\nnext = ["nope"]\n[[states]]\nname = "b"\nterminal = true',
            "state 'a' declares unknown successor 'nope'",
            id="unknown successor",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nname = "a"\nprompt = "x"',
            "no terminal state",
            id="no terminal state",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nname = "a"\nclear = "yes"\n[[states]]\nname = "b"\nterminal = true',
            "state 'a': clear must be a boolean",
            id="bad clear type",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nname = "a"\nprompt = 3\n[[states]]\nname = "b"\nterminal = true',
            "state 'a': prompt must be a string",
            id="bad prompt type",
        ),
    ],
)
def test_a_malformed_workflow_is_rejected_with_an_error_naming_the_problem(source, expected):
    with pytest.raises(WorkflowError) as caught:
        parse_workflow(source)

    assert expected in str(caught.value)


def test_the_error_names_the_source_of_the_workflow():
    with pytest.raises(WorkflowError) as caught:
        parse_workflow('name = "w"', source="/tmp/broken.toml")

    assert "/tmp/broken.toml" in str(caught.value)
