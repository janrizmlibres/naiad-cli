"""The UserPromptSubmit hook as a Session meets it: a Prompt Naiad typed that
arrived whole is let through and confirmed, one that arrived cut short is
turned away, and anything else passes untouched (ADR 0053)."""

import io
import json
import time

import pytest

from naiad.cli.main import main
from naiad.domain.announcement import Announcement
from naiad.runtime.records import Deliveries, Submissions
from naiad.runtime.run import RunStore

PROMPT = "Before anything else, work out which repositories this Run's work reached."
GRILL = Announcement(seq=1, state="grill")


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    monkeypatch.delenv("NAIAD_RUN_ID", raising=False)
    monkeypatch.setenv("TMUX_PANE", "%264")
    return tmp_path / "naiad"


@pytest.fixture
def run(home, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    created = RunStore(home / "runs").create(
        run_id="r1",
        workflow_path=repo / "w.toml",
        task="t",
        target_repo=repo,
        created_at="2026-09-24T05:33:30Z",
    )
    created.attach_session(tmux_session="gp", tmux_pane="%264")
    return created


def submit(monkeypatch, prompt):
    payload = {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return main(["submitted"])


def test_the_prompt_naiad_typed_is_let_through_and_confirmed(run, monkeypatch):
    Deliveries(run.root).record_attempt(GRILL, prompt=PROMPT, turns=0, at=time.time())

    assert submit(monkeypatch, PROMPT) == 0
    assert Submissions(run.root).of(GRILL, attempt=1) == "landed"


def test_a_prompt_cut_short_is_turned_away_with_the_reason(run, monkeypatch, capsys):
    """Exit 2 is how a UserPromptSubmit hook blocks the prompt and erases it,
    so the agent never starts on half its State's instructions."""
    Deliveries(run.root).record_attempt(GRILL, prompt=PROMPT, turns=0, at=time.time())

    assert submit(monkeypatch, PROMPT[20:]) == 2
    assert Submissions(run.root).of(GRILL, attempt=1) == "rejected"
    assert "naiad" in capsys.readouterr().err


def test_a_humans_prompt_between_deliveries_passes_untouched(run, monkeypatch, capsys):
    assert submit(monkeypatch, "what happened here?") == 0
    assert capsys.readouterr().out == ""


def test_a_session_nobody_is_driving_passes_untouched(home, monkeypatch):
    assert submit(monkeypatch, "anything") == 0


def test_a_hook_run_with_nothing_on_stdin_passes_untouched(run, monkeypatch):
    Deliveries(run.root).record_attempt(GRILL, prompt=PROMPT, turns=0, at=time.time())
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    assert main(["submitted"]) == 0
    assert Submissions(run.root).of(GRILL, attempt=1) is None
