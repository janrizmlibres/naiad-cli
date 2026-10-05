"""`naiad state`, as an author meets it: what a scripted session leaves in the
file, and how each verb fails.

How each edit treats the document is asserted in tests/test_state_file.py and
how a rendered line reads in tests/test_listing.py; asserted here is which
words reach the author and what stays on disk when a verb refuses.
"""

import io
import stat
import tomllib

import pytest

from fake_terminal import ESCAPE, styles_of, to_terminal
from naiad.cli.main import main
from naiad.domain.workflow import load_workflow

PLAN_PROMPT = "/to-spec {task}\n\nWrite the spec, then announce build.\n"


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    return tmp_path / "naiad"


@pytest.fixture
def library(home):
    return home / "workflows"


@pytest.fixture
def demo(library):
    """A Workflow that is only a terminal `done`, as `workflow new` leaves it."""
    assert main(["workflow", "new", "demo"]) == 0
    return library / "demo.toml"


@pytest.fixture
def run(capsys):
    def run(*argv):
        capsys.readouterr()
        code = main(list(argv))
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return run


def names(path):
    return [state.name for state in load_workflow(path).states]


def raw_states(path):
    return tomllib.loads(path.read_text())["states"]


def fake_editor(tmp_path, monkeypatch, body):
    script = tmp_path / "fake-editor"
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("EDITOR", str(script))
    return script


def refused(run, path, *argv):
    """The words a verb refuses in, having left the file exactly as it was."""
    before = path.read_bytes()
    code, out, err = run(*argv)
    assert code == 2, (out, err)
    assert path.read_bytes() == before
    return err


# --- the scripted session ----------------------------------------------------


def test_a_scripted_session_builds_a_workflow_that_checks(demo, run, tmp_path, monkeypatch):
    prompt_file = tmp_path / "plan.md"
    prompt_file.write_text(PLAN_PROMPT)
    fake_editor(tmp_path, monkeypatch, "printf 'Build it.\\n' > \"$1\"")

    assert run("state", "add", "demo", "plan", "--from", str(prompt_file), "--clear")[0] == 0
    assert run("state", "add", "demo", "review", "--gate")[0] == 0
    assert run("state", "add", "demo", "build")[0] == 0
    assert run("state", "add", "demo", "verify", "--prompt", "/verify {task}")[0] == 0
    assert run("state", "next", "demo", "review", "build", "done")[0] == 0
    assert run("workflow", "check", "demo")[0] == 0

    workflow = load_workflow(demo)
    assert [state.name for state in workflow.states] == ["plan", "review", "build", "verify", "done"]
    assert workflow.state("plan").prompt == PLAN_PROMPT
    assert workflow.state("plan").clear
    assert workflow.state("review").is_gate_state
    assert workflow.state("review").next_candidates == ("build", "done")
    assert workflow.state("build").prompt == "Build it."
    assert workflow.state("verify").prompt == "/verify {task}"


# --- list and show -----------------------------------------------------------


def test_list_prints_the_states_the_workflow_show_prints(demo, run):
    run("state", "add", "demo", "plan", "--prompt", "/to-spec {task}", "--clear")

    _, listed, _ = run("state", "list", "demo")
    _, shown, _ = run("workflow", "show", "demo")

    assert shown.endswith(listed)
    assert listed.splitlines()[0].split()[0] == "STATE"
    assert "plan" in listed and "clears" in listed


def test_show_prints_the_states_row_then_its_prompt_in_full(demo, run):
    run("state", "add", "demo", "plan", "--prompt", "Line one.\nLine two.")

    code, out, _ = run("state", "show", "demo", "plan")

    assert code == 0
    assert [line.split() for line in out.splitlines()[:3]] == [
        ["STATE", "KIND", "MARKS"],
        ["plan", "prompt", "questions:", "human"],
        [],
    ]
    assert out.endswith("\n\nLine one.\nLine two.\n")


