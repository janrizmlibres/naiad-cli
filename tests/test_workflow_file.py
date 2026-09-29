"""Writing a Workflow file the way an author's own edits are written: through
the one seam every writing verb shares (ADR 0049).

What is asserted is the contract that keeps a file the author's to hand-edit:
comments survive a write, a write the loader rejects changes nothing, a
symlinked library entry is written through, and a file that loads after the
write is the only outcome a caller ever sees.
"""

import pytest

from naiad.domain.workflow import WorkflowError
from naiad.runtime import workflow_file
from naiad.runtime.workflow_file import edit_workflow, scaffold_workflow

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
