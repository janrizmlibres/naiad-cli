"""The three Queue commands as an operator meets them: exit status, what lands
on disk, what is printed.

`naiad queue add` is also the command an agent inside a session uses, so the
tests hold it to returning without supervising anything.
"""

import json

import pytest

from naiad.cli.main import main
from naiad.domain.decide import Finish
from naiad.domain.entry import Entry
from naiad.runtime.log import RunLog
from naiad.runtime.queue import Queue
from naiad.runtime.run import RunStore

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "implement"
prompt = "/implement the ticket at {subject}"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def home(monkeypatch, tmp_path):
    """A Naiad home of this test's own, beside the repositories rather than
    inside one."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    return tmp_path / "naiad"


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    (path / "workflow.toml").write_text(WORKFLOW)
    return path


@pytest.fixture(autouse=True)
def no_tmux(monkeypatch, sessions):
    """Nothing in this file may open a session. Wired for every test so that a
    command which tried to would be caught rather than reaching real tmux."""
    monkeypatch.setattr("naiad.cli.main.TmuxSessions", lambda: sessions)
    return sessions


def queue_of(home):
    return Queue(home / "queue")


def add(repo, *arguments):
    return main(
        [
            "queue",
            "add",
            str(repo / "workflow.toml"),
            "add dark mode",
            "--repo",
            str(repo),
            *arguments,
        ]
    )


def test_adding_an_entry_records_it_under_the_naiad_home(home, repo, capsys):
    assert add(repo, "--branch", "MC-AGENT-8546") == 0

    (queued,) = queue_of(home).all()
    assert queued.task == "add dark mode"
    assert queued.target_repo == repo
    assert queued.working_branch == "MC-AGENT-8546"
    assert queued.id in capsys.readouterr().out


def test_adding_an_entry_records_every_field_it_was_given(home, repo):
    add(
        repo,
        "--branch",
        "MC-AGENT-8546",
        "--base",
        "MC-AGENT-8000",
        "--at",
        "implement",
        "--subject",
        "docs/ticket.md",
        "--skip-gates",
    )

    (queued,) = queue_of(home).all()
    assert queued.pinned_base == "MC-AGENT-8000"
    assert queued.start_state == "implement"
    assert queued.subject == "docs/ticket.md"
    assert queued.skip_gates is True


def test_adding_an_entry_supervises_nothing(home, repo, no_tmux):
    """It must return promptly: a tool call that becomes a process blocking for
    hours is the failure the Queue exists to avoid."""
    add(repo, "--branch", "MC-AGENT-8546")

    assert no_tmux.spawned == []
    assert RunStore(home / "runs").all() == []
    assert queue_of(home).all()[0].run_id is None


def test_entries_added_in_a_row_each_get_their_own_place_in_the_queue(home, repo):
    """Ids are sortable timestamps, so adding twice in quick succession queues
    two Entries in the order they arrived rather than colliding."""
    add(repo, "--branch", "MC-AGENT-8546")
    add(repo, "--branch", "MC-AGENT-8547")

    ids = [held.id for held in queue_of(home).all()]
    assert ids == sorted(ids)
    assert [held.working_branch for held in queue_of(home).all()] == [
        "MC-AGENT-8546",
        "MC-AGENT-8547",
    ]


def test_adding_an_entry_with_no_working_branch_is_refused(home, repo, capsys):
    assert add(repo) == 2

    assert "--branch" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_adding_an_entry_on_a_branch_another_entry_claims_is_refused(home, repo, capsys):
    add(repo, "--branch", "MC-AGENT-8546")

    assert add(repo, "--branch", "MC-AGENT-8546") == 2

    assert "MC-AGENT-8546" in capsys.readouterr().err
    assert len(queue_of(home).all()) == 1


def test_adding_an_entry_starting_at_an_undeclared_state_is_refused(home, repo, capsys):
    assert add(repo, "--branch", "MC-AGENT-8546", "--at", "grrill") == 2

    assert "grrill" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_listing_shows_entries_in_queue_order_with_what_became_of_each(home, repo, capsys):
    add(repo, "--branch", "MC-AGENT-8546")
    add(repo, "--branch", "MC-AGENT-8547")
    first, second = queue_of(home).all()

    assert main(["queue", "list"]) == 0

    printed = capsys.readouterr().out
    assert printed.index(first.id) < printed.index(second.id)
    assert printed.count("waiting") == 2
    assert "MC-AGENT-8546" in printed and "add dark mode" in printed


def test_listing_tells_apart_two_repositories_that_share_a_name(home, repo, tmp_path, capsys):
    """One Queue spans every repository, so two checkouts called `repo` are
    exactly the case a list has to distinguish."""
    namesake = tmp_path / "elsewhere" / "repo"
    namesake.mkdir(parents=True)
    (namesake / "workflow.toml").write_text(WORKFLOW)
    add(repo, "--branch", "MC-AGENT-8546")
    add(namesake, "--branch", "MC-AGENT-8546")
    capsys.readouterr()

    assert main(["queue", "list"]) == 0

    printed = capsys.readouterr().out
    assert str(repo) in printed and str(namesake) in printed


def test_listing_derives_what_became_of_an_entry_from_its_run(home, repo, capsys):
    """No status is stored, so a finished Run is what makes an Entry done
    (ADR 0013)."""
    run = RunStore(home / "runs").create(
        run_id="a-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )
    RunLog(run.root).record(Finish(state="done"))
    queue_of(home).add(
        Entry(
            id="an-entry",
            workflow_path=repo / "workflow.toml",
            task="add dark mode",
            target_repo=repo,
            working_branch="MC-AGENT-8546",
            created_at="2026-07-22T12:00:00Z",
            run_id="a-run",
        )
    )

    assert main(["queue", "list"]) == 0

    printed = capsys.readouterr().out
    assert "done" in printed
    assert "a-run" in printed


def test_listing_a_queue_holding_an_unreadable_entry_reports_it(home, repo, capsys):
    """Read as a message rather than a traceback: the operator can see these
    files and so can damage one, and a stack trace is not something they can
    act on."""
    add(repo, "--branch", "MC-AGENT-8546")
    (document,) = (home / "queue").iterdir()
    document.write_text("{ not json")

    assert main(["queue", "list"]) == 2

    assert str(document) in capsys.readouterr().err


def test_listing_an_empty_queue_says_so_rather_than_printing_nothing(home, capsys):
    assert main(["queue", "list"]) == 0

    assert capsys.readouterr().out.strip() != ""


# `naiad queue watch`. The Supervisor against a real Queue is manual smoke — a
# loop that drives a real session through a fake tmux would be green over a
# system that does not work — so what is held here is the wiring: that the
# command supervises in follow mode, and that an Entry reaches the Run it
# becomes with everything it was queued with. The loop itself is covered in
# tests/test_supervisor.py and its rules in tests/test_supervise.py.


def supervision(monkeypatch):
    """Stand in for the Supervisor's loop, and record what it was wired with."""
    wiring = {}

    def fake(**arguments):
        wiring.update(arguments)

    monkeypatch.setattr("naiad.cli.main.supervise_queue", fake)
    return wiring


