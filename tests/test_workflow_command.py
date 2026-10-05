"""`naiad workflow`, as an author meets it: exit
status, what is printed, and what lands in the library.

What each rendered line holds is asserted in tests/test_listing.py and how a
write keeps a file whole in tests/test_workflow_file.py; asserted here is which
files a call reaches and how it fails.
"""

import os
import re

import pytest

from fake_terminal import ESCAPE, to_terminal
from naiad.cli.main import build_parser, main
from naiad.cli.style import ABSENT
from naiad.domain.workflow import load_workflow
from naiad.runtime.log import RunLog
from naiad.runtime.queue import Queue
from naiad.runtime.run import RunStore

STARTER_LIKE = """\
# Kept: an author's own comment.
name = "demo"

[[states]]
name = "plan"
prompt = "/to-spec {task}"

[[states]]
name = "done"
terminal = true
"""


def cells(line):
    """A line's cells, told apart by two spaces or more."""
    return re.split(r"\s{2,}", line.strip())


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    return tmp_path / "naiad"


@pytest.fixture
def library(home):
    return home / "workflows"


def test_new_writes_a_terminal_done_into_the_library(library, capsys):
    assert main(["workflow", "new", "demo"]) == 0

    assert (library / "demo.toml").is_file()
    assert "demo" in capsys.readouterr().out


def test_show_then_lists_that_one_terminal_state(library, capsys):
    main(["workflow", "new", "demo"])
    capsys.readouterr()

    assert main(["workflow", "show", "demo"]) == 0

    printed = capsys.readouterr().out
    assert [cells(line) for line in printed.splitlines()] == [
        ["name", "demo"],
        [""],
        ["STATE", "KIND"],
        ["done", "terminal"],
    ]


def test_check_passes_on_what_new_wrote(library, capsys):
    main(["workflow", "new", "demo"])
    capsys.readouterr()

    assert main(["workflow", "check", "demo"]) == 0

    assert capsys.readouterr().out.strip() == "demo: OK"


def test_the_queue_accepts_a_workflow_new_wrote(home, tmp_path):
    main(["workflow", "new", "demo"])
    repo = tmp_path / "repo"
    repo.mkdir()

    assert main(["queue", "add", "demo", "a task", "--repo", str(repo)]) == 0

    assert len(Queue(home / "queue").all()) == 1


def test_new_refuses_a_name_that_exists_and_leaves_it_alone(library, capsys):
    library.mkdir(parents=True)
    (library / "demo.toml").write_text(STARTER_LIKE)

    assert main(["workflow", "new", "demo"]) == 2

    assert "already" in capsys.readouterr().err
    assert (library / "demo.toml").read_text() == STARTER_LIKE


@pytest.mark.parametrize("argument", ["sub/demo", "demo.toml", ""])
def test_new_takes_a_bare_name_and_nothing_shaped_like_a_path(library, capsys, argument):
    assert main(["workflow", "new", argument]) == 2

    assert "name" in capsys.readouterr().err
    assert not library.exists()


def test_show_reads_a_path_as_a_path(tmp_path, capsys):
    elsewhere = tmp_path / "elsewhere.toml"
    elsewhere.write_text(STARTER_LIKE)

    assert main(["workflow", "show", str(elsewhere)]) == 0

    assert "/to-spec" in capsys.readouterr().out


def test_show_refuses_a_name_the_library_does_not_hold(library, capsys):
    assert main(["workflow", "show", "nothing"]) == 2

    assert "no workflow named 'nothing'" in capsys.readouterr().err


def test_check_prints_the_loaders_refusal_and_exits_two(library, capsys):
    library.mkdir(parents=True)
    (library / "demo.toml").write_text('name = "demo"\nmodle = "opus"\n')

    assert main(["workflow", "check", "demo"]) == 2

    err = capsys.readouterr().err
    assert "unknown key 'modle'" in err


def test_check_reads_a_path_as_a_path(tmp_path, capsys):
    elsewhere = tmp_path / "elsewhere.toml"
    elsewhere.write_text(STARTER_LIKE)

    assert main(["workflow", "check", str(elsewhere)]) == 0


def test_states_and_show_name_the_same_states_with_the_same_words(library, capsys):
    """The agent's listing and the author's table are two layouts of one set of
    facts; with its header and dashes left out, show's row is the agent's line."""
    library.mkdir(parents=True)
    (library / "demo.toml").write_text(STARTER_LIKE)

    main(["states", "demo"])
    listed = [cells(line) for line in capsys.readouterr().out.splitlines()[1:]]
    main(["workflow", "show", "demo"])
    shown = capsys.readouterr().out.splitlines()
    table = shown[shown.index("") + 2 :]

    assert [[cell for cell in cells(row) if cell != ABSENT] for row in table] == listed


