"""`naiad states`, as the adopting agent meets it: exit status and what is
printed.

A listing added for the one reader that needs it —
an agent turning the operator's words into a State the Workflow declares. What
each line holds is asserted in tests/test_listing.py; what is asserted here is
which Workflows a call reaches and how it fails.
"""

import pytest

from naiad.cli.main import main

WORKFLOW = """
name = "matt-pocock"

[[states]]
name = "spec"
prompt = "/to-spec"

[[states]]
name = "done"
terminal = true
"""

OTHER = """
name = "acme-hotfix"

[[states]]
name = "diagnose"
prompt = "/diagnosing-bugs {task}"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def library(monkeypatch, tmp_path):
    """A Workflow library of this test's own, reached the way the command
    reaches it: under the Naiad home."""
    root = tmp_path / "naiad" / "workflows"
    root.mkdir(parents=True)
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    return root


def test_a_bare_name_lists_that_workflows_states(library, capsys):
    (library / "matt-pocock.toml").write_text(WORKFLOW)

    assert main(["states", "matt-pocock"]) == 0

    printed = capsys.readouterr().out
    assert "matt-pocock" in printed
    assert "/to-spec" in printed


def test_a_path_is_read_as_a_path(library, tmp_path, capsys):
    """The same rule every entrance obeys: shape alone decides, so a Workflow
    outside the library is listed by naming its file."""
    elsewhere = tmp_path / "elsewhere.toml"
    elsewhere.write_text(WORKFLOW)

    assert main(["states", str(elsewhere)]) == 0
    assert "/to-spec" in capsys.readouterr().out


def test_no_workflow_lists_every_one_the_library_holds(library, capsys):
    """What the agent runs when the operator named no Workflow: one call
    answers both which Workflows exist and what each declares."""
    (library / "matt-pocock.toml").write_text(WORKFLOW)
    (library / "acme-hotfix.toml").write_text(OTHER)

    assert main(["states"]) == 0

    printed = capsys.readouterr().out
    assert "matt-pocock" in printed
    assert "acme-hotfix" in printed
    assert "/to-spec" in printed
    assert "/diagnosing-bugs" in printed


def test_an_empty_library_says_where_workflows_go(library, capsys):
    """An empty listing is an empty library rather than a failure, so it says
    what would fill it instead of refusing."""
    assert main(["states"]) == 0

    printed = capsys.readouterr().out
    assert str(library) in printed


def test_a_name_the_library_does_not_hold_is_refused_with_what_it_does(library, capsys):
    """The refusal already written, reaching the agent here too: a
    misremembered name is answered with the names that exist."""
    (library / "matt-pocock.toml").write_text(WORKFLOW)

    assert main(["states", "matt-pocok"]) == 2
    assert "matt-pocock" in capsys.readouterr().err


def test_a_workflow_that_cannot_be_parsed_is_refused_rather_than_traced(library, capsys):
    (library / "matt-pocock.toml").write_text("name = 'matt-pocock'\n")

    assert main(["states", "matt-pocock"]) == 2
    assert "naiad:" in capsys.readouterr().err


def test_one_unreadable_workflow_does_not_hide_the_rest(library, capsys):
    """A whole listing lost to one damaged file would leave the agent guessing
    at the Workflows that are fine, which is what the listing prevents."""
    (library / "matt-pocock.toml").write_text(WORKFLOW)
    (library / "broken.toml").write_text("this is not a workflow")

    assert main(["states"]) == 0

    printed = capsys.readouterr().out
    assert "/to-spec" in printed
    assert "broken" in printed
