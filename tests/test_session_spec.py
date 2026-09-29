from pathlib import Path

from naiad.adapters.tmux import command_for
from naiad.domain.session import SessionSpec, session_name


def spec(**overrides):
    fields = dict(
        name="naiad-one",
        cwd=Path("/repo"),
        claude_session_id="sess-1",
        initial_prompt="do the work",
    )
    fields.update(overrides)
    return SessionSpec(**fields)


def test_a_session_runs_in_bypass_permissions_mode_by_default():
    assert spec().permission_mode == "bypassPermissions"


def test_the_session_is_named_after_the_run():
    assert session_name("20260719-120000-feature") == "naiad-20260719-120000-feature"


def test_the_command_asks_for_bypass_permissions_mode():
    argv = command_for(spec())

    assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"


def test_the_command_pins_the_claude_session_id():
    argv = command_for(spec())

    assert argv[argv.index("--session-id") + 1] == "sess-1"


def test_a_detached_session_is_created_in_the_target_repository():
    argv = command_for(spec())

    assert argv[:2] == ["tmux", "new-session"]
    assert "-d" in argv
    assert argv[argv.index("-c") + 1] == "/repo"


def test_the_run_is_named_in_the_sessions_environment():
    argv = command_for(spec(environ={"NAIAD_RUN_ID": "one"}))

    assert ["-e", "NAIAD_RUN_ID=one"] == argv[argv.index("-e") : argv.index("-e") + 2]


def test_the_pane_id_is_reported_back():
    argv = command_for(spec())

    assert "-P" in argv
    assert argv[argv.index("-F") + 1] == "#{pane_id}"


def test_the_first_prompt_is_carried_into_the_session_as_it_starts():
    argv = command_for(spec(initial_prompt="/grill add dark mode"))

    assert argv[-1] == "/grill add dark mode"


def test_a_session_with_nothing_to_deliver_carries_no_prompt():
    argv = command_for(spec(initial_prompt=None))

    assert argv[-1] == "sess-1"


def test_the_first_states_model_and_effort_ride_as_launch_flags():
    argv = command_for(spec(model="opus", effort="high"))

    assert argv[argv.index("--model") + 1] == "opus"
    assert argv[argv.index("--effort") + 1] == "high"
    # Flags precede the positional Prompt, which stays last.
    assert argv[-1] == "do the work"


def test_a_session_with_neither_key_passes_no_flags():
    argv = command_for(spec())

    assert "--model" not in argv
    assert "--effort" not in argv


def test_the_compaction_point_rides_as_a_launch_flag():
    """Handed to the flag verbatim: the Session judges the value."""
    argv = command_for(spec(autocompact="200k"))

    assert argv[argv.index("--autocompact") + 1] == "200k"
    assert argv[-1] == "do the work"


def test_a_session_with_no_compaction_point_passes_no_flag():
    argv = command_for(spec())

    assert "--autocompact" not in argv
