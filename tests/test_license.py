"""The license files a wheel carries: the MIT text names the two Workflow files
that are 0BSD instead, and every file `pyproject.toml` lists as a license file
exists, so a build cannot ship a declaration with nothing behind it.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
ZERO_BSD_FILES = ["naiad/workflows/starter.toml", "workflows/matt-pocock.toml"]


def test_the_license_names_both_zero_bsd_files() -> None:
    text = (ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License")
    assert "Copyright (c) 2026 Janriz Libres" in text
    for name in ZERO_BSD_FILES:
        assert name in text


def test_the_zero_bsd_files_exist() -> None:
    for name in ZERO_BSD_FILES:
        assert (ROOT / name).is_file()


def test_the_declared_license_covers_both_texts() -> None:
    assert PROJECT["license"] == "MIT AND 0BSD"
    assert PROJECT["license-files"] == ["LICENSE", "LICENSES/0BSD.txt"]
    for name in PROJECT["license-files"]:
        assert (ROOT / name).is_file()
    assert "Zero-Clause BSD" in (ROOT / "LICENSES/0BSD.txt").read_text()
