"""The entry point's odds and ends: how a Run is named, driving one by name, and
installing into the operator's Claude configuration.

`naiad run` has its own file (tests/test_run_command.py) now that it is one
entrance to the Queue rather than a way to spawn a session, and the Queue's
commands have theirs (tests/test_queue_command.py).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from naiad.adapters.lock import SupervisorLock
from naiad.cli.main import _run_id, build_parser, main

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


def test_the_parser_is_built_without_running_a_command(monkeypatch, tmp_path):
    """Reading the command tree must not execute a handler."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path))

    arguments = build_parser().parse_args(["announce", "grill", "--subject", "01-a.md"])

    assert arguments.name == "grill"
    assert arguments.subject == "01-a.md"
    assert not (tmp_path / "runs").exists()


def test_the_old_announce_spelling_is_not_in_the_command_tree(capsys):
    """`state` is the authoring noun now, and a State's name is not one of its
    verbs, so the old spelling of an announcement reaches no handler."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["state", "grill"])

    assert "invalid choice: 'grill'" in capsys.readouterr().err


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


def _install(tmp_path, *arguments):
    """Installing into a configuration of the operator's that is this test's."""
    return [
        "install",
        "--settings",
        str(tmp_path / ".claude" / "settings.json"),
        "--skills",
        str(tmp_path / ".claude" / "skills"),
        *arguments,
    ]


def test_installing_writes_the_settings_file_the_operator_named(tmp_path, capsys):
    settings = tmp_path / ".claude" / "settings.json"

    assert main(_install(tmp_path)) == 0

    installed = json.loads(settings.read_text())["hooks"]
    assert sorted(entry["matcher"] for entry in installed["SessionStart"]) == [
        "clear",
        "compact",
        "startup",
    ]
    assert str(settings) in capsys.readouterr().out


def test_installing_ships_the_adopt_skill_beside_the_hooks(tmp_path, capsys):
    """One command for the machine's whole setup: an operator who installed the
    hooks and not the skill has a naiad the operator's intent cannot reach."""
    skill = tmp_path / ".claude" / "skills" / "naiad-adopt" / "SKILL.md"

    assert main(_install(tmp_path)) == 0

    # That the skill arrived, and nothing about what it says: its contents are
    # tests/test_adopt_skill.py's, and the naiad it names is whichever one
    # installed it rather than a string this test could predict.
    assert "name: naiad-adopt" in skill.read_text()
    assert str(skill) in capsys.readouterr().out


def test_a_bare_install_leaves_the_library_alone(monkeypatch, tmp_path, capsys):
    """The library is the operator's store: install touches it only
    when asked, so re-running install without thinking can never reach it."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    library = tmp_path / "naiad" / "workflows"
    library.mkdir(parents=True)
    (library / "mine.toml").write_text("their own workflow\n")
    before = {path.name: path.read_bytes() for path in library.iterdir()}

    assert main(_install(tmp_path)) == 0

    assert {path.name: path.read_bytes() for path in library.iterdir()} == before
    assert "installed the starter" not in capsys.readouterr().out


def test_a_bare_install_does_not_create_the_library(monkeypatch, tmp_path):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))

    assert main(_install(tmp_path)) == 0

    assert not (tmp_path / "naiad" / "workflows").exists()


def test_installing_the_starter_writes_a_regular_file_the_name_resolves(
    monkeypatch, tmp_path, capsys, sessions
):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    monkeypatch.setattr("naiad.cli.main.TmuxSessions", lambda: sessions)
    entry = tmp_path / "naiad" / "workflows" / "starter.toml"
    repo = tmp_path / "repo"
    repo.mkdir()

    assert main(_install(tmp_path, "--starter")) == 0

    assert entry.is_file() and not entry.is_symlink()
    assert str(entry) in capsys.readouterr().out
    assert main(["queue", "add", "starter", "a task", "--repo", str(repo)]) == 0


def test_installing_the_starter_over_an_edited_one_is_refused_and_says_how_to_go_on(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    theirs = tmp_path / "naiad" / "workflows" / "starter.toml"
    theirs.parent.mkdir(parents=True)
    theirs.write_text("my edits\n")

    assert main(_install(tmp_path, "--starter")) == 2

    printed = capsys.readouterr()
    assert "starter.toml differs from the shipped starter; pass --force" in printed.err
    assert "hooks" in printed.out
    assert theirs.read_text() == "my edits\n"


def test_force_overwrites_an_edited_starter(monkeypatch, tmp_path):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    theirs = tmp_path / "naiad" / "workflows" / "starter.toml"
    theirs.parent.mkdir(parents=True)
    theirs.write_text("my edits\n")

    assert main(_install(tmp_path, "--starter", "--force")) == 0

    assert theirs.read_text() != "my edits\n"


def test_force_without_the_starter_has_nothing_to_force(tmp_path, capsys):
    assert main(_install(tmp_path, "--force")) == 2

    printed = capsys.readouterr()
    assert "--starter" in printed.err
    assert not (tmp_path / ".claude" / "settings.json").exists()


def test_install_follows_the_claude_config_dir_when_it_is_set(monkeypatch, tmp_path):
    """The hooks and the skill land where Claude Code itself reads, which the
    variable moves; naming neither option is the case this is about."""
    configuration = tmp_path / "work-account"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(configuration))

    assert main(["install"]) == 0

    assert "hooks" in json.loads((configuration / "settings.json").read_text())
    assert (configuration / "skills" / "naiad-adopt" / "SKILL.md").is_file()


def test_install_without_the_variable_installs_under_dot_claude_in_the_home(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert main(["install"]) == 0

    assert "hooks" in json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert (tmp_path / ".claude" / "skills" / "naiad-adopt" / "SKILL.md").is_file()


def test_the_settings_and_skills_options_still_win_over_the_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "from-the-variable"))

    assert main(_install(tmp_path)) == 0

    assert (tmp_path / ".claude" / "settings.json").is_file()
    assert not (tmp_path / "from-the-variable").exists()


def test_installing_over_an_unreadable_settings_file_is_reported_not_a_traceback(
    tmp_path, capsys
):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{ not json")

    assert main(_install(tmp_path)) == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_installing_over_a_skill_naiad_did_not_write_is_reported_not_a_traceback(
    tmp_path, capsys
):
    """And what the hooks did is said before the refusal, because they were
    installed: an operator told only that something was refused would not know
    which half of the command had already happened."""
    theirs = tmp_path / ".claude" / "skills" / "naiad-adopt" / "SKILL.md"
    theirs.parent.mkdir(parents=True)
    theirs.write_text("my own adopt notes\n")

    assert main(_install(tmp_path)) == 2

    printed = capsys.readouterr()
    assert "refusing to overwrite" in printed.err
    assert "hooks" in printed.out
    assert "hooks" in json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert theirs.read_text() == "my own adopt notes\n"


def test_run_ids_of_concurrent_runs_differ():
    """Two Runs of the same Workflow in the same second must not collide, since
    a reused id is refused by the store."""
    same_second = _run_id(STARTED, Path("/repo/w.toml"))

    assert same_second != "20260719-120000-w"
    assert same_second.rsplit("-", 1)[-1].isdigit()
