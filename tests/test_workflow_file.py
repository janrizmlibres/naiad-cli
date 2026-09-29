"""Writing a Workflow file the way an author's own edits are written: through
the one seam every writing verb shares.

What is asserted is the contract that keeps a file the author's to hand-edit:
comments survive a write, a write the loader rejects changes nothing, a
symlinked library entry is written through, and a file that loads after the
write is the only outcome a caller ever sees.
"""

import os

import pytest

from naiad.domain.workflow import WorkflowError
from naiad.runtime import workflow_file
from naiad.runtime.workflow_file import (
    copy_workflow,
    edit_workflow,
    scaffold_workflow,
    set_file_key,
    unset_file_key,
)

COMMENTED = """\
# Hand-written header: kept.
#
# model = "opus"   # a choice left commented out

name = "demo"

[[states]]
name = "plan"   # trailing comment on a key
prompt = \"\"\"
Plan {task}.

  Indented line, kept exactly.
\"\"\"

# Between States: kept.
[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def workflow(tmp_path):
    path = tmp_path / "demo.toml"
    path.write_text(COMMENTED)
    return path


def set_effort(document):
    document["states"][0]["effort"] = "high"


def test_an_edit_keeps_every_comment_and_the_layout_around_it(workflow):
    """The point of a comment-preserving writer: the starter's commented header
    must still be there after the first write."""
    edit_workflow(workflow, set_effort)

    written = workflow.read_text()
    assert 'effort = "high"\n' in written
    assert written.replace('effort = "high"\n', "", 1) == COMMENTED


def test_the_edited_file_is_returned_as_the_loader_reads_it(workflow):
    loaded = edit_workflow(workflow, set_effort)

    assert loaded.state("plan").effort == "high"


def test_an_edit_the_loader_rejects_leaves_the_file_exactly_as_it_was(workflow):
    def misspell(document):
        document["states"][0]["efort"] = "high"

    with pytest.raises(WorkflowError) as refused:
        edit_workflow(workflow, misspell)

    assert "unknown key 'efort'" in str(refused.value)
    assert workflow.read_bytes() == COMMENTED.encode()


def test_a_failed_reload_puts_the_previous_bytes_back(workflow, monkeypatch):
    """The file was written and then failed to load — the case validation ahead
    of the write cannot rule out — so the write is undone rather than left for
    a Run to trip over."""
    real = workflow_file.load_workflow

    def reload_fails(path):
        if path.read_text() != COMMENTED:
            raise WorkflowError("the reload failed")
        return real(path)

    monkeypatch.setattr(workflow_file, "load_workflow", reload_fails)

    with pytest.raises(WorkflowError, match="the reload failed"):
        edit_workflow(workflow, set_effort)

    assert workflow.read_bytes() == COMMENTED.encode()


def test_a_symlinked_entry_is_written_through_to_its_target(tmp_path):
    """A hand-made link is an entry for a Workflow maintained elsewhere: the
    maintained file is what changes, and the link stays a link."""
    maintained = tmp_path / "checkout" / "demo.toml"
    maintained.parent.mkdir()
    maintained.write_text(COMMENTED)
    library = tmp_path / "workflows"
    library.mkdir()
    entry = library / "demo.toml"
    entry.symlink_to(maintained)

    edit_workflow(entry, set_effort)

    assert entry.is_symlink() and entry.readlink() == maintained
    assert 'effort = "high"' in maintained.read_text()


def test_an_edit_keeps_the_permissions_the_author_gave_the_file(workflow):
    """A temporary file is created private, so without care the first write
    would turn a hand-edited 0644 file into 0600."""
    workflow.chmod(0o644)

    edit_workflow(workflow, set_effort)

    assert workflow.stat().st_mode & 0o777 == 0o644


def test_a_scaffold_is_readable_as_any_file_the_author_makes(tmp_path):
    path = tmp_path / "demo.toml"
    umask = os.umask(0o022)
    try:
        scaffold_workflow(path, "demo")
    finally:
        os.umask(umask)

    assert path.stat().st_mode & 0o777 == 0o644


def test_no_temporary_file_is_left_beside_the_workflow(workflow):
    edit_workflow(workflow, set_effort)

    assert [file.name for file in workflow.parent.iterdir()] == ["demo.toml"]


def test_a_scaffold_is_a_name_and_a_terminal_done(tmp_path):
    path = tmp_path / "library" / "demo.toml"

    loaded = scaffold_workflow(path, "demo")

    assert loaded.name == "demo"
    assert [(state.name, state.terminal) for state in loaded.states] == [("done", True)]
    assert path.is_file()


def test_a_scaffold_never_replaces_a_file_that_is_there(workflow):
    with pytest.raises(FileExistsError):
        scaffold_workflow(workflow, "demo")

    assert workflow.read_text() == COMMENTED


def test_a_scaffold_never_replaces_a_dangling_link(tmp_path):
    entry = tmp_path / "demo.toml"
    entry.symlink_to(tmp_path / "nowhere.toml")

    with pytest.raises(FileExistsError):
        scaffold_workflow(entry, "demo")

    assert entry.is_symlink()


def test_a_new_file_key_lands_beside_the_name_not_after_the_states(workflow):
    edit_workflow(workflow, lambda document: set_file_key(document, "model", "opus"))

    written = workflow.read_text()
    assert written.index('model = "opus"') < written.index("[[states]]")
    assert written.replace('model = "opus"\n', "", 1) == COMMENTED


def test_a_file_key_that_is_there_is_replaced_in_place(workflow):
    workflow.write_text(COMMENTED.replace('name = "demo"\n', 'name = "demo"\nmodel = "opus"\n'))

    edit_workflow(workflow, lambda document: set_file_key(document, "model", "haiku"))

    assert workflow.read_text() == COMMENTED.replace(
        'name = "demo"\n', 'name = "demo"\nmodel = "haiku"\n'
    )


def test_an_answerer_key_makes_the_table_when_there_is_none(workflow):
    loaded = edit_workflow(workflow, lambda d: set_file_key(d, "answerer.fallback", "sonnet"))

    assert loaded.answerer_fallback == "sonnet"
    assert "[answerer]" in workflow.read_text()


def test_unset_deletes_the_key(workflow):
    edit_workflow(workflow, lambda d: set_file_key(d, "effort", "high"))

    loaded = edit_workflow(workflow, lambda d: unset_file_key(d, "effort"))

    assert loaded.effort is None
    assert workflow.read_text() == COMMENTED


def test_unsetting_the_last_answerer_key_keeps_the_table_because_it_is_the_opt_in(workflow):
    """An `[answerer]` table flips the file's default for Questions,
    so emptying it must not switch the Answerer off as a side effect."""
    edit_workflow(workflow, lambda d: set_file_key(d, "answerer.model", "haiku"))

    loaded = edit_workflow(workflow, lambda d: unset_file_key(d, "answerer.model"))

    assert "[answerer]" in workflow.read_text()
    assert loaded.state("plan").questions == "answerer"


def test_unset_of_a_key_that_is_not_there_changes_nothing(workflow):
    edit_workflow(workflow, lambda d: unset_file_key(d, "answerer.model"))

    assert workflow.read_text() == COMMENTED


def test_a_copy_takes_the_new_stem_as_its_name_and_keeps_everything_else(tmp_path, workflow):
    target = tmp_path / "copy.toml"

    copied = copy_workflow(workflow, target, "copy")

    assert copied.name == "copy"
    assert target.read_text() == COMMENTED.replace('name = "demo"', 'name = "copy"')


def test_a_copy_refuses_a_file_that_is_there(tmp_path, workflow):
    target = tmp_path / "copy.toml"
    target.write_text("mine")

    with pytest.raises(FileExistsError):
        copy_workflow(workflow, target, "copy")

    assert target.read_text() == "mine"
