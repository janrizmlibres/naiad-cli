"""Editing a Workflow's States in its file: the operations behind `naiad state`.

Each is applied through the one write seam, so what is asserted is what an
author's file holds afterwards: the States in their declared order, only the
keys that were given, the author's comments where they were, and a file the
loader still accepts. A refusal is asserted to leave the file byte for byte as
it was.
"""

import tomllib

import pytest

from naiad.domain.workflow import WorkflowError, load_workflow
from naiad.runtime.state_file import (
    add_state,
    move_state,
    remove_state,
    rename_state,
    set_next,
    set_prompt,
    set_state_key,
    unset_state_key,
)
from naiad.runtime.workflow_file import edit_workflow

COMMENTED = """\
# Kept: the author's header.
name = "demo"

[[states]]
name = "plan"   # trailing comment on a key
prompt = "/to-spec {task}"
next = ["build", "done"]

# Between States: kept.
[[states]]
name = "build"
prompt = "/implement {task}"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def workflow(tmp_path):
    path = tmp_path / "demo.toml"
    path.write_text(COMMENTED)
    return path


def edited(path, operation, *arguments, **keywords):
    return edit_workflow(path, lambda document: operation(document, *arguments, **keywords))


def names(path):
    return [state.name for state in load_workflow(path).states]


def raw_states(path):
    return tomllib.loads(path.read_text())["states"]


def refused(path, operation, *arguments, **keywords):
    """The refusal an edit meets, having left the file exactly as it was."""
    before = path.read_bytes()
    with pytest.raises(WorkflowError) as error:
        edited(path, operation, *arguments, **keywords)
    assert path.read_bytes() == before
    return str(error.value)


# --- add ---------------------------------------------------------------------


def test_add_lands_before_the_first_terminal_state_by_default(workflow):
    edited(workflow, add_state, "review", prompt="/review")

    assert names(workflow) == ["plan", "build", "review", "done"]


def test_add_after_and_before_place_it_beside_the_state_named(workflow):
    edited(workflow, add_state, "first", prompt="p", before="plan")
    edited(workflow, add_state, "second", prompt="p", after="plan")

    assert names(workflow) == ["first", "plan", "second", "build", "done"]


def test_a_terminal_state_lands_at_the_end(workflow):
    edited(workflow, add_state, "abandoned", terminal=True)

    assert names(workflow) == ["plan", "build", "done", "abandoned"]
    assert load_workflow(workflow).state("abandoned").prompt is None


def test_add_writes_the_keys_it_was_given_and_no_others(workflow):
    edited(workflow, add_state, "bare", prompt="say hi")

    assert raw_states(workflow)[2] == {"name": "bare", "prompt": "say hi"}


def test_add_writes_each_key_it_is_given(workflow):
    edited(
        workflow,
        add_state,
        "full",
        prompt="go",
        clear=True,
        model="opus",
        effort="high",
        questions="answerer",
        successors=("done", "build"),
    )

    assert raw_states(workflow)[2] == {
        "name": "full",
        "model": "opus",
        "effort": "high",
        "clear": True,
        "questions": "answerer",
        "next": ["done", "build"],
        "prompt": "go",
    }


def test_add_with_no_prompt_is_a_gate(workflow):
    edited(workflow, add_state, "review")

    assert load_workflow(workflow).state("review").is_gate_state


def test_add_keeps_every_comment_where_it_was(workflow):
    edited(workflow, add_state, "review", prompt="/review")

    text = workflow.read_text()
    for kept in ("# Kept: the author's header.", "# trailing comment on a key", "# Between States: kept."):
        assert kept in text


def test_a_state_added_is_set_apart_from_its_neighbours_by_a_blank_line(workflow):
    edited(workflow, add_state, "review", prompt="/review")
    edited(workflow, add_state, "end", terminal=True)

    lines = workflow.read_text().splitlines()
    for at, line in enumerate(lines):
        if line == "[[states]]" and at:
            assert lines[at - 1] == "" or lines[at - 1].startswith("#"), lines[at - 2 : at + 1]


def test_a_prompt_of_several_lines_is_written_as_a_multi_line_string(workflow):
    prompt = 'Line one.\n\n  Indented "quoted" \\ backslash and """triple""" quotes.\nLast.\n'

    edited(workflow, add_state, "long", prompt=prompt)

    assert 'prompt = """\nLine one.' in workflow.read_text()
    assert load_workflow(workflow).state("long").prompt == prompt


