"""What a Prompt becomes on its way into the TUI's input box.

A Prompt that opens with a slash command only runs that skill if Claude Code
reads it as a command, and Claude Code reads a command only out of typed input:
bracketed paste arrives as `[Pasted text #1]` and is submitted as prose. So
every Prompt is typed, and the newlines inside it are typed too.
"""

import pytest

from naiad.adapters.tmux import TYPED_PIECE_BYTES, TmuxError, TmuxSessions, keystrokes_for


def test_a_single_line_is_typed_literally():
    assert keystrokes_for("%1", "/clear") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "--", "/clear"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_newline_is_typed_as_alt_enter_so_the_prompt_is_not_submitted_early():
    assert keystrokes_for("%1", "first\nsecond") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "--", "first"],
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "-l", "--", "second"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_blank_line_between_paragraphs_is_two_newlines_and_nothing_typed_between():
    assert keystrokes_for("%1", "one\n\ntwo") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "--", "one"],
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "-l", "--", "two"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_long_prompt_is_still_typed_rather_than_pasted():
    """The old threshold pasted anything past 200 characters, which is where
    every skill-invoking Prompt in the shipped Workflow sat."""
    prompt = "/implement the ticket at " + "x" * 400

    typed = [argv[-1] for argv in keystrokes_for("%1", prompt) if "-l" in argv]

    assert "".join(typed) == prompt
    assert not any("paste-buffer" in argv for argv in keystrokes_for("%1", prompt))


def test_a_long_line_is_typed_in_pieces_the_session_reads_as_typing():
    """One write of a kilobyte or more is read by the Session as a paste: it
    arrives wrapped as pasted content, or with its first 1022 bytes gone —
    which is how the pull-request Prompt reached the Session headless. Pieces of
    TYPED_PIECE_BYTES arrive as typed."""
    line = "word " * 700

    pieces = [argv[-1] for argv in keystrokes_for("%1", line.strip()) if "-l" in argv]

    assert len(pieces) > 1
    assert all(len(piece.encode()) <= TYPED_PIECE_BYTES for piece in pieces)
    assert "".join(pieces) == line.strip()


def test_a_piece_never_splits_a_character():
    """The shipped Prompts are full of em-dashes, three bytes each, and a
    piece cut through one would type two halves of nothing."""
    line = "—" * TYPED_PIECE_BYTES

    pieces = [argv[-1] for argv in keystrokes_for("%1", line) if "-l" in argv]

    assert all(len(piece.encode()) <= TYPED_PIECE_BYTES for piece in pieces)
    assert "".join(pieces) == line


def test_a_prompt_opening_with_a_newline_still_types_it():
    """The blank line is what a Prompt's leading newline is for, and counting
    what has been typed so far rather than the position would swallow it."""
    assert keystrokes_for("%1", "\n/implement") == [
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "-l", "--", "/implement"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_line_opening_with_a_dash_is_typed_rather_than_read_as_a_flag():
    """An Answer that lists its steps as bullets reaches tmux as `-l - step`,
    and tmux reads the bullet as a flag: `invalid flag -`. The `--` is what
    ends tmux's own option parsing, so the line is only ever text."""
    assert keystrokes_for("%1", "- ready-for-agent") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "--", "- ready-for-agent"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_prompt_ending_in_a_newline_does_not_type_a_trailing_empty_segment():
    assert keystrokes_for("%1", "done\n") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "--", "done"],
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def fake_tmux(directory, monkeypatch, *, says, status):
    """A tmux on PATH that records its arguments and answers as told."""
    directory.mkdir()
    script = directory / "tmux"
    script.write_text(
        f'#!/bin/sh\necho "$@" >> "{directory}/argv"\necho "{says}" >&2\nexit {status}\n'
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}:/usr/bin:/bin")
    return directory / "argv"


def test_closing_a_session_kills_the_session_holding_the_pane(tmp_path, monkeypatch):
    argv = fake_tmux(tmp_path / "bin", monkeypatch, says="", status=0)

    TmuxSessions().close("%3")

    assert argv.read_text() == "kill-session -t %3\n"


@pytest.mark.parametrize(
    "says",
    [
        "can't find pane: %3",
        "can't find session: naiad-run-03",
        "no server running on /tmp/tmux-501/default",
        "error connecting to /tmp/tmux-501/default (No such file or directory)",
    ],
)
def test_closing_a_session_already_gone_is_ignored(tmp_path, monkeypatch, says):
    fake_tmux(tmp_path / "bin", monkeypatch, says=says, status=1)

    TmuxSessions().close("%3")


def test_closing_fails_loudly_for_any_other_reason(tmp_path, monkeypatch):
    fake_tmux(tmp_path / "bin", monkeypatch, says="server exited unexpectedly", status=1)

    with pytest.raises(TmuxError):
        TmuxSessions().close("%3")