def test_show_is_styled_at_a_terminal(library, monkeypatch):
    held(library)
    terminal = to_terminal(monkeypatch)

    assert main(["workflow", "show", "demo"]) == 0

    assert ESCAPE in terminal.getvalue()


def held(library, name="demo", text=STARTER_LIKE):
    library.mkdir(parents=True, exist_ok=True)
    (library / f"{name}.toml").write_text(text)
    return library / f"{name}.toml"


def queued(home, tmp_path, workflow="demo"):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    assert main(["queue", "add", workflow, "a task", "--repo", str(repo)]) == 0
    (entry,) = Queue(home / "queue").all()
    return entry


# list


def test_list_names_every_library_entry(library, capsys):
    held(library, "beta", STARTER_LIKE.replace("demo", "beta"))
    held(library, "alpha", STARTER_LIKE.replace("demo", "alpha"))

    assert main(["workflow", "list"]) == 0

    assert [cells(line) for line in capsys.readouterr().out.splitlines()] == [
        ["WORKFLOW"],
        ["alpha"],
        ["beta"],
    ]


def test_list_names_a_broken_link_as_broken_and_still_lists_the_rest(library, tmp_path, capsys):
    held(library, "alpha", STARTER_LIKE.replace("demo", "alpha"))
    (library / "gone.toml").symlink_to(tmp_path / "missing.toml")

    assert main(["workflow", "list"]) == 0

    rows = [cells(line) for line in capsys.readouterr().out.splitlines()]
    assert [row[0] for row in rows] == ["WORKFLOW", "alpha", "gone"]
    assert rows[1][1] == ABSENT
    assert "broken" in rows[2][1]


def test_list_is_styled_at_a_terminal(library, monkeypatch):
    held(library, "alpha", 'name = "alpha"\nmodle = "x"\n')
    terminal = to_terminal(monkeypatch)

    assert main(["workflow", "list"]) == 0

    assert ESCAPE in terminal.getvalue()


def test_list_names_a_file_the_loader_refuses_in_place(library, capsys):
    held(library, "alpha", 'name = "alpha"\nmodle = "x"\n')

    assert main(["workflow", "list"]) == 0

    assert "unknown key 'modle'" in capsys.readouterr().out


def test_list_of_an_empty_library_says_where_to_put_files(library, capsys):
    assert main(["workflow", "list"]) == 0

    assert "holds no workflows" in capsys.readouterr().out


# set and unset


def test_set_writes_a_file_level_key_and_show_reads_it_back(library, capsys):
    held(library)

    assert main(["workflow", "set", "demo", "model", "opus"]) == 0
    capsys.readouterr()
    main(["workflow", "show", "demo"])

    assert load_workflow(library / "demo.toml").model == "opus"
    assert "opus" in capsys.readouterr().out


@pytest.mark.parametrize(
    "key, attribute",
    [
        ("model", "model"),
        ("effort", "effort"),
        ("autocompact", "autocompact"),
        ("answerer.model", "answerer_model"),
        ("answerer.effort", "answerer_effort"),
        ("answerer.fallback", "answerer_fallback"),
    ],
)
def test_every_file_level_key_can_be_set_then_unset(library, key, attribute):
    path = held(library)

    assert main(["workflow", "set", "demo", key, "200k"]) == 0
    assert getattr(load_workflow(path), attribute) == "200k"
    assert main(["workflow", "unset", "demo", key]) == 0

    assert getattr(load_workflow(path), attribute) is None


def test_set_keeps_the_authors_comments(library):
    path = held(library)

    main(["workflow", "set", "demo", "effort", "high"])

    assert path.read_text().startswith("# Kept: an author's own comment.\n")


def test_set_refuses_an_unknown_key_before_writing(library, capsys):
    path = held(library)

    assert main(["workflow", "set", "demo", "modle", "opus"]) == 2

    assert "unknown key 'modle'" in capsys.readouterr().err
    assert path.read_text() == STARTER_LIKE


def test_set_name_is_refused_naming_rename(library, capsys):
    path = held(library)

    assert main(["workflow", "set", "demo", "name", "other"]) == 2

    assert "naiad workflow rename" in capsys.readouterr().err
    assert path.read_text() == STARTER_LIKE


def test_set_refuses_a_blank_value_before_writing(library, capsys):
    path = held(library)

    assert main(["workflow", "set", "demo", "model", ""]) == 2

    assert path.read_text() == STARTER_LIKE


def test_unset_of_a_key_that_is_absent_succeeds_and_says_so(library, capsys):
    path = held(library)

    assert main(["workflow", "unset", "demo", "model"]) == 0

    assert "not set" in capsys.readouterr().out
    assert path.read_text() == STARTER_LIKE


