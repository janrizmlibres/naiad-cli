from naiad.domain.prompt import render_prompt


def test_interpolates_the_task():
    rendered = render_prompt("/grill {task}", task="add dark mode", next_state="review")

    assert rendered == "/grill add dark mode"


def test_interpolates_the_expected_next_state():
    rendered = render_prompt(
        "do the work, then announce {next_state}", task="t", next_state="spec"
    )

    assert rendered == "do the work, then announce spec"


def test_interpolates_every_occurrence():
    rendered = render_prompt("{task} / {task}", task="t", next_state="s")

    assert rendered == "t / t"


def test_a_missing_next_state_renders_as_nothing():
    rendered = render_prompt("announce {next_state}", task="t", next_state=None)

    assert rendered == "announce "


def test_leaves_unrecognised_braces_untouched():
    rendered = render_prompt('return {"ok": true} for {task}', task="t", next_state="s")

    assert rendered == 'return {"ok": true} for t'
