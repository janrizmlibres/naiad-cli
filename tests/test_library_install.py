"""Linking the shipped Workflow into the library (ADR 0037).

A library entry is an address, so what is pinned here is that install makes one,
that re-running it repairs a wrong one, and that it refuses the case this
decision came from — a regular file in the library, which is a copy and can fall
behind the file it copies.

That the resolution rule itself works is tests/test_library.py's; that the
shipped file is well-formed is tests/test_shipped_workflow.py's.
"""

from pathlib import Path

import pytest

from naiad.cli.library import link_shipped_workflows, resolve_workflow, shipped_workflows

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
    return tmp_path / "home" / "workflows"


@pytest.fixture
def shipped(tmp_path):
    path = tmp_path / "checkout" / "workflows"
    path.mkdir(parents=True)
    (path / "matt-pocock.toml").write_text(WORKFLOW)
    return path


def test_links_into_a_library_that_does_not_exist_yet(library, shipped):
    linked = link_shipped_workflows(library=library, shipped=shipped)

    assert linked == (library / "matt-pocock.toml",)
    assert linked[0].is_symlink()
    assert linked[0].readlink() == shipped / "matt-pocock.toml"


def test_the_link_is_what_a_bare_name_resolves_to(library, shipped):
    """The whole point of the entry: the name opens the file under review.

    A name still resolves to the library entry rather than through it, which is
    the address an Entry stores and a Run record names (ADR 0023). What the
    decision changed is what that address leads to."""
    link_shipped_workflows(library=library, shipped=shipped)

    resolved = resolve_workflow("matt-pocock", library=library)

    assert resolved == library / "matt-pocock.toml"
    assert resolved.resolve() == shipped / "matt-pocock.toml"


def test_an_edit_to_the_maintained_file_is_what_the_name_reads(library, shipped):
    """An address cannot fall behind what it addresses, which is the fault this
    decision removes."""
    link_shipped_workflows(library=library, shipped=shipped)

    (shipped / "matt-pocock.toml").write_text(WORKFLOW.replace("grill", "diagnose"))

    assert "diagnose" in (library / "matt-pocock.toml").read_text()


def test_installing_twice_leaves_one_link(library, shipped):
    link_shipped_workflows(library=library, shipped=shipped)

    linked = link_shipped_workflows(library=library, shipped=shipped)

    assert [path.name for path in library.iterdir()] == ["matt-pocock.toml"]
    assert linked[0].readlink() == shipped / "matt-pocock.toml"


def test_a_link_pointing_somewhere_else_is_replaced(library, shipped, tmp_path):
    """An address is cheap to rewrite, and a wrong one is what this repairs."""
    stale = tmp_path / "elsewhere" / "matt-pocock.toml"
    stale.parent.mkdir()
    stale.write_text(WORKFLOW)
    library.mkdir(parents=True)
    (library / "matt-pocock.toml").symlink_to(stale)

    link_shipped_workflows(library=library, shipped=shipped)

    assert (library / "matt-pocock.toml").readlink() == shipped / "matt-pocock.toml"


def test_a_link_to_a_file_that_is_gone_is_repaired(library, shipped, tmp_path):
    """What a moved or deleted checkout leaves behind. It is still an address,
    so it is rewritten rather than refused."""
    library.mkdir(parents=True)
    (library / "matt-pocock.toml").symlink_to(tmp_path / "gone" / "matt-pocock.toml")

    link_shipped_workflows(library=library, shipped=shipped)

    assert (library / "matt-pocock.toml").readlink() == shipped / "matt-pocock.toml"


def test_a_regular_file_of_the_same_name_is_refused(library, shipped):
    """The refusal that was missing: a copy in the library is exactly what fell
    four days behind, and it is not Naiad's to delete."""
    library.mkdir(parents=True)
    theirs = library / "matt-pocock.toml"
    theirs.write_text("their own copy\n")

    with pytest.raises(ValueError) as refused:
        link_shipped_workflows(library=library, shipped=shipped)

    assert theirs.read_text() == "their own copy\n"
    assert not theirs.is_symlink()
    assert str(theirs) in str(refused.value)


def test_a_refusal_links_nothing_at_all(library, shipped):
    """All of them or none: a refusal that had already written some entries
    would report none of what it did, and the operator reads the refusal
    against a library it cannot see."""
    (shipped / "hcgps-hotfix.toml").write_text(WORKFLOW.replace("matt-pocock", "hcgps-hotfix"))
    library.mkdir(parents=True)
    (library / "matt-pocock.toml").write_text("their own copy\n")

    with pytest.raises(ValueError):
        link_shipped_workflows(library=library, shipped=shipped)

    assert not (library / "hcgps-hotfix.toml").exists()


def test_leaves_the_operators_other_library_files_alone(library, shipped):
    library.mkdir(parents=True)
    theirs = library / "hcgps-hotfix.toml"
    theirs.write_text(WORKFLOW.replace("matt-pocock", "hcgps-hotfix"))

    link_shipped_workflows(library=library, shipped=shipped)

    assert theirs.read_text() == WORKFLOW.replace("matt-pocock", "hcgps-hotfix")


def test_a_package_with_no_workflows_beside_it_links_nothing(library, tmp_path):
    """Refused in one sentence rather than raised: the hooks and the skill have
    already landed, and a distribution carries no Workflow at all."""
    assert shipped_workflows(tmp_path / "no-checkout" / "workflows") == ()
    assert link_shipped_workflows(library=library, shipped=tmp_path / "no-checkout") == ()
    assert not library.exists()


def test_the_shipped_directory_defaults_to_the_one_beside_the_package():
    """Where the file actually is: pyproject packages naiad* alone, so a
    distribution carries no Workflow and only the checkout has one."""
    beside = Path(__file__).resolve().parents[1] / "workflows"

    assert shipped_workflows() == (beside / "matt-pocock.toml",)
