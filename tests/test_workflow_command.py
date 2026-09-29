"""`naiad workflow new`, `show` and `check`, as an author meets them: exit
status, what is printed, and what lands in the library.

What each rendered line holds is asserted in tests/test_listing.py and how a
write keeps a file whole in tests/test_workflow_file.py; asserted here is which
files a call reaches and how it fails.
"""

import pytest

from naiad.cli.main import main
from naiad.runtime.queue import Queue

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
    assert printed.splitlines()[0].split() == ["name", "demo"]
    assert [line.split()[:2] for line in printed.splitlines()[2:]] == [["done", "terminal"]]


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


def test_states_and_show_render_the_states_the_same(library, capsys):
    library.mkdir(parents=True)
    (library / "demo.toml").write_text(STARTER_LIKE)

    main(["states", "demo"])
    listed = capsys.readouterr().out.splitlines()[1:]
    main(["workflow", "show", "demo"])
    shown = capsys.readouterr().out.splitlines()

    assert shown[-len(listed):] == listed
