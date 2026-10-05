"""What an author reads of a Workflow: the library, the file's own keys, and
its States as a table.

A row is read here as its cells, told apart by two spaces or more, the way a
person's eye and a script splitting on runs of spaces both find them. How a
State's facts are worded — its kind, its command, its marks — is asserted in
tests/test_listing.py, against the listing the adopting agent reads; asserted
here is that the author's table carries those same words, laid out under a
header and styled for a terminal.
"""

import re

from fake_terminal import styles_of
from naiad.cli.style import ABSENT
from naiad.cli.workflow_view import (
    render_library,
    render_state,
    render_state_list,
    render_workflow,
)
from naiad.domain.listing import render_states
from naiad.domain.workflow import parse_workflow

MARKED = """
name = "marked"
model = "opus"
autocompact = "200k"

[answerer]
fallback = "sonnet"

[[states]]
name = "classify"
next = ["plan", "review"]
prompt = "Decide what kind of work the following task is."

[[states]]
name = "plan"
clear = true
report = true
effort = "high"
questions = "human"
next = ["build"]
prompt = "/to-spec {task}"

[[states]]
name = "review"

[[states]]
name = "build"
prompt = "/implement {task}"

[[states]]
name = "done"
terminal = true
"""

ONLY_DONE = """
name = "demo"

[[states]]
name = "done"
terminal = true
"""

PROSE = """
name = "prose"

[[states]]
name = "plan"
prompt = "Plan it."

[[states]]
name = "done"
terminal = true
"""


def cells(line):
    return re.split(r"\s{2,}", str(line).strip())


def rows(shown):
    return [cells(line) for line in shown.splitlines()]


def row_of(shown, name):
    (row,) = [row for row in rows(shown) if row[0] == name]
    return row


# the State table


def test_the_states_stand_under_a_header_in_declared_order():
    shown = render_state_list(parse_workflow(MARKED), width=200)

    assert rows(shown)[0] == ["STATE", "KIND", "COMMAND", "NEXT", "MARKS"]
    assert [row[0] for row in rows(shown)[1:]] == ["classify", "plan", "review", "build", "done"]


def test_a_row_holds_the_kind_the_command_the_successors_then_the_marks():
    shown = render_state_list(parse_workflow(MARKED), width=200)

    assert row_of(shown, "plan") == [
        "plan",
        "prompt",
        "/to-spec",
        "→ build",
        "clears",
        "report",
        "questions: human",
        "model: opus",
        "effort: high",
    ]


def test_a_cell_with_nothing_to_show_holds_a_dash():
    """A blank cell shifts the eye to the next column's words, so a Gate's
    missing command would be read in its successors' place."""
    shown = render_state_list(parse_workflow(MARKED), width=200)

    assert row_of(shown, "review") == ["review", "gate", ABSENT, ABSENT, ABSENT]
    assert row_of(shown, "classify")[2] == ABSENT


def test_a_column_no_state_fills_is_left_out():
    """As the agent's listing leaves out a command column of blanks: a column
    of dashes is one more thing to read past."""
    assert rows(render_state_list(parse_workflow(ONLY_DONE), width=200)) == [
        ["STATE", "KIND"],
        ["done", "terminal"],
    ]
    assert "COMMAND" not in rows(render_state_list(parse_workflow(PROSE), width=200))[0]


def test_the_author_reads_the_words_the_adopting_agent_reads():
    """Two layouts of one set of facts: with its dashes left out, each row is
    the agent's line for that State, so a mark cannot mean one thing to the
    author and another to the agent."""
    workflow = parse_workflow(MARKED)

    agents = [cells(line) for line in render_states(workflow).splitlines()[1:]]
    authors = [
        [cell for cell in row if cell != ABSENT]
        for row in rows(render_state_list(workflow, width=200))[1:]
    ]

    assert authors == agents


def test_only_the_marks_are_cut_to_the_width():
    """The successors are where the Run may go next, and are kept whole; the
    marks are the part a narrow terminal can lose the end of."""
    shown = render_state_list(parse_workflow(MARKED), width=60)

    plan = row_of(shown, "plan")
    assert plan[:4] == ["plan", "prompt", "/to-spec", "→ build"]
    assert shown.splitlines()[2].endswith("…")
    assert "effort: high" not in shown


def test_each_cell_is_styled_for_what_it_holds():
    shown = render_state_list(parse_workflow(MARKED), width=200)
    header, classify, plan, review, _build, done = shown.text.split("\n")

    assert set(styles_of(header).values()) == {"header"}
    assert styles_of(classify) == {
        "classify": "state",
        "prompt": "kind.prompt",
        "→ ": "secondary",
        "plan": "state",
        "review": "state",
    }
    assert styles_of(plan)["/to-spec"] == "command"
    assert styles_of(review)["gate"] == "kind.gate"
    assert styles_of(done)["terminal"] == "kind.terminal"


# one State


def test_one_state_is_its_row_under_the_header_with_the_columns_it_fills():
    workflow = parse_workflow(MARKED)

    assert rows(render_state(workflow.state("review"))) == [
        ["STATE", "KIND"],
        ["review", "gate"],
    ]
    assert rows(render_state(workflow.state("plan")))[1] == row_of(
        render_state_list(workflow, width=200), "plan"
    )


def test_one_state_is_shown_whole_however_narrow_the_terminal():
    """Asking for one State is asking for all of it; a terminal wraps the row
    rather than the end of its marks being lost."""
    workflow = parse_workflow(MARKED)

    assert "effort: high" in render_state(workflow.state("plan"))


# the whole Workflow


def test_the_files_own_keys_stand_above_the_state_table():
    workflow = parse_workflow(MARKED)

    shown = render_workflow(workflow, width=200).splitlines()

    assert [cells(line) for line in shown[:4]] == [
        ["name", "marked"],
        ["model", "opus"],
        ["autocompact", "200k"],
        ["answerer.fallback", "sonnet"],
    ]
    assert shown[4] == ""
    assert shown[5:] == render_state_list(workflow, width=200).splitlines()


def test_a_key_is_dim_beside_its_value_and_the_name_is_styled_as_a_workflow():
    name_line = render_workflow(parse_workflow(MARKED), width=200).text.split("\n")[0]

    assert styles_of(name_line) == {"name": "secondary", "marked": "workflow"}


# the library


def test_the_library_is_each_entry_under_a_header_with_its_problem_beside_it():
    shown = render_library([("alpha", None), ("broken", "broken link: points at nowhere")])

    assert rows(shown) == [
        ["WORKFLOW", "PROBLEM"],
        ["alpha", ABSENT],
        ["broken", "broken link: points at nowhere"],
    ]


def test_a_problem_is_shown_whole_however_long():
    """The problem is the sentence that says what to fix, and the part a cut
    would lose is that part."""
    problem = "workflow /a/very/long/path/" + "x" * 200 + ".toml: unknown key 'modle'"

    shown = render_library([("broken", problem)])

    assert row_of(shown, "broken")[1] == problem


def test_a_library_with_nothing_wrong_lists_the_names_alone():
    assert rows(render_library([("alpha", None), ("beta", None)])) == [
        ["WORKFLOW"],
        ["alpha"],
        ["beta"],
    ]


def test_a_problem_is_styled_as_a_failure_and_the_name_as_a_workflow():
    line = render_library([("broken", "misfiled")]).text.split("\n")[1]

    assert styles_of(line) == {"broken": "workflow", "misfiled": "severity.fail"}
