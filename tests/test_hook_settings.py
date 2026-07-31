"""The settings document that puts Naiad's hooks in front of every session.

The document is plain data, so the rules about it — which moments are covered,
that installing twice is not installing twice, that another tool's hooks
survive — are tested here rather than by inspecting a real settings file.
"""

import pytest

from naiad.hooks.settings import SESSION_START_MATCHERS, with_naiad_hooks

COMMAND = "/opt/naiad/bin/naiad"


@pytest.fixture
def installed():
    return with_naiad_hooks({}, naiad=COMMAND)


def commands_for(settings, event, matcher=None):
    return [
        hook["command"]
        for entry in settings["hooks"].get(event, [])
        if entry.get("matcher") == matcher
        for hook in entry["hooks"]
    ]


def test_the_protocol_is_injected_when_a_session_starts(installed):
    assert commands_for(installed, "SessionStart", "startup") == [f"{COMMAND} protocol"]


def test_the_protocol_is_injected_after_a_clear(installed):
    """A Run Clears between loop iterations, so this is the common case rather
    than the exotic one."""
    assert commands_for(installed, "SessionStart", "clear") == [f"{COMMAND} protocol"]


def test_the_protocol_is_injected_after_a_compaction(installed):
    """Compaction strikes unannounced mid-phase; an agent that loses the
    Protocol to it falls silent and the Run dies quietly."""
    assert commands_for(installed, "SessionStart", "compact") == [f"{COMMAND} protocol"]


def test_each_moment_is_its_own_entry_rather_than_one_alternation(installed):
    """Alternation is documented for tool-name matchers, not for SessionStart
    sources, and Naiad depends only on documented surfaces."""
    matchers = [entry["matcher"] for entry in installed["hooks"]["SessionStart"]]

    assert sorted(matchers) == sorted(SESSION_START_MATCHERS)


def test_the_turn_ending_hook_is_installed_without_a_matcher(installed):
    """Stop takes no matcher — it fires whenever the agent finishes."""
    assert commands_for(installed, "Stop") == [f"{COMMAND} stopped"]


def test_installing_twice_installs_one_set_of_hooks(installed):
    assert with_naiad_hooks(installed, naiad=COMMAND) == installed


def test_a_naiad_installed_elsewhere_replaces_the_old_entry_rather_than_joining_it(installed):
    """Two naiads racing to answer the same hook would deliver two Protocols
    and record every turn twice."""
    moved = with_naiad_hooks(installed, naiad="/usr/local/bin/naiad")

    assert commands_for(moved, "Stop") == ["/usr/local/bin/naiad stopped"]
    assert commands_for(moved, "SessionStart", "clear") == ["/usr/local/bin/naiad protocol"]


def test_another_tools_hooks_are_left_alone():
    existing = {
        "hooks": {
            "SessionStart": [{"matcher": "startup", "hooks": [{"command": "somebody else"}]}],
            "Stop": [{"hooks": [{"command": "somebody else"}]}],
            "PreToolUse": [{"matcher": "Write", "hooks": [{"command": "a linter"}]}],
        }
    }

    merged = with_naiad_hooks(existing, naiad=COMMAND)

    assert "somebody else" in commands_for(merged, "SessionStart", "startup")
    assert "somebody else" in commands_for(merged, "Stop")
    assert commands_for(merged, "PreToolUse", "Write") == ["a linter"]


def test_settings_that_are_nothing_to_do_with_hooks_survive():
    merged = with_naiad_hooks({"model": "opus", "env": {"FOO": "1"}}, naiad=COMMAND)

    assert merged["model"] == "opus"
    assert merged["env"] == {"FOO": "1"}


def test_the_operators_settings_are_not_mutated_in_place():
    """Merging is a pure transformation; a caller that decides not to write
    must still hold what it read."""
    existing = {"hooks": {"Stop": [{"hooks": [{"command": "somebody else"}]}]}}

    with_naiad_hooks(existing, naiad=COMMAND)

    assert existing == {"hooks": {"Stop": [{"hooks": [{"command": "somebody else"}]}]}}


def test_every_installed_hook_is_a_command_hook(installed):
    for entries in installed["hooks"].values():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["type"] == "command"
