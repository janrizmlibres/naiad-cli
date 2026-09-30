"""`naiad run` as an operator meets it: one entrance to starting Runs.

It adds one Entry and then adopts or becomes — returning at once when a
Supervisor already holds the lock, and supervising in the foreground when none
does. Both halves are asserted here, because the pair is the command.

The lock is real and taken by the test itself rather than by a second process.
Racing two real Supervisors would be flaky, slow, and would assert the operating
system's behaviour rather than Naiad's; what is asserted instead is what each
command does with the lock's answer.

Supervising itself is handed to a stand-in. Driving a Run for real would need a
fake tmux and a fake agent, and green tests over a system that does not work is
the failure this project is avoiding; the loop is covered in
tests/test_supervisor.py and its rules in tests/test_supervise.py.
"""

import pytest

from naiad.adapters.lock import SupervisorLock
from naiad.cli.main import main
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
    inside one — so the lock this test takes is this test's alone."""
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


def run(repo, *arguments):
    return main(
        [
            "run",
            str(repo / "workflow.toml"),
            "add dark mode",
            "--repo",
            str(repo),
            *arguments,
        ]
    )


def supervision(monkeypatch, *, then=None):
    """Stand in for the Supervisor's loop, and record what it was wired with.

    `then` is called while the stand-in is running, for the tests that ask what
    is true *during* supervision rather than after it.
    """
    wiring = {}

    def fake(**arguments):
        wiring.update(arguments)
        if then is not None:
            wiring["during"] = then()

    monkeypatch.setattr("naiad.cli.main.supervise_queue", fake)
    return wiring


def refuse_supervising(monkeypatch):
    """For the tests where supervising at all would be the bug."""

    def fake(**_arguments):
        raise AssertionError("a second supervisor was started")

    monkeypatch.setattr("naiad.cli.main.supervise_queue", fake)


@pytest.fixture
def supervised(home):
    """A Supervisor already holding the lock, without a second process."""
    with SupervisorLock(home / "supervisor.lock").taken() as mine:
        assert mine
        yield


# One entrance: the Entry lands, and no session is spawned behind the Queue's back.


def test_running_by_bare_name_queues_the_library_file_of_that_stem(home, repo, monkeypatch):
    """`naiad run` shares the one entrance, so a bare name resolves through
    the Workflow library here exactly as it does at `queue add`."""
    supervision(monkeypatch)
    library = home / "workflows"
    library.mkdir(parents=True)
    (library / "feature.toml").write_text(WORKFLOW)

    assert main(["run", "feature", "add dark mode", "--repo", str(repo)]) == 0

    (queued,) = queue_of(home).all()
    assert queued.workflow_path == library / "feature.toml"


def test_running_adds_an_entry_rather_than_spawning_a_session(home, repo, no_tmux, monkeypatch):
    """A second entrance to starting Runs would bypass the guard that matters
    most: nothing would stop an immediate Run putting a second agent into a
    working tree the Supervisor is already driving a Run in."""
    supervision(monkeypatch)

    assert run(repo, "--branch", "TASK-8546") == 0

    (queued,) = queue_of(home).all()
    assert queued.task == "add dark mode"
    assert queued.target_repo == repo
    assert queued.working_branch == "TASK-8546"
    assert no_tmux.spawned == []
    assert RunStore(home / "runs").all() == []


def test_running_records_every_field_it_was_given(home, repo, monkeypatch):
    """An Entry is a Run that does not exist yet, so everything the command used
    to hand kickoff has to reach the Entry instead — `--base` as the pinned base
    a Predecessor is later resolved from."""
    supervision(monkeypatch)

    run(
        repo,
        "--branch",
        "TASK-8546",
        "--base",
        "TASK-8000",
        "--at",
        "implement",
        "--subject",
        "docs/ticket.md",
        "--skip-gates",
    )

    (queued,) = queue_of(home).all()
    assert queued.pinned_base == "TASK-8000"
    assert queued.start_state == "implement"
    assert queued.subject == "docs/ticket.md"
    assert queued.skip_gates is True


def test_running_appends_rather_than_jumping_the_queue(home, repo, monkeypatch):
    """It stopped meaning 'start this now' the moment a Queue existed, and the
    honest place for that to show is where the Entry lands."""
    supervision(monkeypatch)
    main(
        [
            "queue",
            "add",
            str(repo / "workflow.toml"),
            "an earlier task",
            "--repo",
            str(repo),
            "--branch",
            "TASK-8000",
        ]
    )

    run(repo, "--branch", "TASK-8546")

    assert [queued.task for queued in queue_of(home).all()] == [
        "an earlier task",
        "add dark mode",
    ]


# The kickoff-time refusals, now at enqueue: nothing queued and nothing started.


def test_running_without_a_working_branch_queues_branchless_work(home, repo, monkeypatch):
    """Omission is intent: the Entry records no Working branch, and
    the agent at the head of its Run derives and declares one there."""
    supervision(monkeypatch)

    assert run(repo) == 0

    (queued,) = queue_of(home).all()
    assert queued.working_branch is None


