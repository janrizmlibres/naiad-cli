"""Reading a batch file: a night's work as one document.

Held to the shape Workflow parsing is already held to — a well-formed file
produces what it declares, and a malformed one is rejected naming the file and
the offending position — because a batch file is written by a person or an
agent, and both need to be told which line to fix.

Queueing what a file declares is tested in tests/test_enqueue.py, where the
refusals it shares with the single-Entry path live.
"""

from pathlib import Path

import pytest

from naiad.cli.batch import BatchError, parse_batch

BATCH = """
workflow = "workflows/matt-pocock.toml"
repo = "/repos/hcgps"

[[entries]]
task = "the login redirect loops"
branch = "MC-AGENT-8546"
at = "diagnose"

[[entries]]
task = "design the audit log"
branch = "MC-AGENT-8547"
at = "grill"
base = "MC-AGENT-8000"
subject = "docs/ticket.md"
skip-gates = true
"""


def parse(text, repo=Path("/repos/default"), library=Path("/library")):
    return parse_batch(text, source="batch.toml", repo=repo, library=library)


def test_a_batch_file_declares_one_piece_of_work_per_entry():
    first, second = parse(BATCH)

    assert first.task == "the login redirect loops"
    assert first.working_branch == "MC-AGENT-8546"
    assert first.start_state == "diagnose"
    assert second.task == "design the audit log"
    assert second.working_branch == "MC-AGENT-8547"


def test_entries_in_one_file_may_differ_in_everything_that_describes_them():
    """What makes a file worth having: three bugs starting at one State and two
    designs starting at another go in one document, which repeated flags cannot
    express without positional pairing nobody can read."""
    _first, second = parse(BATCH)

    assert second.start_state == "grill"
    assert second.pinned_base == "MC-AGENT-8000"
    assert second.subject == "docs/ticket.md"
    assert second.skip_gates is True


def test_an_entry_saying_nothing_about_the_optional_fields_carries_none_of_them():
    first, _second = parse(BATCH)

    assert first.pinned_base is None
    assert first.subject is None
    assert first.skip_gates is False


def test_the_entries_arrive_in_the_order_the_file_writes_them():
    """Ordering follows the file, because file order is what the Predecessor
    rule reads: a batch is usually also a stack."""
    works = parse(
        """
        workflow = "w.toml"

        [[entries]]
        task = "third"
        branch = "c"

        [[entries]]
        task = "first"
        branch = "a"

        [[entries]]
        task = "second"
        branch = "b"
        """
    )

    assert [work.task for work in works] == ["third", "first", "second"]


def test_a_top_level_key_is_the_default_for_every_entry():
    """Five Entries against one repository should not repeat the same Workflow
    and repository five times."""
    first, second = parse(BATCH)

    assert first.workflow_path == Path("workflows/matt-pocock.toml").resolve()
    assert second.workflow_path == first.workflow_path
    assert first.target_repo == Path("/repos/hcgps")
    assert second.target_repo == first.target_repo


def test_a_key_on_an_entry_overrides_the_default_above_it():
    first, second = parse(
        """
        workflow = "shared.toml"
        repo = "/repos/hcgps"
        at = "grill"

        [[entries]]
        task = "one"
        branch = "a"

        [[entries]]
        task = "two"
        branch = "b"
        workflow = "other.toml"
        repo = "/repos/naiad"
        at = "diagnose"
        """
    )

    assert first.workflow_path == Path("shared.toml").resolve()
    assert first.target_repo == Path("/repos/hcgps")
    assert first.start_state == "grill"
    assert second.workflow_path == Path("other.toml").resolve()
    assert second.target_repo == Path("/repos/naiad")
    assert second.start_state == "diagnose"


def test_an_entry_naming_no_repository_stands_in_the_working_directory():
    """The default `--repo` already has, so that a file describing work in the
    repository it sits in has nothing to say about where that is."""
    (work,) = parse(
        """
        workflow = "w.toml"

        [[entries]]
        task = "one"
        branch = "a"
        """,
        repo=Path("/repos/cwd"),
    )

    assert work.target_repo == Path("/repos/cwd")