def test_a_prompt_of_one_line_stays_on_one_line(workflow):
    edited(workflow, add_state, "short", prompt="Just this.")

    assert 'prompt = "Just this."' in workflow.read_text()


def test_add_refuses_a_name_that_is_taken(workflow):
    assert "'build' already" in refused(workflow, add_state, "build", prompt="p")


def test_add_refuses_a_place_beside_a_state_that_is_not_there(workflow):
    message = refused(workflow, add_state, "x", prompt="p", after="nowhere")

    assert "no State 'nowhere'" in message
    assert "plan, build, done" in message


# --- set and unset -----------------------------------------------------------


def test_set_writes_a_key_the_state_lacks_before_the_trivia_that_follows_it(workflow):
    edited(workflow, set_state_key, "plan", "model", "opus")

    assert load_workflow(workflow).state("plan").model == "opus"
    assert 'model = "opus"\n\n# Between States: kept.\n[[states]]' in workflow.read_text()


def test_set_changes_a_key_where_it_stands(workflow):
    edited(workflow, set_state_key, "plan", "model", "opus")
    edited(workflow, set_state_key, "plan", "model", "sonnet")

    assert raw_states(workflow)[0]["model"] == "sonnet"


def test_set_writes_a_flag_as_a_boolean(workflow):
    edited(workflow, set_state_key, "plan", "clear", True)

    assert raw_states(workflow)[0]["clear"] is True


def test_set_keeps_the_comments(workflow):
    edited(workflow, set_state_key, "plan", "effort", "high")

    assert "# trailing comment on a key" in workflow.read_text()


def test_unset_deletes_the_key_and_says_there_was_one(workflow):
    edited(workflow, set_state_key, "plan", "model", "opus")
    removed = []

    edit_workflow(workflow, lambda d: removed.append(unset_state_key(d, "plan", "model")))

    assert removed == [True]
    assert "model" not in raw_states(workflow)[0]


def test_unset_of_a_key_that_is_absent_says_so(workflow):
    removed = []

    edit_workflow(workflow, lambda d: removed.append(unset_state_key(d, "plan", "effort")))

    assert removed == [False]


def test_a_state_that_is_not_there_is_refused_listing_the_states(workflow):
    message = refused(workflow, set_state_key, "nowhere", "model", "opus")

    assert "no State 'nowhere'" in message
    assert "plan, build, done" in message


def test_unsetting_the_last_terminal_is_refused(workflow):
    assert "no terminal state" in refused(workflow, unset_state_key, "done", "terminal")


def test_setting_the_last_terminal_false_is_refused(workflow):
    assert "no terminal state" in refused(workflow, set_state_key, "done", "terminal", False)


def test_a_second_terminal_can_stand_in_for_the_first(workflow):
    edited(workflow, set_state_key, "build", "terminal", True)

    edited(workflow, unset_state_key, "done", "terminal")

    assert [state.terminal for state in load_workflow(workflow).states] == [False, True, False]


def test_report_on_a_gate_is_refused_by_the_loader(workflow):
    edited(workflow, add_state, "review")

    assert "Gate State" in refused(workflow, set_state_key, "review", "report", True)


# --- set-prompt --------------------------------------------------------------


def test_set_prompt_replaces_the_prompt_and_nothing_else(workflow):
    edited(workflow, set_prompt, "plan", "/grill {task}")

    plan = raw_states(workflow)[0]
    assert plan == {"name": "plan", "prompt": "/grill {task}", "next": ["build", "done"]}
    assert "# trailing comment on a key" in workflow.read_text()


def test_set_prompt_writes_several_lines_as_a_multi_line_string(workflow):
    edited(workflow, set_prompt, "build", "First.\n\nSecond.\n")

    assert 'prompt = """\nFirst.\n\nSecond.\n"""' in workflow.read_text()
    assert load_workflow(workflow).state("build").prompt == "First.\n\nSecond.\n"


