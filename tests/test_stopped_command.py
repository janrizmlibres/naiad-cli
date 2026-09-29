"""The Stop hook as a session meets it: which record a Turn end lands in.

Ordinarily the Run's own turns record; through an Adoption's gap, the sidecar
beside the Entry that will become it; with neither, nowhere — the
hook is installed machine-wide and a pane nobody adopted stays silent.
"""

import pytest

from naiad.cli.main import main
from naiad.domain.entry import Attachment, Entry
from naiad.runtime.queue import Queue
from naiad.runtime.records import EntryTurns, Turns
from naiad.runtime.run import RunStore


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    monkeypatch.delenv("NAIAD_RUN_ID", raising=False)
    return tmp_path / "naiad"


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    return path


@pytest.fixture
def pane(monkeypatch):
    monkeypatch.setenv("TMUX_PANE", "%264")
    return "%264"


def adopted_entry(repo, *, pane):
    return Entry(
        id="20260808-075254-753384-matt-pocock-58418",
        workflow_path=repo / "w.toml",
        task="retire the analytics sub-agent",
        target_repo=repo,
        working_branch=None,
        created_at="2026-08-08T07:52:54Z",
        attachment=Attachment(tmux_pane=pane),
    )


def test_a_turn_ending_in_the_gap_lands_beside_the_entry(home, repo, pane):
    entry = Queue(home / "queue").add(adopted_entry(repo, pane=pane))

    assert main(["stopped"]) == 0
    assert EntryTurns(home / "queue", entry.id).count() == 1


def test_a_turn_ending_in_a_pane_nobody_adopted_records_nothing(home, repo, pane):
    assert main(["stopped"]) == 0
    assert not (home / "queue").exists()


def test_a_turn_ending_in_a_live_runs_pane_still_lands_in_the_run(home, repo, pane):
    """The Entry stands in only through the gap: once the Run answers for the
    pane, the Turn end is the Run's, exactly as before."""
    entry = Queue(home / "queue").add(adopted_entry(repo, pane=pane))
    run = RunStore(home / "runs").create(
        run_id="r1",
        workflow_path=repo / "w.toml",
        task="t",
        target_repo=repo,
        created_at="2026-08-08T07:53:30Z",
    )
    run.attach_session(tmux_session="gp", tmux_pane=pane)

    assert main(["stopped"]) == 0
    assert Turns(run.root).ended_since(None) is True
    assert EntryTurns(home / "queue", entry.id).count() == 0


def test_a_damaged_entry_does_not_crash_the_hook(home, repo, pane, capsys):
    """The hook is installed machine-wide and fires on every turn end; a queue
    file an operator truncated is a command's refusal to report, never a
    traceback out of every session on the machine."""
    (home / "queue").mkdir(parents=True)
    (home / "queue" / "20260808-000000-broken.json").write_text("{ not json")

    assert main(["stopped"]) == 0


def test_a_stop_that_races_the_attach_still_lands_in_the_run(home, repo, pane, monkeypatch):
    """The reverse interleaving of relocation's write-if-absent:
    the hook resolved the Entry, the Supervisor then created the Run and
    relocated an absent sidecar, and only then did the hook's write land. The
    hook re-resolves after writing and performs the same move itself, so the
    turn end reaches the Run from whichever side acted last."""
    entry = Queue(home / "queue").add(adopted_entry(repo, pane=pane))
    store = RunStore(home / "runs")
    import naiad.cli.main as cli_main

    class RacingEntryTurns(EntryTurns):
        def record_end(self):
            # The Supervisor's whole attach happens between this hook resolving
            # the Entry and its write landing: the Run appears, answers for the
            # pane, and relocation finds no sidecar to move.
            run = store.create(
                run_id="r1",
                workflow_path=repo / "w.toml",
                task="t",
                target_repo=repo,
                created_at="2026-08-08T07:53:30Z",
            )
            run.attach_session(tmux_session="gp", tmux_pane="%264")
            EntryTurns(self.path.parent, entry.id).relocate_into(run.root)
            super().record_end()

    monkeypatch.setattr(cli_main, "EntryTurns", RacingEntryTurns)

    assert main(["stopped"]) == 0

    run = store.load("r1")
    assert Turns(run.root).ended_since(None) is True
    assert not EntryTurns(home / "queue", entry.id).path.exists()