def test_a_workflow_given_as_a_bare_name_resolves_through_the_library(tmp_path):
    library = tmp_path / "workflows"
    library.mkdir()
    (library / "matt-pocock.toml").write_text(
        'name = "matt-pocock"\n\n[[states]]\nname = "done"\nterminal = true\n'
    )

    (work,) = parse(
        'workflow = "matt-pocock"\n\n[[entries]]\ntask = "one"\nbranch = "a"\n',
        library=library,
    )

    assert work.workflow_path == library / "matt-pocock.toml"


def test_a_name_the_library_does_not_hold_is_rejected_naming_the_position(tmp_path):
    library = tmp_path / "workflows"
    library.mkdir()

    with pytest.raises(BatchError) as caught:
        parse(
            'workflow = "matt-pocok"\n\n[[entries]]\ntask = "one"\nbranch = "a"\n',
            library=library,
        )

    message = str(caught.value)
    assert "batch.toml" in message
    assert "entry 1" in message
    assert "no workflow named 'matt-pocok'" in message


def test_a_file_that_is_not_valid_toml_is_rejected_naming_the_file():
    with pytest.raises(BatchError) as caught:
        parse("[[entries]\ntask = ")

    assert "batch.toml" in str(caught.value)


def test_a_file_declaring_no_entries_is_rejected_naming_the_file():
    with pytest.raises(BatchError) as caught:
        parse('workflow = "w.toml"\n')

    assert "batch.toml" in str(caught.value)
    assert "entries" in str(caught.value)


def test_an_entry_that_is_not_a_table_is_rejected_naming_its_position():
    with pytest.raises(BatchError) as caught:
        parse('workflow = "w.toml"\nentries = ["one", "two"]\n')

    assert "batch.toml" in str(caught.value)
    assert "1" in str(caught.value)


def test_an_entry_naming_no_task_is_rejected_naming_its_position():
    with pytest.raises(BatchError) as caught:
        parse(
            """
            workflow = "w.toml"

            [[entries]]
            task = "one"
            branch = "a"

            [[entries]]
            branch = "b"
            """
        )

    assert "entry 2" in str(caught.value)
    assert "task" in str(caught.value)


def test_an_entry_naming_no_workflow_is_rejected_naming_its_position():
    with pytest.raises(BatchError) as caught:
        parse(
            """
            [[entries]]
            task = "one"
            branch = "a"
            """
        )

    assert "entry 1" in str(caught.value)
    assert "workflow" in str(caught.value)


def test_an_entry_whose_field_is_of_the_wrong_type_is_rejected_naming_its_position():
    with pytest.raises(BatchError) as caught:
        parse(
            """
            workflow = "w.toml"

            [[entries]]
            task = "one"
            branch = ["a", "b"]
            """
        )

    assert "entry 1" in str(caught.value)
    assert "branch" in str(caught.value)


def test_an_entry_skipping_gates_must_say_so_with_a_boolean():
    with pytest.raises(BatchError) as caught:
        parse(
            """
            workflow = "w.toml"

            [[entries]]
            task = "one"
            branch = "a"
            skip-gates = "yes"
            """
        )

    assert "entry 1" in str(caught.value)
    assert "skip-gates" in str(caught.value)


def test_a_key_naiad_does_not_read_is_refused_rather_than_ignored():
    """A file is written by a person or an agent, and a key nothing reads is a
    setting its writer believes they made — a misspelt `skip-gates` would park
    the unattended night it was written to avoid."""
    with pytest.raises(BatchError) as caught:
        parse(
            """
            workflow = "w.toml"

            [[entries]]
            task = "one"
            branch = "a"
            skip_gates = true
            """
        )

    assert "entry 1" in str(caught.value)
    assert "skip_gates" in str(caught.value)


def test_a_default_naiad_does_not_read_is_refused_naming_the_file():
    with pytest.raises(BatchError) as caught:
        parse(
            """
            workflow = "w.toml"
            brnach = "a"

            [[entries]]
            task = "one"
            branch = "a"
            """
        )

    assert "batch.toml" in str(caught.value)
    assert "brnach" in str(caught.value)
