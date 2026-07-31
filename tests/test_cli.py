import json
from datetime import datetime, timezone
from pathlib import Path

from naiad.cli.main import _run_id, main

STARTED = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


def _repo(tmp_path):
    """Beside the Naiad home rather than around it, since a run directory
    inside the target repository is refused."""
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _workflow(tmp_path):
    workflow = tmp_path / "workflow.toml"
    workflow.write_text(
        'name = "w"\n'
        "[[states]]\nname = 'grill'\nprompt = '/grill'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )
    return workflow


def test_a_run_id_names_the_workflow_and_when_it_started():
    run_id = _run_id(STARTED, Path("/repo/Matt Pocock Feature.toml"))

    assert run_id.startswith("20260719-120000-matt-pocock-feature-")


def test_watching_a_run_that_does_not_exist_fails_rather_than_watching_another(
    monkeypatch, tmp_path, capsys
):
    """Falling back to whichever Run this session belongs to would silently
    drive a different Run than the one the operator named."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path))
    monkeypatch.setenv("NAIAD_RUN_ID", "some-other-run")

    assert main(["watch", "no-such-run"]) == 2
    assert "no-such-run" in capsys.readouterr().err


def test_starting_at_a_state_the_workflow_does_not_declare_is_refused(
    monkeypatch, tmp_path, capsys
):
    """Refused before a session is created, so the operator reads an error
    naming the valid States rather than watching a run start in the wrong one."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    workflow = _workflow(tmp_path)

    # A branch is supplied so that the refusal under test is the one asserted:
    # a Run started without one is refused first, and for its own reason.
    command = ["run", str(workflow), "a task", "--repo", str(tmp_path)]
    assert main([*command, "--branch", "MC-AGENT-8546", "--at", "grrill"]) == 2

    error = capsys.readouterr().err
    assert "grrill" in error and "grill" in error
    assert not (tmp_path / "naiad" / "runs").exists()


def test_installing_hooks_writes_the_settings_file_the_operator_named(tmp_path, capsys):
    settings = tmp_path / ".claude" / "settings.json"

    assert main(["install-hooks", "--settings", str(settings)]) == 0

    installed = json.loads(settings.read_text())["hooks"]
    assert sorted(entry["matcher"] for entry in installed["SessionStart"]) == [
        "clear",
        "compact",
        "startup",
    ]
    assert str(settings) in capsys.readouterr().out


def test_installing_hooks_over_an_unreadable_settings_file_is_reported_not_a_traceback(
    tmp_path, capsys
):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{ not json")

    assert main(["install-hooks", "--settings", str(settings)]) == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_starting_a_run_without_a_working_branch_is_refused(monkeypatch, tmp_path, capsys):
    """Refused before the Run directory or the session exists, and the error
    names the flag to pass, the way the missing-Subject one names the command
    to retype. Naiad derives no branch name (ADR 0015)."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    workflow = _workflow(tmp_path)

    assert main(["run", str(workflow), "a task", "--repo", str(tmp_path)]) == 2

    assert "--branch" in capsys.readouterr().err
    assert not (tmp_path / "naiad" / "runs").exists()


def test_the_working_branch_and_the_pinned_base_reach_the_run(monkeypatch, tmp_path, sessions):
    """`--base` names what the work stands on; the Run records it as its
    Predecessor, verbatim and unread."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    monkeypatch.setattr("naiad.cli.main.TmuxSessions", lambda: sessions)
    workflow = _workflow(tmp_path)

    code = main(
        [
            "run",
            str(workflow),
            "a task",
            "--repo",
            str(_repo(tmp_path)),
            "--branch",
            "MC-AGENT-8546",
            "--base",
            "MC-AGENT-8000",
        ]
    )

    assert code == 0
    (metadata,) = (tmp_path / "naiad" / "runs").glob("*/run.json")
    recorded = json.loads(metadata.read_text())
    assert recorded["working_branch"] == "MC-AGENT-8546"
    assert recorded["predecessor"] == "MC-AGENT-8000"


def test_a_run_started_with_no_pinned_base_has_no_predecessor(monkeypatch, tmp_path, sessions):
    """The Predecessor is optional: work that stands on nothing is ordinary."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    monkeypatch.setattr("naiad.cli.main.TmuxSessions", lambda: sessions)
    workflow = _workflow(tmp_path)

    code = main(
        [
            "run",
            str(workflow),
            "a task",
            "--repo",
            str(_repo(tmp_path)),
            "--branch",
            "MC-AGENT-8546",
        ]
    )

    assert code == 0
    (metadata,) = (tmp_path / "naiad" / "runs").glob("*/run.json")
    assert json.loads(metadata.read_text())["predecessor"] is None


def test_run_ids_of_concurrent_runs_differ():
    """Two Runs of the same Workflow in the same second must not collide, since
    a reused id is refused by the store."""
    same_second = _run_id(STARTED, Path("/repo/w.toml"))

    assert same_second != "20260719-120000-w"
    assert same_second.rsplit("-", 1)[-1].isdigit()