def test_watching_the_queue_supervises_in_follow_mode(home, monkeypatch):
    """Follow rather than drain, so that Entries added after the Supervisor
    started are picked up without starting anything again."""
    wiring = supervision(monkeypatch)

    assert main(["queue", "watch"]) == 0

    assert wiring["following"] is True
    assert wiring["queue"].root == home / "queue"
    assert wiring["runs"].root == home / "runs"


def test_watching_the_queue_starts_a_run_carrying_everything_the_entry_held(
    home, repo, monkeypatch, no_tmux
):
    """An Entry is a Run that does not exist yet, so every field it was queued
    with has to arrive at the Run — including the Predecessor the rules
    resolved, which is the Entry's alone to be told."""
    add(
        repo,
        "--branch",
        "MC-AGENT-8546",
        "--at",
        "implement",
        "--subject",
        "docs/ticket.md",
        "--skip-gates",
    )
    wiring = supervision(monkeypatch)

    assert main(["queue", "watch"]) == 0

    (queued,) = wiring["queue"].all()
    run = wiring["start"](queued, "MC-AGENT-8000")
    assert run.task == "add dark mode"
    assert run.target_repo == repo
    assert run.working_branch == "MC-AGENT-8546"
    assert run.predecessor == "MC-AGENT-8000"
    assert run.start_state == "implement"
    assert run.skip_gates is True
    assert no_tmux.spawned


def test_interrupting_the_supervisor_leaves_nothing_to_clean_up(home, monkeypatch):
    """Ctrl-C is how an operator stops the night. It stops a Supervisor exactly
    as it stops a watch: the Queue is on disk and the sessions are left alive."""

    def interrupted(**_arguments):
        raise KeyboardInterrupt

    monkeypatch.setattr("naiad.cli.main.supervise_queue", interrupted)

    assert main(["queue", "watch"]) == 0


def test_a_damaged_entry_stops_the_supervisor_with_a_message(home, repo, capsys):
    """Read as a message rather than a traceback, as listing one is: an
    operator can see these files and so can damage one."""
    add(repo, "--branch", "MC-AGENT-8546")
    (document,) = (home / "queue").iterdir()
    document.write_text("{ not json")

    assert main(["queue", "watch"]) == 2

    assert str(document) in capsys.readouterr().err


def test_removing_an_entry_takes_it_out_of_the_queue(home, repo, capsys):
    add(repo, "--branch", "MC-AGENT-8546")
    add(repo, "--branch", "MC-AGENT-8547")
    first, second = queue_of(home).all()

    assert main(["queue", "rm", first.id]) == 0

    assert [held.id for held in queue_of(home).all()] == [second.id]
    assert first.id in capsys.readouterr().out


def test_removing_an_entry_leaves_the_run_it_produced_untouched(home, repo):
    """Removal is a Queue operation rather than a destructive one: the Run and
    the session it is in are somebody else's record."""
    run = RunStore(home / "runs").create(
        run_id="a-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )
    queue_of(home).add(
        Entry(
            id="an-entry",
            workflow_path=repo / "workflow.toml",
            task="add dark mode",
            target_repo=repo,
            working_branch="MC-AGENT-8546",
            created_at="2026-07-22T12:00:00Z",
            run_id="a-run",
        )
    )

    assert main(["queue", "rm", "an-entry"]) == 0

    assert queue_of(home).all() == []
    assert json.loads(run.metadata_path.read_text())["task"] == "add dark mode"


def test_removing_an_entry_that_is_not_there_is_reported(home, repo, capsys):
    assert main(["queue", "rm", "no-such-entry"]) == 2

    assert "no-such-entry" in capsys.readouterr().err
