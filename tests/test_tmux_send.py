"""What a Prompt becomes on its way into the TUI's input box.

A Prompt that opens with a slash command only runs that skill if Claude Code
reads it as a command, and Claude Code reads a command only out of typed input:
bracketed paste arrives as `[Pasted text #1]` and is submitted as prose. So
every Prompt is typed, and the newlines inside it are typed too.
"""

from naiad.adapters.tmux import keystrokes_for


def test_a_single_line_is_typed_literally():
    assert keystrokes_for("%1", "/clear") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "/clear"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_newline_is_typed_as_alt_enter_so_the_prompt_is_not_submitted_early():
    assert keystrokes_for("%1", "first\nsecond") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "first"],
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "-l", "second"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_blank_line_between_paragraphs_is_two_newlines_and_nothing_typed_between():
    assert keystrokes_for("%1", "one\n\ntwo") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "one"],
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "-l", "two"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_long_prompt_is_still_typed_rather_than_pasted():
    """The old threshold pasted anything past 200 characters, which is where
    every skill-invoking Prompt in the shipped Workflow sat."""
    prompt = "/implement the ticket at " + "x" * 400

    typed = [argv for argv in keystrokes_for("%1", prompt) if "-l" in argv]

    assert typed == [["tmux", "send-keys", "-t", "%1", "-l", prompt]]
    assert not any("paste-buffer" in argv for argv in keystrokes_for("%1", prompt))


def test_a_prompt_opening_with_a_newline_still_types_it():
    """The blank line is what a Prompt's leading newline is for, and counting
    what has been typed so far rather than the position would swallow it."""
    assert keystrokes_for("%1", "\n/implement") == [
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "-l", "/implement"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]


def test_a_prompt_ending_in_a_newline_does_not_type_a_trailing_empty_segment():
    assert keystrokes_for("%1", "done\n") == [
        ["tmux", "send-keys", "-t", "%1", "-l", "done"],
        ["tmux", "send-keys", "-t", "%1", "M-Enter"],
        ["tmux", "send-keys", "-t", "%1", "Enter"],
    ]