def test_set_writes_through_a_link_and_leaves_the_link(library, tmp_path):
    target = tmp_path / "elsewhere" / "demo.toml"
    target.parent.mkdir()
    target.write_text(STARTER_LIKE)
    library.mkdir(parents=True)
    (library / "demo.toml").symlink_to(target)

    assert main(["workflow", "set", "demo", "model", "opus"]) == 0

    assert (library / "demo.toml").is_symlink()
    assert load_workflow(target).model == "opus"


def test_set_and_unset_help_print_the_key_table(capsys):
    for verb in ("set", "unset"):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["workflow", verb, "--help"])
        helped = capsys.readouterr().out
        for key in ("model", "effort", "autocompact", "answerer.model", "answerer.fallback"):
            assert key in helped


# new --from


def test_new_from_a_name_copies_it_and_rewrites_the_name(library):
    source = held(library, "a", STARTER_LIKE.replace("demo", "a"))

    assert main(["workflow", "new", "b", "--from", "a"]) == 0

    copied = library / "b.toml"
    assert copied.read_text() == source.read_text().replace('name = "a"', 'name = "b"')
    assert load_workflow(copied).name == "b"
    assert main(["workflow", "check", "b"]) == 0


def test_new_from_a_path_copies_it(library, tmp_path):
    elsewhere = tmp_path / "somewhere.toml"
    elsewhere.write_text(STARTER_LIKE)

    assert main(["workflow", "new", "b", "--from", str(elsewhere)]) == 0

    assert load_workflow(library / "b.toml").name == "b"
    assert elsewhere.read_text() == STARTER_LIKE


def test_new_from_refuses_a_name_that_exists_and_leaves_it_alone(library, capsys):
    held(library, "a", STARTER_LIKE.replace("demo", "a"))
    taken = held(library, "b", STARTER_LIKE.replace("demo", "b"))
    before = taken.read_text()

    assert main(["workflow", "new", "b", "--from", "a"]) == 2

    assert "already" in capsys.readouterr().err
    assert taken.read_text() == before


def test_new_from_a_name_the_library_does_not_hold_writes_nothing(library, capsys):
    assert main(["workflow", "new", "b", "--from", "nothing"]) == 2

    assert "no workflow named 'nothing'" in capsys.readouterr().err
    assert not (library / "b.toml").exists()


def test_new_from_a_file_the_loader_refuses_writes_nothing(library, capsys):
    held(library, "a", 'name = "a"\nmodle = "x"\n')

    assert main(["workflow", "new", "b", "--from", "a"]) == 2

    assert not (library / "b.toml").exists()


# rm


def test_rm_removes_the_file(library, capsys):
    path = held(library)

    assert main(["workflow", "rm", "demo"]) == 0

    assert not path.exists()
    assert main(["workflow", "show", "demo"]) == 2


def test_rm_of_a_link_removes_the_link_and_not_its_target(library, tmp_path):
    target = tmp_path / "elsewhere.toml"
    target.write_text(STARTER_LIKE)
    library.mkdir(parents=True)
    (library / "demo.toml").symlink_to(target)

    assert main(["workflow", "rm", "demo"]) == 0

    assert not (library / "demo.toml").is_symlink()
    assert target.read_text() == STARTER_LIKE


def test_rm_removes_a_broken_link(library, tmp_path):
    library.mkdir(parents=True)
    (library / "gone.toml").symlink_to(tmp_path / "missing.toml")

    assert main(["workflow", "rm", "gone"]) == 0

    assert not (library / "gone.toml").is_symlink()


def test_rm_refuses_a_name_the_library_does_not_hold(library, capsys):
    assert main(["workflow", "rm", "nothing"]) == 2

    assert "no workflow named 'nothing'" in capsys.readouterr().err


def test_rm_refuses_while_a_waiting_entry_addresses_the_file_naming_it(
    home, library, tmp_path, capsys
):
    path = held(library)
    entry = queued(home, tmp_path)

    assert main(["workflow", "rm", "demo"]) == 2

    err = capsys.readouterr().err
    assert entry.id in err
    assert "naiad queue rm" in err
    assert path.is_file()


def test_rm_succeeds_once_the_entry_is_removed(home, library, tmp_path):
    path = held(library)
    entry = queued(home, tmp_path)
    main(["queue", "rm", entry.id])

    assert main(["workflow", "rm", "demo"]) == 0

    assert not path.exists()


def test_rm_does_not_mind_an_entry_that_is_done(home, library, tmp_path):
    path = held(library)
    entry = queued(home, tmp_path)
    finished_run(home, entry)

    assert main(["workflow", "rm", "demo"]) == 0
    assert not path.exists()


