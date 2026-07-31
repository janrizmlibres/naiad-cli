import json
from datetime import datetime, timezone
from pathlib import Path

from naiad.cli.main import _run_id, main
from naiad.runtime.run import default_runs_root

STARTED = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


def test_runs_live_under_the_operators_naiad_directory(monkeypatch):
    monkeypatch.delenv("NAIAD_HOME", raising=False)

    assert default_runs_root() == Path.home() / ".naiad" / "runs"


def test_the_naiad_directory_can_be_moved(monkeypatch, tmp_path):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "elsewhere"))

    assert default_runs_root() == tmp_path / "elsewhere" / "runs"


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
    workflow = tmp_path / "workflow.toml"
    workflow.write_text(
        'name = "w"\n'
        "[[states]]\nname = 'grill'\nprompt = '/grill'\n"
        "[[states]]\nname = 'done'\nterminal = true\n"
    )

    assert main(["run", str(workflow), "a task", "--repo", str(tmp_path), "--at", "grrill"]) == 2

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


def test_run_ids_of_concurrent_runs_differ():
    """Two Runs of the same Workflow in the same second must not collide, since
    a reused id is refused by the store."""
    same_second = _run_id(STARTED, Path("/repo/w.toml"))

    assert same_second != "20260719-120000-w"
    assert same_second.rsplit("-", 1)[-1].isdigit()
