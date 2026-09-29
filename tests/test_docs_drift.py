"""The shipped documents show `naiad` commands, and a command that no longer
parses is a document that has drifted from the program. Every line starting
`naiad ` inside a fenced code block of the README, the contributing guide and
the guides under docs/ is parsed with the real command tree. Prose is not
tested: only what a reader would copy into a terminal.
"""

import re
import shlex
from pathlib import Path

import pytest

from naiad.cli.main import build_parser

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").glob("*.md"))]

FENCE = re.compile(r"^\s*```")


def documented_commands(text: str) -> list[str]:
    """Each line inside a fenced block that starts with `naiad `."""
    commands = []
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        elif fenced and line.startswith("naiad "):
            commands.append(line)
    return commands


def parses(command: str) -> bool:
    """Whether the command tree accepts the line."""
    try:
        build_parser().parse_args(shlex.split(command, comments=True)[1:])
    except SystemExit:
        return False
    return True


def test_only_naiad_lines_inside_a_fence_are_collected():
    text = "\n".join(
        [
            "naiad outside a fence is prose",
            "```",
            "naiad queue list",
            "uv tool install naiad-cli",
            "  naiad indented is not a line starting naiad",
            "```",
            "naiad after the fence is prose again",
            "```sh",
            'naiad queue add starter "<task>" --repo .',
            "```",
        ]
    )

    assert documented_commands(text) == [
        "naiad queue list",
        'naiad queue add starter "<task>" --repo .',
    ]


def test_a_renamed_verb_is_refused(capsys):
    assert parses("naiad queue list")
    assert not parses("naiad queue enqueue starter")
    capsys.readouterr()


def test_a_trailing_comment_is_not_part_of_the_command():
    assert parses("naiad queue list   # entries in order")


def test_the_readme_walks_an_adopter_through_the_commands():
    commands = documented_commands((ROOT / "README.md").read_text())

    assert "naiad install --starter" in commands
    assert any(command.startswith("naiad queue add starter ") for command in commands)
    assert "naiad queue watch" in commands


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.name)
def test_every_documented_command_parses(document, capsys):
    commands = documented_commands(document.read_text())

    offenders = [command for command in commands if not parses(command)]
    capsys.readouterr()

    assert offenders == []
