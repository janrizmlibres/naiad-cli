"""The entry point's odds and ends: how a Run is named, driving one by name, and
installing the hooks.

`naiad run` has its own file (tests/test_run_command.py) now that it is one
entrance to the Queue rather than a way to spawn a session, and the Queue's
commands have theirs (tests/test_queue_command.py).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from naiad.adapters.lock import SupervisorLock
from naiad.cli.main import _run_id, main

STARTED = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


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


def test_watching_a_run_while_a_supervisor_holds_the_lock_is_refused(
    monkeypatch, tmp_path, capsys
):
    """The Queue is sequential, so a held lock means the Supervisor is driving
    the only live Run — and two tickers on one Run deliver everything twice."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    monkeypatch.setenv("NAIAD_RUN_ID", "a-run")

    with SupervisorLock(tmp_path / "naiad" / "supervisor.lock").taken() as mine:
        assert mine
        assert main(["watch"]) == 2

    assert "supervisor" in capsys.readouterr().err


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
