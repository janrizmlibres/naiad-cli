"""Copying the starter into the library on request.

The library is the operator's store, so what is pinned here is the rule for a
file of the starter's name: absent, it is written; byte-identical, it is
refreshed; anything else is the operator's and is refused unless they say
otherwise. That the resolution rule itself works is tests/test_library.py's;
that the shipped file is well-formed is tests/test_shipped_workflow.py's.
"""

from importlib.resources import files

import pytest

from naiad.cli.library import install_starter, resolve_workflow

SHIPPED = files("naiad.workflows").joinpath("starter.toml").read_bytes()
REFUSAL = "starter.toml differs from the shipped starter; pass --force or move it aside"


@pytest.fixture
def library(tmp_path):
    return tmp_path / "home" / "workflows"


def test_writes_a_regular_file_into_a_library_that_does_not_exist_yet(library):
    written = install_starter(library=library)

    assert written == library / "starter.toml"
    assert written.is_file() and not written.is_symlink()
    assert written.read_bytes() == SHIPPED


def test_the_copy_is_what_the_bare_name_resolves_to(library):
    install_starter(library=library)

    assert resolve_workflow("starter", library=library) == library / "starter.toml"


def test_a_byte_identical_file_is_rewritten(library):
    """An older copy of the same bytes loses nothing, and rewriting is what
    refreshes the file once the shipped one has moved on."""
    library.mkdir(parents=True)
    (library / "starter.toml").write_bytes(SHIPPED)

    written = install_starter(library=library)

    assert written.read_bytes() == SHIPPED
    assert not written.is_symlink()


def test_a_differing_file_is_refused_and_left_as_it_was(library):
    """The difference is the operator's work, and a re-run done without
    thinking must not destroy it."""
    library.mkdir(parents=True)
    theirs = library / "starter.toml"
    theirs.write_text("my edits\n")

    with pytest.raises(ValueError) as refused:
        install_starter(library=library)

    assert str(refused.value) == REFUSAL
    assert theirs.read_text() == "my edits\n"


def test_a_symlink_of_that_name_is_refused_and_never_replaced(library, tmp_path):
    """A hand-made link is an entry for a Workflow maintained elsewhere, and
    copying over it would let that file go stale beside a copy of it."""
    maintained = tmp_path / "checkout" / "starter.toml"
    maintained.parent.mkdir()
    maintained.write_bytes(SHIPPED)
    library.mkdir(parents=True)
    (library / "starter.toml").symlink_to(maintained)

    with pytest.raises(ValueError) as refused:
        install_starter(library=library)

    assert str(refused.value) == REFUSAL
    assert (library / "starter.toml").readlink() == maintained


def test_force_overwrites_a_differing_file(library):
    library.mkdir(parents=True)
    (library / "starter.toml").write_text("my edits\n")

    written = install_starter(library=library, force=True)

    assert written.read_bytes() == SHIPPED


def test_force_replaces_a_symlink_rather_than_writing_through_it(library, tmp_path):
    """Writing through the link would edit the file in the other repository,
    which is not what asking for the shipped starter means."""
    maintained = tmp_path / "checkout" / "starter.toml"
    maintained.parent.mkdir()
    maintained.write_text("maintained elsewhere\n")
    library.mkdir(parents=True)
    (library / "starter.toml").symlink_to(maintained)

    written = install_starter(library=library, force=True)

    assert written.is_file() and not written.is_symlink()
    assert written.read_bytes() == SHIPPED
    assert maintained.read_text() == "maintained elsewhere\n"


def test_leaves_the_operators_other_library_files_alone(library):
    library.mkdir(parents=True)
    theirs = library / "acme-hotfix.toml"
    theirs.write_text("their own\n")

    install_starter(library=library)

    assert theirs.read_text() == "their own\n"