def test_show_prints_the_prompt_exactly_as_the_author_wrote_it(demo, run, monkeypatch):
    """Prose the author wrote, read back to them: a tab stays a tab, and words
    in brackets are words, at a terminal too."""
    prompt = "Indented\twith a tab.\n  [bold]not markup[/bold]"
    run("state", "add", "demo", "plan", "--prompt", prompt)
    terminal = to_terminal(monkeypatch)

    assert main(["state", "show", "demo", "plan"]) == 0

    assert terminal.getvalue().endswith(f"\n\n{prompt}\n")
    assert ESCAPE in terminal.getvalue().split("\n\n")[0]


def test_a_gate_shows_its_row_and_no_prompt(demo, run):
    run("state", "add", "demo", "review", "--gate")

    _, out, _ = run("state", "show", "demo", "review")

    assert [line.split() for line in out.splitlines()] == [["STATE", "KIND"], ["review", "gate"]]


def test_show_of_a_state_that_is_not_there_names_the_states(demo, run):
    err = refused(run, demo, "state", "show", "demo", "nowhere")

    assert "no State 'nowhere'" in err and "done" in err


def test_a_verb_names_the_workflow_by_path_too(tmp_path, run):
    path = tmp_path / "loose.toml"
    path.write_text('name = "loose"\n\n[[states]]\nname = "done"\nterminal = true\n')

    assert run("state", "add", str(path), "plan", "--gate")[0] == 0

    assert names(path) == ["plan", "done"]


# --- add ---------------------------------------------------------------------


def test_add_lands_before_done_by_default(demo, run):
    code, out, _ = run("state", "add", "demo", "plan", "--gate")

    assert code == 0
    assert names(demo) == ["plan", "done"]
    assert "plan" in out


def test_add_honours_after_before_and_terminal(demo, run):
    run("state", "add", "demo", "a", "--gate")
    run("state", "add", "demo", "c", "--gate", "--after", "a")
    run("state", "add", "demo", "b", "--gate", "--before", "c")
    run("state", "add", "demo", "gone", "--terminal")

    assert names(demo) == ["a", "b", "c", "done", "gone"]
    assert load_workflow(demo).state("gone").terminal


def test_add_writes_only_the_keys_it_was_given(demo, run):
    run("state", "add", "demo", "plan", "--prompt", "go")

    assert raw_states(demo)[0] == {"name": "plan", "prompt": "go"}


def test_add_writes_each_key_flag(demo, run):
    run(
        "state", "add", "demo", "plan", "--prompt", "go", "--clear", "--model", "opus",
        "--effort", "high", "--next", "done", "--next", "plan", "--auto",
    )

    assert raw_states(demo)[0] == {
        "name": "plan",
        "model": "opus",
        "effort": "high",
        "clear": True,
        "questions": "answerer",
        "next": ["done", "plan"],
        "prompt": "go",
    }


def test_there_is_no_flag_to_hand_questions_to_the_human(demo, run):
    with pytest.raises(SystemExit):
        run("state", "add", "demo", "plan", "--questions", "human")


def test_the_prompt_sources_are_mutually_exclusive(demo, run):
    with pytest.raises(SystemExit):
        run("state", "add", "demo", "plan", "--prompt", "a", "--gate")


def test_add_takes_the_prompt_from_standard_input(demo, run, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("From a pipe.\nSecond line.\n"))

    assert run("state", "add", "demo", "plan", "--from", "-")[0] == 0

    assert load_workflow(demo).state("plan").prompt == "From a pipe.\nSecond line.\n"


def test_add_takes_the_prompt_from_the_editor(demo, run, tmp_path, monkeypatch):
    fake_editor(tmp_path, monkeypatch, "printf 'Typed in the editor.\\n' > \"$1\"")

    assert run("state", "add", "demo", "plan")[0] == 0

    assert load_workflow(demo).state("plan").prompt == "Typed in the editor."


def test_add_with_no_editor_refuses_in_one_sentence_naming_both_remedies(demo, run):
    err = refused(run, demo, "state", "add", "demo", "plan")

    assert "$VISUAL" in err and "$EDITOR" in err and "--from" in err
    assert len(err.strip().splitlines()) == 1


