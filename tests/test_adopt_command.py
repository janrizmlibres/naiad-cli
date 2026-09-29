"""`naiad adopt` as the agent inside a live session meets it: what lands on the
Queue, what is printed back, and what is refused while the human is still there.

The command validates, enqueues, prints and exits (ADR 0014) — the Run is attached
by the Supervisor, on its ordinary pass — so nothing here may spawn a session or
start a Run. The output is the whole of what a hitherto-undriven agent learns,
which makes its absences the silent failures: an agent that never read the
Protocol cannot announce, and the Run dies quietly.
"""

import pytest

from naiad.adapters.executable import naiad_command
from naiad.adapters.lock import SupervisorLock
from naiad.cli.main import main
from naiad.domain.entry import Attachment
from naiad.runtime.queue import Queue
from naiad.runtime.run import RunStore

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "spec"
prompt = "/to-spec"

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
def adopting_pane(monkeypatch):
    """The pane the adopting process stands in, which is where the session
    being adopted lives. Set for every test but the ones asserting its absence,
    which unset it themselves."""
    monkeypatch.setenv("TMUX_PANE", "%42")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)


@pytest.fixture(autouse=True)
def no_tmux(monkeypatch, sessions):
    """Nothing in this file may open a session — the whole point of an Adoption
    is that a session already exists. Wired for every test so that a command
    which tried to would be caught rather than reaching real tmux."""
    monkeypatch.setattr("naiad.cli.main.TmuxSessions", lambda: sessions)
    return sessions


@pytest.fixture
def supervised(home):
    """A Supervisor already holding the lock, without a second process."""
    with SupervisorLock(home / "supervisor.lock").taken() as mine:
        assert mine
        yield


def queue_of(home):
    return Queue(home / "queue")


def adopt(repo, *arguments, workflow=None):
    return main(
        [
            "adopt",
            workflow if workflow is not None else str(repo / "workflow.toml"),
            "--repo",
            str(repo),
            "--at",
            "spec",
            "--task",
            "the audit log design",
            *arguments,
        ]
    )


# The Entry: an Adoption is an ordinary Entry carrying one extra mark.


def test_adopting_queues_an_entry_marked_with_the_session_to_attach_to(home, repo, capsys):
    assert adopt(repo) == 0

    (queued,) = queue_of(home).all()
    assert queued.attachment == Attachment(tmux_pane="%42")
    assert queued.start_state == "spec"
    assert queued.target_repo == repo
    assert queued.id in capsys.readouterr().out


def test_adopting_records_the_claude_session_id_when_it_can_be_gathered(
    home, repo, monkeypatch
):
    """A second key for the resolution seam. The pane is the reliable one, so
    the id is recorded when the session exports it and never insisted on."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "a-session")

    assert adopt(repo) == 0

    assert queue_of(home).all()[0].attachment == Attachment(
        tmux_pane="%42", claude_session_id="a-session"
    )


def test_the_task_the_agent_distilled_becomes_the_entrys_task(home, repo):
    """The agent writes it, being the one party holding the conversation the
    operator's intent came out of (ADR 0028)."""
    adopt(repo)

    assert queue_of(home).all()[0].task == "the audit log design"


def test_adopting_records_every_describer_it_was_given(home, repo):
    adopt(
        repo,
        "--branch",
        "MC-AGENT-8546",
        "--base",
        "MC-AGENT-8000",
        "--skip-gates",
    )

    (queued,) = queue_of(home).all()
    assert queued.working_branch == "MC-AGENT-8546"
    assert queued.pinned_base == "MC-AGENT-8000"
    assert queued.skip_gates is True


def test_adopting_supervises_nothing_and_starts_nothing(home, repo, no_tmux):
    """A tool call that became a process blocking for hours is the failure the
    Queue exists to avoid, and attaching the Run is the Supervisor's alone."""
    assert adopt(repo) == 0

    assert no_tmux.spawned == []
    assert RunStore(home / "runs").all() == []
    assert queue_of(home).all()[0].run_id is None


