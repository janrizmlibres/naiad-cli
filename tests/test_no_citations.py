"""A comment, a docstring or a shipped document states its rule inline. It
never cites a decision record, a ticket, a spec or a smoke walkthrough,
because a reader of the public checkout holds none of them.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Each name is spelt in two pieces so that this file does not cite what it
# forbids.
CITATION = re.compile(
    "|".join(
        [
            r"\b" + "AD" + "R",
            r"\b" + "PR" + r"D\b",
            "CONTEXT" + r"\.md",
            r"\." + "scratch",
            "docs/" + "smoke",
            "docs/" + "adr",
        ]
    )
)


def test_no_python_file_cites_the_maintainers_record() -> None:
    offenders = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for folder in ("naiad", "tests")
        for path in sorted((ROOT / folder).rglob("*.py"))
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if CITATION.search(line)
    ]
    assert offenders == []


def test_no_shipped_document_cites_the_maintainers_record() -> None:
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for name in ("README.md", "CONTRIBUTING.md")
        for number, line in enumerate((ROOT / name).read_text().splitlines(), start=1)
        if CITATION.search(line)
    ]
    assert offenders == []