def test_an_empty_editor_buffer_changes_nothing_and_says_so(demo, run, tmp_path, monkeypatch):
    fake_editor(tmp_path, monkeypatch, ": > \"$1\"")
    before = demo.read_bytes()

    code, out, _ = run("state", "add", "demo", "plan")

    assert code == 0
    assert "nothing" in out
    assert demo.read_bytes() == before


def test_an_empty_prompt_file_changes_nothing_either(demo, run, tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("\n")
    before = demo.read_bytes()

    code, out, _ = run("state", "add", "demo", "plan", "--from", str(empty))

    assert code == 0 and "nothing" in out
    assert demo.read_bytes() == before


def test_add_refuses_a_prompt_file_that_cannot_be_read(demo, run, tmp_path):
    err = refused(run, demo, "state", "add", "demo", "plan", "--from", str(tmp_path / "missing.md"))

    assert "missing.md" in err


def test_add_refuses_a_name_that_is_taken_before_opening_the_editor(demo, run, tmp_path, monkeypatch):
    marker = tmp_path / "opened"
    fake_editor(tmp_path, monkeypatch, f"touch {marker}")

    err = refused(run, demo, "state", "add", "demo", "done")

    assert "'done' already" in err
    assert not marker.exists()


def test_add_refuses_a_place_beside_a_state_that_is_not_there(demo, run):
    err = refused(run, demo, "state", "add", "demo", "plan", "--gate", "--after", "nowhere")

    assert "no State 'nowhere'" in err


@pytest.mark.parametrize("flag", ["--model", "--effort"])
def test_add_checks_a_model_and_effort_as_set_does_before_writing(demo, run, flag):
    err = refused(run, demo, "state", "add", "demo", "plan", "--gate", flag, " ")

    assert "naiad state unset" in err


def test_a_terminal_state_takes_no_prompt(demo, run):
    err = refused(run, demo, "state", "add", "demo", "end", "--terminal", "--prompt", "hi")

    assert "terminal" in err and "Prompt" in err


# --- set-prompt --------------------------------------------------------------


def test_set_prompt_takes_the_same_sources(demo, run, tmp_path, monkeypatch):
    run("state", "add", "demo", "plan", "--prompt", "old")
    prompt_file = tmp_path / "new.md"
    prompt_file.write_text("From a file.\nTwo lines.\n")

    assert run("state", "set-prompt", "demo", "plan", "--from", str(prompt_file))[0] == 0
    assert load_workflow(demo).state("plan").prompt == "From a file.\nTwo lines.\n"
    assert 'prompt = """\nFrom a file.' in demo.read_text()

    assert run("state", "set-prompt", "demo", "plan", "--prompt", "Inline.")[0] == 0
    assert load_workflow(demo).state("plan").prompt == "Inline."


def test_set_prompt_opens_the_editor_on_the_current_prompt(demo, run, tmp_path, monkeypatch):
    run("state", "add", "demo", "plan", "--prompt", "Current prompt.")
    fake_editor(tmp_path, monkeypatch, f"cp \"$1\" {tmp_path}/seen; echo 'Edited.' > \"$1\"")

    assert run("state", "set-prompt", "demo", "plan")[0] == 0

    assert (tmp_path / "seen").read_text() == "Current prompt.\n"
    assert load_workflow(demo).state("plan").prompt == "Edited."


def test_set_prompt_with_no_editor_refuses(demo, run):
    run("state", "add", "demo", "plan", "--prompt", "old")

    err = refused(run, demo, "state", "set-prompt", "demo", "plan")

    assert "$EDITOR" in err


def test_set_prompt_with_an_empty_buffer_keeps_the_prompt(demo, run, tmp_path, monkeypatch):
    run("state", "add", "demo", "plan", "--prompt", "keep me")
    fake_editor(tmp_path, monkeypatch, ": > \"$1\"")
    before = demo.read_bytes()

    code, out, _ = run("state", "set-prompt", "demo", "plan")

    assert code == 0 and "nothing" in out
    assert demo.read_bytes() == before


# --- set and unset -----------------------------------------------------------


def test_set_and_unset_reach_every_state_key(demo, run):
    run("state", "add", "demo", "plan", "--prompt", "go")
    values = {
        "model": "opus",
        "effort": "high",
        "clear": True,
        "terminal": False,
        "questions": "human",
        "report": True,
    }

    for key, value in values.items():
        assert run("state", "set", "demo", "plan", key, str(value).lower())[0] == 0
    assert {k: v for k, v in raw_states(demo)[0].items() if k in values} == values

    for key in values:
        assert run("state", "unset", "demo", "plan", key)[0] == 0
    assert raw_states(demo)[0] == {"name": "plan", "prompt": "go"}


@pytest.mark.parametrize(
    ("key", "verb"),
    [("name", "rename"), ("prompt", "set-prompt"), ("next", "next")],
)
def test_set_refuses_a_key_a_verb_owns_naming_the_verb(demo, run, key, verb):
    assert verb in refused(run, demo, "state", "set", "demo", "done", key, "x")


def test_set_refuses_a_value_the_key_does_not_take_before_writing(demo, run):
    assert "true|false" in refused(run, demo, "state", "set", "demo", "done", "clear", "maybe")


def test_unsetting_the_last_terminal_is_refused(demo, run):
    assert "no terminal state" in refused(run, demo, "state", "unset", "demo", "done", "terminal")


def test_unset_says_when_the_key_was_not_set(demo, run):
    code, out, _ = run("state", "unset", "demo", "done", "model")

    assert code == 0 and "was not set" in out


def test_set_and_unset_help_print_the_key_table(run, capsys):
    for verb in ("set", "unset"):
        with pytest.raises(SystemExit):
            main(["state", verb, "--help"])
        printed = capsys.readouterr().out
        assert "questions" in printed and "answerer|human" in printed
        assert "true|false" in printed


# --- rename, rm, move --------------------------------------------------------


def test_rename_rewrites_every_next_edge_that_names_the_state(demo, run):
    run("state", "add", "demo", "build", "--gate")
    run("state", "add", "demo", "plan", "--gate", "--next", "build", "--next", "done", "--before", "build")

    assert run("state", "rename", "demo", "build", "make")[0] == 0

    assert names(demo) == ["plan", "make", "done"]
    assert load_workflow(demo).state("plan").next_candidates == ("make", "done")


def test_rm_refuses_while_a_state_names_it_naming_those_states(demo, run):
    run("state", "add", "demo", "build", "--gate")
    run("state", "add", "demo", "plan", "--gate", "--next", "build", "--next", "done")
    run("state", "add", "demo", "other", "--gate", "--next", "build")

    err = refused(run, demo, "state", "rm", "demo", "build")

    assert "plan" in err and "other" in err


def test_rm_removes_a_state_nothing_names(demo, run):
    run("state", "add", "demo", "plan", "--gate")

    assert run("state", "rm", "demo", "plan")[0] == 0

    assert names(demo) == ["done"]


def test_rm_of_the_last_terminal_state_is_refused(demo, run):
    run("state", "add", "demo", "plan", "--gate")

    assert "no terminal state" in refused(run, demo, "state", "rm", "demo", "done")


def test_move_reorders_the_states(demo, run):
    for name in ("a", "b", "c"):
        run("state", "add", "demo", name, "--gate")

    assert run("state", "move", "demo", "c", "--before", "a")[0] == 0
    assert run("state", "move", "demo", "a", "--after", "b")[0] == 0

    assert names(demo) == ["c", "b", "a", "done"]


def test_move_needs_a_place(demo, run):
    run("state", "add", "demo", "a", "--gate")

    with pytest.raises(SystemExit):
        run("state", "move", "demo", "a")


# --- next --------------------------------------------------------------------


def test_next_replaces_the_successors_and_none_clears_them(demo, run):
    run("state", "add", "demo", "plan", "--gate")

    assert run("state", "next", "demo", "plan", "done", "plan")[0] == 0
    assert load_workflow(demo).state("plan").next_candidates == ("done", "plan")

    assert run("state", "next", "demo", "plan", "--none")[0] == 0
    assert load_workflow(demo).state("plan").next_candidates == ()
    assert "next" not in raw_states(demo)[0]


def test_next_refuses_none_together_with_states(demo, run):
    run("state", "add", "demo", "plan", "--gate")

    err = refused(run, demo, "state", "next", "demo", "plan", "done", "--none")

    assert "--none" in err


def test_next_with_no_arguments_and_no_terminal_refuses_naming_the_list_form(demo, run):
    run("state", "add", "demo", "plan", "--gate")

    err = refused(run, demo, "state", "next", "demo", "plan")

    assert "terminal" in err
    assert "naiad state next demo plan" in err


def test_next_with_no_arguments_opens_a_numbered_picker_in_a_terminal(demo, run, monkeypatch):
    run("state", "add", "demo", "plan", "--gate", "--next", "done")
    run("state", "add", "demo", "build", "--gate")
    monkeypatch.setattr("sys.stdin", _Terminal())
    monkeypatch.setattr("sys.stdout", _Terminal())
    answers = iter(["2 3"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    code = main(["state", "next", "demo", "plan"])

    assert code == 0
    assert load_workflow(demo).state("plan").next_candidates == ("build", "done")


# --- what a verb says --------------------------------------------------------


@pytest.fixture
def said(monkeypatch):
    """Every line a verb says, as it said it."""
    lines = []
    monkeypatch.setattr("naiad.cli.state.say", lambda line, **_: lines.append(line))
    return lines


def test_each_verb_says_what_it_did_with_the_workflow_and_states_it_names_styled(
    demo, run, said
):
    """The words are what they were, for a script reading them; at a terminal
    the Workflow and the States stand out from what was done to them."""
    run("state", "add", "demo", "plan", "--prompt", "Plan it.")
    run("state", "add", "demo", "build", "--prompt", "Build it.")
    run("state", "set", "demo", "plan", "effort", "high")
    run("state", "unset", "demo", "plan", "effort")
    run("state", "rename", "demo", "plan", "draft")
    run("state", "move", "demo", "build", "--before", "draft")
    run("state", "next", "demo", "draft", "build", "done")
    run("state", "set-prompt", "demo", "draft", "--prompt", "Draft it.")
    run("state", "next", "demo", "draft", "--none")
    run("state", "rm", "demo", "build")

    assert said == [
        "demo: added plan at position 1",
        "demo: added build at position 2",
        "demo/plan: effort = high",
        "demo/plan: effort removed",
        "demo: renamed plan to draft",
        "demo: moved build to position 1",
        "demo/draft: next = build, done",
        "demo/draft: Prompt replaced",
        "demo/draft: next = none",
        "demo: removed build",
    ]
    assert [styles_of(line) for line in said] == [
        {"demo": "workflow", "plan": "state"},
        {"demo": "workflow", "build": "state"},
        {"demo": "workflow", "plan": "state"},
        {"demo": "workflow", "plan": "state"},
        {"demo": "workflow", "plan": "state", "draft": "state"},
        {"demo": "workflow", "build": "state"},
        {"demo": "workflow", "draft": "state", "build": "state", "done": "state"},
        {"demo": "workflow", "draft": "state"},
        {"demo": "workflow", "draft": "state"},
        {"demo": "workflow", "build": "state"},
    ]


def test_a_verb_that_changed_nothing_says_so_with_its_names_styled(
    demo, run, said, tmp_path
):
    empty = tmp_path / "empty.md"
    empty.write_text("")

    run("state", "add", "demo", "plan", "--from", str(empty))

    assert said == ["the Prompt is empty, so nothing was added to demo"]
    assert styles_of(said[0]) == {"demo": "workflow"}


def test_next_of_a_successor_the_workflow_lacks_is_refused(demo, run):
    run("state", "add", "demo", "plan", "--gate")

    assert "unknown successor 'nowhere'" in refused(run, demo, "state", "next", "demo", "plan", "nowhere")


class _Terminal(io.StringIO):
    def isatty(self):
        return True