def test_an_adoption_takes_its_place_in_the_queue_rather_than_jumping_it(home, repo):
    """It waits its Lane turn like any Entry, so a Run already live in that
    working tree is never typed over (ADR 0028)."""
    main(
        [
            "queue",
            "add",
            str(repo / "workflow.toml"),
            "an earlier task",
            "--repo",
            str(repo),
            "--branch",
            "MC-AGENT-8000",
        ]
    )

    adopt(repo)

    assert [queued.task for queued in queue_of(home).all()] == [
        "an earlier task",
        "the audit log design",
    ]


def test_an_adoption_is_listed_like_any_other_entry(home, repo, capsys):
    adopt(repo)
    (queued,) = queue_of(home).all()
    capsys.readouterr()

    assert main(["queue", "list"]) == 0

    printed = capsys.readouterr().out
    assert queued.id in printed
    assert "the audit log design" in printed


def test_removing_an_adoption_leaves_the_session_untouched(home, repo, no_tmux):
    """Changing one's mind before the Run is attached costs nothing: removal
    is a Queue operation, and the session was never Naiad's to begin with."""
    adopt(repo)
    (queued,) = queue_of(home).all()

    assert main(["queue", "rm", queued.id]) == 0

    assert queue_of(home).all() == []
    assert no_tmux.spawned == []


# tmux only, for now: delivery is typing into a pane.


def test_adopting_outside_tmux_is_refused_naming_the_constraint(
    home, repo, monkeypatch, capsys
):
    monkeypatch.delenv("TMUX_PANE", raising=False)

    assert adopt(repo) == 2

    assert "tmux" in capsys.readouterr().err
    assert queue_of(home).all() == []


# The refusals check_start makes, fired here while the human is still standing
# at the session rather than hours later, when the Supervisor attaches the Run.


def test_adopting_at_a_state_the_workflow_does_not_declare_is_refused(home, repo, capsys):
    assert main(
        [
            "adopt",
            str(repo / "workflow.toml"),
            "--repo",
            str(repo),
            "--at",
            "spek",
            "--task",
            "the audit log design",
        ]
    ) == 2

    assert "spek" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_adopting_at_a_state_whose_prompt_names_a_subject_without_one_is_refused(
    home, repo, capsys
):
    assert main(
        [
            "adopt",
            str(repo / "workflow.toml"),
            "--repo",
            str(repo),
            "--at",
            "implement",
            "--task",
            "the audit log design",
        ]
    ) == 2

    err = capsys.readouterr().err
    assert "--subject" in err
    # The remedy speaks this command's vocabulary, not queue add's.
    assert "naiad adopt" in err
    assert queue_of(home).all() == []


def test_adopting_a_workflow_that_cannot_be_read_is_refused(home, repo, capsys):
    (repo / "workflow.toml").write_text("name = ")

    assert adopt(repo) == 2

    assert "workflow.toml" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_adopting_by_bare_name_queues_the_library_file_of_that_stem(home, repo):
    """The entrances share one resolution, so a bare name is shorthand here
    exactly as it is at `queue add` (ADR 0023)."""
    library = home / "workflows"
    library.mkdir(parents=True)
    (library / "feature.toml").write_text(WORKFLOW)

    assert adopt(repo, workflow="feature") == 0

    assert queue_of(home).all()[0].workflow_path == library / "feature.toml"


def test_adopting_by_a_name_the_library_does_not_hold_is_refused(home, repo, capsys):
    assert adopt(repo, workflow="featuer") == 2

    assert "no workflow named 'featuer'" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_adopting_without_a_task_is_refused(home, repo):
    """There is no Subject stand-in for an Adoption: the operator's words were
    a conversation rather than a line, and only the agent holding it can say
    what the work is (ADR 0028)."""
    with pytest.raises(SystemExit) as refused:
        main(
            [
                "adopt",
                str(repo / "workflow.toml"),
                "--repo",
                str(repo),
                "--at",
                "spec",
                "--subject",
                "docs/ticket.md",
            ]
        )

    assert refused.value.code == 2
    assert queue_of(home).all() == []


