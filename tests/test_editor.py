"""Writing a Prompt in the author's own editor.

The editor is a real program, so it is a fake one here: a script that writes
what it is told into the file it is given, which is all an editor is to Naiad.
"""

import os
import stat

import pytest

from naiad.adapters.editor import EditorError, edit_text


def script(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_the_editor_is_given_a_file_and_what_it_leaves_there_comes_back(tmp_path):
    editor = script(tmp_path, "ed", "printf 'typed\\n' > \"$1\"")

    assert edit_text("", environ={"EDITOR": editor}) == "typed\n"


def test_the_file_opens_holding_the_text_to_edit(tmp_path):
    editor = script(tmp_path, "ed", "cp \"$1\" \"$0.seen\"")

    edit_text("the current Prompt\n", environ={"EDITOR": editor})

    assert (tmp_path / "ed.seen").read_text() == "the current Prompt\n"


def test_visual_is_preferred_to_editor(tmp_path):
    visual = script(tmp_path, "visual", "echo visual > \"$1\"")
    editor = script(tmp_path, "editor", "echo editor > \"$1\"")

    assert edit_text("", environ={"VISUAL": visual, "EDITOR": editor}) == "visual\n"


def test_an_empty_visual_falls_through_to_editor(tmp_path):
    editor = script(tmp_path, "editor", "echo editor > \"$1\"")

    assert edit_text("", environ={"VISUAL": "", "EDITOR": editor}) == "editor\n"


def test_an_editor_with_arguments_is_run_as_typed(tmp_path):
    editor = script(tmp_path, "ed", "echo \"$1\" > \"$2\"")

    assert edit_text("", environ={"EDITOR": f"{editor} --wait"}) == "--wait\n"


def test_no_editor_is_refused_in_one_sentence_naming_both_remedies():
    with pytest.raises(EditorError) as refused:
        edit_text("", environ={})

    message = str(refused.value)
    assert "$VISUAL" in message and "$EDITOR" in message
    assert "--from" in message
    assert "\n" not in message


def test_an_editor_that_fails_is_refused_with_its_status(tmp_path):
    editor = script(tmp_path, "ed", "exit 3")

    with pytest.raises(EditorError) as refused:
        edit_text("", environ={"EDITOR": editor})

    assert "status 3" in str(refused.value)


def test_an_editor_that_is_not_there_is_refused_naming_it(tmp_path):
    with pytest.raises(EditorError) as refused:
        edit_text("", environ={"EDITOR": str(tmp_path / "missing")})

    assert "missing" in str(refused.value)


def test_the_file_is_gone_once_the_editor_has_closed(tmp_path):
    editor = script(tmp_path, "ed", "echo \"$1\" > \"$0.path\"")

    edit_text("", environ={"EDITOR": editor})

    assert not os.path.exists((tmp_path / "ed.path").read_text().strip())


def test_a_blank_editor_is_no_editor():
    with pytest.raises(EditorError):
        edit_text("", environ={"VISUAL": "  ", "EDITOR": ""})
