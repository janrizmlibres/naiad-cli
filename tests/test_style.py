"""How Naiad's output looks: styled for a person at a terminal, plain for
everything else.

The audience decides it. A person at a terminal gets colour; an agent's Bash
tool, a hook and a file all read a stream that is not a terminal, and get the
same characters with no escape codes among them. NO_COLOR is the operator
saying they want none, and it wins over everything.
"""

from typing import get_args

from rich.text import Text

from fake_terminal import ESCAPE, styles_of, to_terminal
from naiad.cli.style import GLYPHS, THEME, Styled, columns, console, refusal, say, status, styled
from naiad.runtime.queue import Status


def test_output_that_is_not_a_terminal_carries_no_escape_codes(capsys):
    console().print(status("running"))

    printed = capsys.readouterr().out
    assert ESCAPE not in printed
    assert printed == f"{GLYPHS['running']} running\n"


def test_output_to_a_terminal_is_coloured(monkeypatch):
    terminal = to_terminal(monkeypatch)

    console().print(status("parked"))

    assert ESCAPE in terminal.getvalue()


def test_force_color_colours_output_that_is_not_a_terminal(monkeypatch, capsys):
    monkeypatch.setenv("FORCE_COLOR", "1")

    console().print(status("running"))

    assert ESCAPE in capsys.readouterr().out


def test_no_color_wins_over_a_terminal_and_over_force_color(monkeypatch):
    terminal = to_terminal(monkeypatch)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")

    console().print(status("parked"))

    assert ESCAPE not in terminal.getvalue()
    assert "parked" in terminal.getvalue()


def test_the_error_console_writes_to_stderr(capsys):
    console(stderr=True).print(refusal("no entry 'x' in the queue"))

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "naiad: no entry 'x' in the queue\n"


def test_square_brackets_in_text_are_printed_as_they_are(capsys):
    """A Task is whatever the operator typed, and `[bold]` in it is theirs."""
    console().print("fix [bold]x[/bold] and :smile: in [repo]")

    assert capsys.readouterr().out == "fix [bold]x[/bold] and :smile: in [repo]\n"


def test_nothing_in_a_line_is_highlighted(monkeypatch):
    """Rich colours numbers, paths and quoted strings unless told not to, which
    would put escape codes into text nobody styled."""
    terminal = to_terminal(monkeypatch)

    console().print("entry 20261005-012208 in /Users/me/dev 'quoted' 42")

    assert ESCAPE not in terminal.getvalue()


def test_the_console_is_as_wide_as_columns_says(monkeypatch):
    monkeypatch.setenv("COLUMNS", "132")

    assert console().width == 132


def test_a_line_wider_than_the_console_is_never_wrapped(monkeypatch, capsys):
    """Lines are cut to fit before they are printed; a second wrap by the
    console would break a row that was already the right width, or one the
    reader needs whole."""
    monkeypatch.setenv("COLUMNS", "20")

    console().print(Text("a" * 50 + " " + "b" * 50))

    assert capsys.readouterr().out == "a" * 50 + " " + "b" * 50 + "\n"


def test_every_status_has_a_glyph_and_a_style_of_its_own():
    assert set(GLYPHS) == set(get_args(Status))
    for word in get_args(Status):
        assert f"status.{word}" in THEME.styles


def test_a_status_reads_as_its_glyph_then_its_word():
    shown = status("done")

    assert shown.plain == f"{GLYPHS['done']} done"
    assert shown.cell_len == len(shown.plain)


def plain(lines):
    return [line.plain for line in lines]


def test_columns_are_padded_to_their_widest_cell_and_the_last_is_not_padded():
    lines = columns([["ID", "STATE", "TASK"], ["51695", "orchestrate", "build"]], width=80)

    assert plain(lines) == [
        "ID     STATE        TASK",
        "51695  orchestrate  build",
    ]


def test_the_last_column_is_cut_so_each_line_fits_the_width():
    lines = columns([["ID", "TASK"], ["51695", "x" * 100]], width=30)

    assert plain(lines)[1] == "51695  " + "x" * 22 + "…"
    assert all(line.cell_len <= 30 for line in lines)


def test_the_last_column_keeps_its_least_width_however_narrow_the_terminal():
    lines = columns([["ID", "TASK"], ["a" * 40, "y" * 100]], width=30, least=12)

    assert plain(lines)[1] == "a" * 40 + "  " + "y" * 11 + "…"


def test_no_width_cuts_nothing():
    """For a last column the reader needs whole, as a terminal wraps it."""
    lines = columns([["NAME", "PROBLEM"], ["broken", "z" * 500]], width=None)

    assert plain(lines)[1] == "broken  " + "z" * 500


def test_columns_are_measured_in_cells_and_keep_their_styles():
    """A wide character takes two columns, and a style takes none."""
    wide = Text("漢字", style="state")
    lines = columns([["名前", "TASK"], [wide, Text("done", style="status.done")]], width=80)

    assert plain(lines) == ["名前  TASK", "漢字  done"]
    assert any(span.style == "state" for span in lines[1].spans)
    assert any(span.style == "status.done" for span in lines[1].spans)


def test_a_styled_line_reads_as_its_words_to_anything_that_reads_text():
    """A test's list, a log and `print` take a line as text; only the terminal
    is shown its styles."""
    line = Styled(Text.assemble(("starting", "event.progress"), " ", ("51695", "id")))

    assert isinstance(line, str)
    assert line == "starting 51695"
    assert styles_of(line) == {"starting": "event.progress", "51695": "id"}


def test_a_line_nobody_styled_is_shown_as_its_words():
    shown = styled("the queue is drained")

    assert shown.plain == "the queue is drained"
    assert shown.spans == []


def test_a_said_line_is_plain_off_a_terminal(capsys):
    say(Styled(Text("starting", style="event.progress")))

    assert capsys.readouterr().out == "starting\n"


def test_a_said_line_is_coloured_at_a_terminal(monkeypatch):
    terminal = to_terminal(monkeypatch)

    say(Styled(Text("starting", style="event.progress")))

    assert ESCAPE in terminal.getvalue()


def test_a_line_said_to_stderr_goes_to_stderr(capsys):
    say("naiad: refused", stderr=True)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "naiad: refused\n"


def test_every_kind_of_event_has_a_style_of_its_own():
    for kind in ("progress", "attention", "ended"):
        assert f"event.{kind}" in THEME.styles


def test_a_said_line_off_a_terminal_is_its_words_byte_for_byte(capsys):
    """An agent, a hook or a script reads these words. A tab in a Task or an
    answer is the writer's, and a Console would have turned it into spaces and
    dropped a carriage return."""
    say("fix\tthis\rnow")
    say(Styled(Text.assemble(("queued", "event.progress"), "\tlater")), stderr=True)

    captured = capsys.readouterr()
    assert captured.out == "fix\tthis\rnow\n"
    assert captured.err == "queued\tlater\n"


def test_a_said_line_under_no_color_is_its_words_byte_for_byte(monkeypatch):
    terminal = to_terminal(monkeypatch)
    monkeypatch.setenv("NO_COLOR", "1")

    say("fix\tthis")

    assert terminal.getvalue() == "fix\tthis\n"


def test_a_line_assembled_from_pieces_keeps_every_character_of_its_words(capsys):
    """A Text drops control characters from what it holds; the words a reader
    off a terminal is given are what the pieces said."""
    line = Styled.assemble(("queued", "event.progress"), " in ", ("/tmp/odd\rname", "repo"))

    assert line == "queued in /tmp/odd\rname"
    say(line)
    assert capsys.readouterr().out == "queued in /tmp/odd\rname\n"