# The branch, settled at the act of adopting: both Workflow branch heads are
# behind a mid-Workflow start (ADR 0022, ADR 0028).


def test_adopting_on_a_branch_another_entry_claims_is_refused(home, repo, capsys):
    main(
        [
            "queue",
            "add",
            str(repo / "workflow.toml"),
            "an earlier task",
            "--repo",
            str(repo),
            "--branch",
            "MC-AGENT-8546",
        ]
    )

    assert adopt(repo, "--branch", "MC-AGENT-8546") == 2

    assert "MC-AGENT-8546" in capsys.readouterr().err
    assert len(queue_of(home).all()) == 1


def test_adopting_without_a_branch_queues_branchless_and_claims_nothing(home, repo):
    """Absent one, the Entry claims nothing until the agent declares the name
    it derived (ADR 0022)."""
    assert adopt(repo) == 0
    assert adopt(repo) == 0

    assert [queued.working_branch for queued in queue_of(home).all()] == [None, None]


# The output: everything the hitherto-undriven agent has to be taught.
#
# Held here is that each part of it reaches the agent through the command, and
# that it is composed for *this* Entry and *this* machine — the State it starts
# at, the branch it queued with, whether a Supervisor holds the lock. The
# wording itself belongs to tests/test_protocol.py, which is where a phrase is
# changed; asserting prose in both places would mean tuning it broke two files.


def teaching(repo, capsys, *arguments):
    assert adopt(repo, *arguments) == 0
    return capsys.readouterr().out


def test_the_output_teaches_the_protocol(home, repo, capsys):
    """The manual session never met the SessionStart injection and no Clear
    will fire before the agent must announce.

    The commands are named as the agent must actually type them — this naiad's
    own path — because the session's PATH is whatever the human's shell held
    and need not hold a bare `naiad` at all."""
    printed = teaching(repo, capsys)

    for verb in ("announce", "ask", "wait", "hold"):
        assert f"{naiad_command()} {verb}" in printed


def test_the_output_names_the_state_expected_after_the_one_adopted_at(home, repo, capsys):
    assert "implement" in teaching(repo, capsys)


def test_the_output_closes_by_telling_the_agent_to_end_its_turn(home, repo, capsys):
    printed = teaching(repo, capsys).lower()

    assert "end your turn" in printed
    assert "lane" in printed


def test_the_output_of_a_branchless_adoption_asks_for_a_branch_to_be_declared(
    home, repo, capsys
):
    assert f"{naiad_command()} branch" in teaching(repo, capsys)


def test_the_output_of_an_adoption_carrying_a_branch_names_it_instead(home, repo, capsys):
    """Told to derive one, an agent whose Entry already claims a branch would
    create a second branch for the same work.

    Read from the taught part alone: the queued report names the branch too, so
    asserting over the whole output would pass on that line and say nothing
    about what the agent was actually told."""
    _report, taught = teaching(repo, capsys, "--branch", "MC-AGENT-8546").split(
        "# Naiad protocol", 1
    )

    assert "MC-AGENT-8546" in taught
    assert f"{naiad_command()} branch" not in taught


def test_the_output_warns_when_no_supervisor_will_ever_take_the_entry(home, repo, capsys):
    """A queued Adoption waiting silently forever is what the warning exists to
    prevent; the agent relays the remedy to the human."""
    assert f"{naiad_command()} queue watch" in teaching(repo, capsys)


def test_the_output_carries_no_warning_when_a_supervisor_holds_the_lock(
    home, repo, supervised, capsys
):
    assert f"{naiad_command()} queue watch" not in teaching(repo, capsys)
