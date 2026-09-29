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


def matching_lines(paths: list[Path], pattern: re.Pattern[str]) -> list[str]:
    """Each line of the files that the pattern finds, as `path:number: text`."""
    return [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path in paths
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if pattern.search(line)
    ]


# Only the guides directly under docs/ ship: a subfolder there holds the
# maintainer's own notes, which may cite what a shipped document may not.
SHIPPED_DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    *sorted((ROOT / "docs").glob("*.md")),
]

# The maintainer's own Workflow is unoffered, so no shipped document names it.
# Spelt in two pieces so that this file does not name what it forbids.
PERSONAL_WORKFLOW = re.compile("matt" + "-pocock", re.IGNORECASE)


def test_no_python_file_cites_the_maintainers_record() -> None:
    python_files = [
        path for folder in ("naiad", "tests") for path in sorted((ROOT / folder).rglob("*.py"))
    ]
    assert matching_lines(python_files, CITATION) == []


def test_no_shipped_document_cites_the_maintainers_record() -> None:
    assert matching_lines(SHIPPED_DOCUMENTS, CITATION) == []


def test_no_shipped_document_names_the_personal_workflow() -> None:
    assert matching_lines(SHIPPED_DOCUMENTS, PERSONAL_WORKFLOW) == []
