from naiad.domain.prompt import render_prompt


def test_interpolates_the_task():
    rendered = render_prompt("/grill {task}", task="add dark mode", next_states=("review",))

    assert rendered == "/grill add dark mode"


def test_interpolates_the_expected_next_state():
    rendered = render_prompt(
        "do the work, then announce {next_state}", task="t", next_states=("spec",)
    )

    assert rendered == "do the work, then announce spec"


def test_a_branching_state_names_every_candidate():
    """The Workflow supplies the names; the Prompt's own text supplies the
    criterion for choosing between them. Nothing in Naiad decides which is
    right."""
    rendered = render_prompt(
        "then announce {next_state}", task="t", next_states=("no-repro", "pull-request")
    )

    assert rendered == "then announce no-repro or pull-request"


def test_three_candidates_read_as_a_list_rather_than_a_run_on():
    rendered = render_prompt("announce {next_state}", task="t", next_states=("a", "b", "c"))

    assert rendered == "announce a, b or c"


def test_interpolates_every_occurrence():
    rendered = render_prompt("{task} / {task}", task="t", next_states=("s",))

    assert rendered == "t / t"


def test_a_missing_next_state_renders_as_nothing():
    rendered = render_prompt("announce {next_state}", task="t", next_states=())

    assert rendered == "announce "


def test_leaves_unrecognised_braces_untouched():
    rendered = render_prompt('return {"ok": true} for {task}', task="t", next_states=("s",))

    assert rendered == 'return {"ok": true} for t'