def test_rm_counts_a_link_and_its_target_as_one_file(home, library, tmp_path, capsys):
    target = tmp_path / "elsewhere.toml"
    target.write_text(STARTER_LIKE)
    library.mkdir(parents=True)
    (library / "demo.toml").symlink_to(target)
    # The Entry addresses the target by path; the library addresses it by link.
    entry = queued(home, tmp_path, workflow=str(target))

    assert main(["workflow", "rm", "demo"]) == 2

    assert entry.id in capsys.readouterr().err


def test_rm_refuses_while_a_live_run_addresses_the_file_naming_it(home, library, tmp_path, capsys):
    path = held(library)
    repo = tmp_path / "repo"
    repo.mkdir()
    run = RunStore(home / "runs").create(
        run_id="20260929-120000-demo-1",
        workflow_path=path,
        task="t",
        target_repo=repo,
        created_at="2026-09-29T12:00:00Z",
    )

    assert main(["workflow", "rm", "demo"]) == 2

    assert run.id in capsys.readouterr().err
    assert path.is_file()


def finished_run(home, entry):
    runs = RunStore(home / "runs")
    run = runs.create(
        run_id="20260929-120000-demo-2",
        workflow_path=entry.workflow_path,
        task="t",
        target_repo=entry.target_repo,
        created_at="2026-09-29T12:00:00Z",
    )
    queue = Queue(home / "queue")
    queue.attach_run(entry, run_id=run.id)
    RunLog(run.root).record_cancellation(state=None)
    return run


# rename


def test_rename_moves_the_file_and_its_name_key_together(library, capsys):
    held(library)

    assert main(["workflow", "rename", "demo", "renamed"]) == 0

    assert not (library / "demo.toml").exists()
    assert load_workflow(library / "renamed.toml").name == "renamed"
    assert main(["workflow", "check", "renamed"]) == 0


def test_a_renamed_workflow_resolves_by_its_new_name_and_its_old_name_is_gone(library, capsys):
    held(library)
    main(["workflow", "rename", "demo", "renamed"])
    capsys.readouterr()

    assert main(["workflow", "show", "renamed"]) == 0
    assert main(["workflow", "show", "demo"]) == 2

    assert "no workflow named 'demo'" in capsys.readouterr().err


def test_rename_keeps_the_authors_comments(library):
    held(library)

    main(["workflow", "rename", "demo", "renamed"])

    text = (library / "renamed.toml").read_text()
    assert text == STARTER_LIKE.replace('name = "demo"', 'name = "renamed"')


def test_rename_refuses_a_name_that_is_taken_and_changes_nothing(library, capsys):
    path = held(library)
    taken = held(library, "other", STARTER_LIKE.replace("demo", "other"))
    before = taken.read_text()

    assert main(["workflow", "rename", "demo", "other"]) == 2

    assert "already" in capsys.readouterr().err
    assert path.read_text() == STARTER_LIKE
    assert taken.read_text() == before


@pytest.mark.parametrize("new", ["sub/x", "x.toml", ""])
def test_rename_takes_a_bare_name(library, capsys, new):
    path = held(library)

    assert main(["workflow", "rename", "demo", new]) == 2

    assert path.read_text() == STARTER_LIKE


def test_rename_refuses_while_a_waiting_entry_addresses_the_file_naming_it(
    home, library, tmp_path, capsys
):
    path = held(library)
    entry = queued(home, tmp_path)

    assert main(["workflow", "rename", "demo", "renamed"]) == 2

    err = capsys.readouterr().err
    assert entry.id in err
    assert "naiad queue rm" in err
    assert path.read_text() == STARTER_LIKE
    assert not (library / "renamed.toml").exists()


def test_rename_succeeds_once_the_entry_is_removed(home, library, tmp_path):
    held(library)
    entry = queued(home, tmp_path)
    main(["queue", "rm", entry.id])

    assert main(["workflow", "rename", "demo", "renamed"]) == 0

    assert (library / "renamed.toml").is_file()


def test_rename_of_a_link_moves_the_link_and_renames_the_target_inside(library, tmp_path):
    target = tmp_path / "elsewhere.toml"
    target.write_text(STARTER_LIKE)
    library.mkdir(parents=True)
    (library / "demo.toml").symlink_to(target)

    assert main(["workflow", "rename", "demo", "renamed"]) == 0

    assert (library / "renamed.toml").is_symlink()
    assert os.path.realpath(library / "renamed.toml") == str(target.resolve())
    assert load_workflow(target).name == "renamed"
    assert not (library / "demo.toml").is_symlink()


def test_a_verb_that_writes_nothing_leaves_no_temporary_file_behind(library):
    held(library)

    main(["workflow", "rename", "demo", "renamed"])
    main(["workflow", "set", "renamed", "model", "opus"])

    assert sorted(file.name for file in library.iterdir()) == ["renamed.toml"]
