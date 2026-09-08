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


def test_a_state_takes_the_file_level_model_and_effort_unless_it_declares_its_own():
    workflow = parse_workflow(
        """
        name = "w"
        model = "sonnet"
        effort = "medium"

        [[states]]
        name = "grill"
        prompt = "/grill {task}"
        model = "opus"
        effort = "high"

        [[states]]
        name = "review"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("grill").model == "opus"
    assert workflow.state("grill").effort == "high"
    # The default reaches every State, Gate and Terminal included — delivery
    # is what decides whether anything is typed, not parsing.
    assert workflow.state("review").model == "sonnet"
    assert workflow.state("done").effort == "medium"


def test_a_workflow_mentioning_neither_key_gives_every_state_none():
    workflow = parse_workflow(WELL_FORMED)

    assert workflow.state("grill").model is None
    assert workflow.state("grill").effort is None


def test_a_state_may_declare_a_setting_with_no_file_level_default():
    """Absence is no opinion rather than an error (ADR 0040). A State declaring
    nothing gets None, so delivery types no Switch and the State runs on what
    the Session holds — which stickiness makes the Model the State before it
    set."""
    workflow = parse_workflow(
        """
        name = "w"

        [[states]]
        name = "a"
        prompt = "x"
        model = "opus"
        effort = "high"

        [[states]]
        name = "b"
        prompt = "y"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("a").model == "opus"
    assert workflow.state("a").effort == "high"
    assert workflow.state("b").model is None
    assert workflow.state("b").effort is None


def test_model_and_effort_default_independently():
    workflow = parse_workflow(
        """
        name = "w"
        model = "sonnet"

        [[states]]
        name = "a"
        prompt = "x"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("a").model == "sonnet"
    assert workflow.state("a").effort is None


def test_an_empty_state_key_is_kept_rather_than_read_as_absent():
    """Values are opaque (ADR 0026): an empty string is a value the session
    will refuse, not an absence for Naiad to interpret a default into."""
    workflow = parse_workflow(
        """
        name = "w"
        model = "sonnet"

        [[states]]
        name = "a"
        prompt = "x"
        model = ""

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("a").model == ""


def test_a_state_may_reserve_its_questions_for_the_human():
    """A State declaring `questions = "human"` is one whose Questions are never
    the Answerer's to settle (ADR 0046). Absence is the Answerer, which is what
    every State meant before the key existed."""
    workflow = parse_workflow(
        """
        name = "w"

        [[states]]
        name = "a"
        prompt = "x"
        questions = "human"

        [[states]]
        name = "b"
        prompt = "y"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("a").questions == "human"
    assert workflow.state("b").questions == "answerer"


def test_the_answerer_table_is_parsed_with_both_keys_optional():
    workflow = parse_workflow(
        """
        name = "w"

        [answerer]
        model = "haiku"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.answerer_model == "haiku"
    assert workflow.answerer_effort is None
    assert workflow.answerer_fallback is None


def test_the_answerers_fallback_is_parsed_as_an_opaque_string():
    """A comma-separated list the platform walks, never parsed by Naiad —
    the same opacity model and effort already have (ADR 0031)."""
    workflow = parse_workflow(
        """
        name = "w"

        [answerer]
        model = "haiku"
        fallback = "opus,sonnet"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.answerer_fallback == "opus,sonnet"


def test_a_workflow_without_an_answerer_table_has_no_answerer_opinion():
    workflow = parse_workflow(WELL_FORMED)

    assert workflow.answerer_model is None
    assert workflow.answerer_effort is None
    assert workflow.answerer_fallback is None


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
        pytest.param(
            'name = "w"\nmodel = 3\n[[states]]\nname = "b"\nterminal = true',
            "model must be a string",
            id="bad file-level model type",
        ),
        pytest.param(
            'name = "w"\nmodel = "s"\n[[states]]\nname = "a"\nmodel = 3\n[[states]]\nname = "b"\nterminal = true',
            "state 'a': model must be a string",
            id="bad state model type",
        ),
        pytest.param(
            'name = "w"\neffort = 3\n[[states]]\nname = "b"\nterminal = true',
            "effort must be a string",
            id="bad file-level effort type",
        ),
        pytest.param(
            'name = "w"\n[answerer]\nmodel = 3\n[[states]]\nname = "b"\nterminal = true',
            "answerer model must be a string",
            id="bad answerer model type",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nname = "a"\nquestions = "nobody"\n[[states]]\nname = "b"\nterminal = true',
            "state 'a': questions must be \"answerer\" or \"human\"",
            id="unknown questions value",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nname = "a"\nquestions = true\n[[states]]\nname = "b"\nterminal = true',
            "state 'a': questions must be \"answerer\" or \"human\"",
            id="bad questions type",
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