def test_running_with_only_a_subject_takes_it_as_the_task(home, repo, monkeypatch):
    """`naiad run <workflow> --at implement --subject <ticket>` needs
    no task beside the Subject — the Subject stands in as the task."""
    supervision(monkeypatch)

    assert (
        main(
            [
                "run",
                str(repo / "workflow.toml"),
                "--repo",
                str(repo),
                "--at",
                "implement",
                "--subject",
                "docs/ticket.md",
            ]
        )
        == 0
    )

    (queued,) = queue_of(home).all()
    assert queued.task == "docs/ticket.md"
    assert queued.subject == "docs/ticket.md"


def test_running_with_neither_a_task_nor_a_subject_is_refused(home, repo, monkeypatch, capsys):
    refuse_supervising(monkeypatch)

    assert main(["run", str(repo / "workflow.toml"), "--repo", str(repo)]) == 2

    err = capsys.readouterr().err
    assert "--subject" in err
    # The remedy speaks this command's vocabulary, not queue add's.
    assert "naiad run" in err
    assert queue_of(home).all() == []


def test_running_at_a_state_the_workflow_does_not_declare_is_refused(
    home, repo, monkeypatch, capsys
):
    refuse_supervising(monkeypatch)

    assert run(repo, "--branch", "TASK-8546", "--at", "grrill") == 2

    assert "grrill" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_running_at_a_state_whose_prompt_names_a_subject_without_one_is_refused(
    home, repo, monkeypatch, capsys
):
    refuse_supervising(monkeypatch)

    assert run(repo, "--branch", "TASK-8546", "--at", "implement") == 2

    assert "--subject" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_running_a_workflow_that_cannot_be_read_is_refused(home, repo, monkeypatch, capsys):
    """The last of the four, and the one that used to be found at kickoff: a
    Workflow that will not parse is read now rather than at three in the
    morning, when nobody is standing at the terminal to retype it."""
    refuse_supervising(monkeypatch)
    (repo / "workflow.toml").write_text("name = ")

    assert run(repo, "--branch", "TASK-8546") == 2

    assert "workflow.toml" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_running_on_a_branch_another_entry_claims_is_refused(home, repo, monkeypatch, capsys):
    supervision(monkeypatch)
    run(repo, "--branch", "TASK-8546")

    refuse_supervising(monkeypatch)
    assert run(repo, "--branch", "TASK-8546") == 2

    assert "TASK-8546" in capsys.readouterr().err
    assert len(queue_of(home).all()) == 1


# Become: nothing is supervising, so this process does, in the foreground.


def test_running_with_nothing_supervising_becomes_the_supervisor(home, repo, monkeypatch):
    """A cold terminal is one command where it used to be two, and what it
    supervises is the Queue the Entry just landed in."""
    wiring = supervision(monkeypatch)

    assert run(repo, "--branch", "TASK-8546") == 0

    assert [queued.task for queued in wiring["queue"].all()] == ["add dark mode"]


def test_becoming_the_supervisor_drains_rather_than_follows(home, repo, monkeypatch):
    """The operator gets their prompt back rather than having to remember to
    interrupt something that has finished the work."""
    wiring = supervision(monkeypatch)

    run(repo, "--branch", "TASK-8546")

    assert wiring["following"] is False


def test_the_lock_is_held_for_as_long_as_it_supervises(home, repo, monkeypatch):
    """What makes one-at-a-time structural: while this one drives the Queue, a
    second is refused and every other `naiad run` merely enqueues."""
    lock = SupervisorLock(home / "supervisor.lock")
    wiring = supervision(monkeypatch, then=lock.held)

    run(repo, "--branch", "TASK-8546")

    assert wiring["during"] is True
    assert lock.held() is False


def test_the_lock_is_released_when_the_supervisor_is_interrupted(home, repo, monkeypatch):
    """Ctrl-C is how an operator stops the night, and the kernel releasing the
    lock is why there is nothing stale to reconcile afterwards."""

    def interrupted(**_arguments):
        raise KeyboardInterrupt

    monkeypatch.setattr("naiad.cli.main.supervise_queue", interrupted)

    assert run(repo, "--branch", "TASK-8546") == 0
    assert SupervisorLock(home / "supervisor.lock").held() is False


# Adopt: something is already supervising, so this is a fire-and-forget enqueue.


def test_running_while_a_supervisor_holds_the_lock_returns_immediately(
    home, repo, supervised, monkeypatch, capsys
):
    """Adding work never blocks on work already running — which is what an
    agent inside a session needs, since a session cannot host a process that
    blocks for hours."""
    refuse_supervising(monkeypatch)

    assert run(repo, "--branch", "TASK-8546") == 0

    (queued,) = queue_of(home).all()
    assert queued.id in capsys.readouterr().out
    assert queued.run_id is None