def test_set_prompt_gives_a_gate_a_prompt(workflow):
    edited(workflow, add_state, "review")

    edited(workflow, set_prompt, "review", "Look it over.")

    assert load_workflow(workflow).state("review").prompt == "Look it over."


# --- rename ------------------------------------------------------------------


def test_rename_rewrites_every_edge_that_names_the_state(workflow):
    edited(workflow, rename_state, "build", "make")

    assert names(workflow) == ["plan", "make", "done"]
    assert load_workflow(workflow).state("plan").next_candidates == ("make", "done")


def test_rename_keeps_the_comments_and_the_order_of_the_edge(workflow):
    edited(workflow, rename_state, "done", "finished")

    assert 'next = ["build", "finished"]' in workflow.read_text()
    assert "# Between States: kept." in workflow.read_text()


def test_rename_refuses_a_name_that_is_taken(workflow):
    assert "'build' already" in refused(workflow, rename_state, "plan", "build")


def test_rename_refuses_a_state_that_is_not_there(workflow):
    assert "no State 'nowhere'" in refused(workflow, rename_state, "nowhere", "x")


# --- rm ----------------------------------------------------------------------


def test_rm_removes_a_state_nothing_names(workflow):
    edited(workflow, add_state, "spare", prompt="p")

    edited(workflow, remove_state, "spare")

    assert names(workflow) == ["plan", "build", "done"]


def test_rm_refuses_while_another_state_names_it_naming_those_states(workflow):
    edited(workflow, set_next, "build", ["done"])
    message = refused(workflow, remove_state, "done")

    assert "'done'" in message
    assert "plan" in message
    assert "build" in message


def test_rm_of_the_last_terminal_state_is_refused(workflow):
    edited(workflow, set_next, "plan", [])

    assert "no terminal state" in refused(workflow, remove_state, "done")


def test_rm_refuses_a_state_that_is_not_there(workflow):
    assert "no State 'nowhere'" in refused(workflow, remove_state, "nowhere")


# --- move --------------------------------------------------------------------


def test_move_after_and_before_reorder_the_declared_states(workflow):
    edited(workflow, move_state, "done", before="plan")
    edited(workflow, move_state, "plan", after="build")

    assert names(workflow) == ["done", "build", "plan"]


def test_move_keeps_every_key_and_comment_the_state_carried(workflow):
    edited(workflow, move_state, "plan", after="build")

    text = workflow.read_text()
    assert load_workflow(workflow).state("plan").next_candidates == ("build", "done")
    assert "# trailing comment on a key" in text
    assert "# Between States: kept." in text


def test_move_leaves_a_blank_line_between_states(workflow):
    edited(workflow, move_state, "done", before="plan")

    lines = workflow.read_text().splitlines()
    for at, line in enumerate(lines):
        if line == "[[states]]" and lines[at - 1].startswith("name"):
            pytest.fail(f"no separation before line {at + 1}")


def test_move_refuses_to_place_a_state_beside_itself(workflow):
    assert "itself" in refused(workflow, move_state, "plan", after="plan")


def test_move_refuses_a_state_that_is_not_there(workflow):
    assert "no State 'nowhere'" in refused(workflow, move_state, "plan", after="nowhere")
    assert "no State 'nowhere'" in refused(workflow, move_state, "nowhere", after="plan")


# --- next --------------------------------------------------------------------


def test_next_replaces_the_successors(workflow):
    edited(workflow, set_next, "plan", ["done"])

    assert load_workflow(workflow).state("plan").next_candidates == ("done",)


def test_next_gives_a_state_with_none_a_list(workflow):
    edited(workflow, set_next, "build", ["plan", "done"])

    assert load_workflow(workflow).state("build").next_candidates == ("plan", "done")


def test_no_successors_deletes_the_key(workflow):
    edited(workflow, set_next, "plan", [])

    assert "next" not in raw_states(workflow)[0]


def test_next_refuses_a_successor_the_workflow_lacks(workflow):
    assert "unknown successor 'nowhere'" in refused(workflow, set_next, "plan", ["nowhere"])
