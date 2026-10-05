"""A terminal for a test to print to, and a way to read what a line was styled.

The suite runs off a terminal, so every line it reads is plain; a test about
colour replaces the stream with one that says it is a terminal. That happens
inside the test rather than in a fixture, because the capture resets stdout and
stderr between a fixture and the test body.
"""

import io
import sys

from rich.text import Text

from naiad.cli.style import styled

ESCAPE = "\x1b["


class Terminal(io.StringIO):
    """A stream that says it is a terminal, as the operator's is."""

    def isatty(self):
        return True


def to_terminal(monkeypatch, *, stream="stdout"):
    """stdout, or stderr, replaced by a terminal."""
    terminal = Terminal()
    monkeypatch.setattr(sys, stream, terminal)
    return terminal


def styles_of(line: str | Text) -> dict[str, str]:
    """Each styled piece of a line, by its words, with the style it carries."""
    text = line if isinstance(line, Text) else styled(line)
    return {text.plain[span.start : span.end]: str(span.style) for span in text.spans}
