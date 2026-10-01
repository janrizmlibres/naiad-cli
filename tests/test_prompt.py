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
    work it out."""
    rendered = render_prompt(
        "/implement the ticket at {subject}",
        task="t",
        next_states=("s",),
        subject="tickets/f/issues/04-x.md",
    )

    assert rendered == "/implement the ticket at tickets/f/issues/04-x.md"


def test_a_prompt_with_no_subject_slot_is_unaffected_by_one():
    """A Subject belongs to the Announcement rather than to the Prompt, so a
    Prompt with no slot for one is rendered as written. The Run log is the
    other reader."""
    rendered = render_prompt("/implement", task="t", next_states=("s",), subject="a-ticket.md")

    assert rendered == "/implement"


def test_a_missing_subject_renders_as_nothing():
    """render_prompt does not guard this — announcing without a Subject a
    Prompt requires is rejected at the announce command, where the agent can
    still fix it inside its own turn."""
    rendered = render_prompt("at {subject}", task="t", next_states=("s",))

    assert rendered == "at "


def test_leaves_unrecognised_braces_untouched():
    rendered = render_prompt('return {"ok": true} for {task}', task="t", next_states=("s",))

    assert rendered == 'return {"ok": true} for t'


def test_interpolates_the_working_branch():
    """A Run-level fact like the task, so it reaches every Prompt the Run
    delivers rather than only the first, and survives a Clear."""
    rendered = render_prompt(
        "check out {branch}", task="t", next_states=("s",), branch="TASK-8546"
    )

    assert rendered == "check out TASK-8546"


def test_interpolates_the_predecessor():
    """Substituted without being read, exactly as a Subject is: whether to
    actually stand on it is decided in the Prompt."""
    rendered = render_prompt(
        "based on {predecessor}", task="t", next_states=("s",), predecessor="TASK-8000"
    )

    assert rendered == "based on TASK-8000"


def test_a_missing_predecessor_renders_as_nothing():
    """The Predecessor is optional — the first Entry for a repository has
    none — so a Prompt naming one renders empty rather than raising."""
    rendered = render_prompt("based on {predecessor}", task="t", next_states=("s",))

    assert rendered == "based on "


def test_a_missing_working_branch_renders_as_nothing():
    """Nothing here guards it. The refusal belongs at kickoff, where the
    operator is standing at the terminal and can retype the command."""
    rendered = render_prompt("check out {branch}", task="t", next_states=("s",))

    assert rendered == "check out "


def test_leaves_a_placeholder_naiad_does_not_define_untouched():
    """`--base` is a flag, not a placeholder: the Prompt names {predecessor}.
    Only the placeholders Naiad defines are replaced."""
    rendered = render_prompt(
        "{base} then {branch}", task="t", next_states=("s",), branch="B", predecessor="P"
    )

    assert rendered == "{base} then B"


def test_interpolates_one_line_per_child():
    from naiad.domain.join import FinishedChild

    rendered = render_prompt(
        "take in:\n{children}\nthen announce {next_state}",
        task="t",
        next_states=("implement",),
        children=(
            FinishedChild("e-1", "03.md", "feat--03", "/work/repo-wt--03", "completed"),
            FinishedChild("e-2", None, None, "/work/repo-wt--04", "cancelled"),
        ),
    )

    assert rendered == (
        "take in:\n"
        "- 03.md: completed, branch feat--03, working tree /work/repo-wt--03\n"
        "- -: cancelled, branch -, working tree /work/repo-wt--04\n"
        "then announce implement"
    )


def test_no_children_named_renders_the_slot_as_nothing():
    rendered = render_prompt("take in [{children}]", task="t", next_states=(), children=())

    assert rendered == "take in []"
