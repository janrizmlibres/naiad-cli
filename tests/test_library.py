"""The Workflow library: a bare name resolves to a library file at the
entrance (ADR 0023).

What is asserted here is the resolution rule itself — shape decides name or
path, a name is a stem in the library, and the two refusals that guard it.
That the entrances actually route through it is asserted where each entrance
is tested (tests/test_queue_command.py, tests/test_run_command.py,
tests/test_batch.py).
"""

from pathlib import Path

import pytest

from naiad.cli.library import LibraryError, resolve_workflow

WORKFLOW = """
name = "matt-pocock"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "workflows"
    path.mkdir()
    return path


def test_an_argument_with_a_path_separator_is_a_path_never_a_name(library, tmp_path):
    given = tmp_path / "elsewhere" / "matt-pocock.toml"
    resolved = resolve_workflow(str(given), library=library)
    assert resolved == given


def test_an_argument_ending_in_toml_is_a_path_even_with_no_separator(library, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    resolved = resolve_workflow("matt-pocock.toml", library=library)
    assert resolved == tmp_path / "matt-pocock.toml"


def test_a_bare_name_resolves_to_the_library_file_of_that_stem(library):
    (library / "matt-pocock.toml").write_text(WORKFLOW)
    resolved = resolve_workflow("matt-pocock", library=library)
    assert resolved == library / "matt-pocock.toml"


def test_a_name_the_library_does_not_hold_is_refused_with_what_it_does(library):
    (library / "matt-pocock.toml").write_text(WORKFLOW)
    (library / "acme-hotfix.toml").write_text(WORKFLOW.replace("matt-pocock", "acme-hotfix"))
    with pytest.raises(LibraryError) as refused:
        resolve_workflow("matt-pocok", library=library)
    message = str(refused.value)
    assert "matt-pocok" in message
    assert "acme-hotfix, matt-pocock" in message
    assert str(library) in message


def test_a_missing_or_empty_library_says_where_to_put_files(library):
    for where in (library, library / "nowhere"):
        with pytest.raises(LibraryError) as refused:
            resolve_workflow("matt-pocock", library=where)
        message = str(refused.value)
        assert "holds no workflows" in message
        assert str(where) in message


def test_a_library_file_declaring_a_name_other_than_its_stem_is_refused(library):
    (library / "experiment.toml").write_text(WORKFLOW)
    with pytest.raises(LibraryError) as refused:
        resolve_workflow("experiment", library=library)
    message = str(refused.value)
    assert "experiment" in message
    assert "matt-pocock" in message


def test_a_workflow_reached_by_path_may_call_itself_anything(library, tmp_path):
    """The coherence rule binds only the library, where the filename has
    become an address; an explicit path keeps today's freedom."""
    given = tmp_path / "experiment.toml"
    given.write_text(WORKFLOW)
    assert resolve_workflow(str(given), library=library) == given


def test_a_stray_local_file_never_shadows_the_library(library, monkeypatch, tmp_path):
    """Disk state around the operator does not participate: a bare name is a
    name even when a file of that exact name sits in the working directory."""
    (library / "matt-pocock.toml").write_text(WORKFLOW)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "matt-pocock").write_text(WORKFLOW)
    resolved = resolve_workflow("matt-pocock", library=library)
    assert resolved == library / "matt-pocock.toml"


def test_a_link_that_points_at_nothing_is_named_as_broken_not_as_missing(library, tmp_path):
    """The library holds the name, so 'no workflow named' would send the
    operator looking for a file they made. What is wrong is where it leads."""
    (library / "feature.toml").symlink_to(tmp_path / "gone" / "feature.toml")

    with pytest.raises(LibraryError) as refused:
        resolve_workflow("feature", library=library)

    message = str(refused.value)
    assert "broken" in message
    assert str(library / "feature.toml") in message
    assert str(tmp_path / "gone" / "feature.toml") in message
    assert "no workflow named" not in message
