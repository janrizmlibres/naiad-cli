import pytest

from naiad.domain.workflow import WorkflowError, load_workflow, parse_workflow

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


def test_a_workflow_with_no_answerer_table_gives_every_state_to_the_human():
    """The human is the default (ADR 0050): nothing is decided for an adopter
    who declared nothing."""
    workflow = parse_workflow(
        """
        name = "w"

        [[states]]
        name = "a"
        prompt = "x"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("a").questions == "human"
    assert workflow.state("a").questions_explicit is False


def test_declaring_the_answerer_table_gives_every_state_to_the_answerer_even_when_empty():
    workflow = parse_workflow(
        """
        name = "w"

        [answerer]

        [[states]]
        name = "a"
        prompt = "x"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("a").questions == "answerer"
    assert workflow.state("a").questions_explicit is False


def test_a_state_may_reserve_its_questions_for_the_human_in_a_file_with_the_table():
    workflow = parse_workflow(
        """
        name = "w"

        [answerer]

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
    assert workflow.state("a").questions_explicit is True
    assert workflow.state("b").questions == "answerer"


def test_a_state_may_opt_in_to_the_answerer_in_a_file_without_the_table():
    """The table carries settings and moves the default; the Answerer does not
    need it to exist. It runs on the platform's defaults (ADR 0050)."""
    workflow = parse_workflow(
        """
        name = "w"

        [[states]]
        name = "a"
        prompt = "x"
        questions = "answerer"

        [[states]]
        name = "b"
        prompt = "y"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("a").questions == "answerer"
    assert workflow.state("a").questions_explicit is True
    assert workflow.state("b").questions == "human"
    assert workflow.answerer_model is None
    assert workflow.answerer_effort is None
    assert workflow.answerer_fallback is None


def test_a_state_asking_for_the_human_in_a_file_without_the_table_has_asked():
    workflow = parse_workflow(
        """
        name = "w"

        [[states]]
        name = "a"
        prompt = "x"
        questions = "human"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.state("a").questions == "human"
    assert workflow.state("a").questions_explicit is True


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


def test_the_compaction_point_is_a_file_level_key_parsed_as_an_opaque_string():
    """Where the Session summarises itself is a property of the Session, set
    once at launch, so the key is the file's and never a State's. The value is
    handed to the launch verbatim and judged there, as a Model is (ADR 0047)."""
    workflow = parse_workflow(
        """
        name = "w"
        autocompact = "200k"

        [[states]]
        name = "done"
        terminal = true
        """
    )

    assert workflow.autocompact == "200k"


def test_a_workflow_that_names_no_compaction_point_has_no_opinion():
    """Absent means no flag, so a Workflow written before the key existed runs
    exactly as it did (ADR 0040, ADR 0047)."""
    workflow = parse_workflow(WELL_FORMED)

    assert workflow.autocompact is None


def test_a_compaction_point_that_is_not_a_string_is_rejected():
    with pytest.raises(WorkflowError, match="autocompact must be a string"):
        parse_workflow(
            """
            name = "w"
            autocompact = 200

            [[states]]
            name = "done"
            terminal = true
            """
        )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            'name = "w"\nquestons = "human"\n[[states]]\nname = "b"\nterminal = true',
            "unknown key 'questons' in the file; allowed: "
            "name, model, effort, autocompact, answerer, states",
            id="top level",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nname = "a"\nquestons = "human"\n[[states]]\nname = "b"\nterminal = true',
            "unknown key 'questons' in state 'a'; allowed: "
            "name, prompt, clear, terminal, next, model, effort, questions",
            id="state",
        ),
        pytest.param(
            'name = "w"\n[[states]]\nnmae = "a"\n[[states]]\nname = "b"\nterminal = true',
            "unknown key 'nmae' in state 1; allowed: "
            "name, prompt, clear, terminal, next, model, effort, questions",
            id="misspelt name",
        ),
        pytest.param(
            'name = "w"\n[answerer]\nmodle = "s"\n[[states]]\nname = "b"\nterminal = true',
            "unknown key 'modle' in [answerer]; allowed: model, effort, fallback",
            id="answerer",
        ),
    ],
)
def test_an_unknown_key_is_refused_naming_the_key_its_place_and_the_allowed_keys(
    source, expected
):
    with pytest.raises(WorkflowError) as caught:
        parse_workflow(source, source="w.toml")

    assert f"workflow w.toml: {expected}" in str(caught.value)


def test_a_workflow_file_with_an_unknown_key_fails_to_load(tmp_path):
    path = tmp_path / "w.toml"
    path.write_text(
        'name = "w"\n[[states]]\nname = "a"\nquestons = "human"\n[[states]]\nname = "b"\nterminal = true'
    )

    with pytest.raises(WorkflowError, match=f"workflow {path}: unknown key 'questons'"):
        load_workflow(path)
