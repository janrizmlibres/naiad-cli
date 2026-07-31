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


def test_interpolates_the_subject():
    """What the Announcement was about, carried into the Prompt across the
    Clear so the receiving context is told what to work on rather than asked to
    work it out (ADR 0009)."""
    rendered = render_prompt(
        "/implement the ticket at {subject}",
        task="t",
        next_states=("s",),
        subject=".scratch/f/issues/04-x.md",
    )

    assert rendered == "/implement the ticket at .scratch/f/issues/04-x.md"


def test_a_prompt_with_no_subject_slot_is_unaffected_by_one():
    """A Subject belongs to the Announcement rather than to the Prompt, so a
    Prompt with no slot for one is rendered as written. The Run log is the
    other reader (ADR 0009)."""
    rendered = render_prompt("/implement", task="t", next_states=("s",), subject="a-ticket.md")

    assert rendered == "/implement"


def test_a_missing_subject_renders_as_nothing():
    """render_prompt does not guard this — announcing without a Subject a
    Prompt requires is rejected at the announce command, where the agent can
    still fix it inside its own turn (ADR 0009)."""
    rendered = render_prompt("at {subject}", task="t", next_states=("s",))

    assert rendered == "at "


def test_leaves_unrecognised_braces_untouched():
    rendered = render_prompt('return {"ok": true} for {task}', task="t", next_states=("s",))

    assert rendered == 'return {"ok": true} for t'
