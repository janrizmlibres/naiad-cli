"""Shared fixtures for the tests that invoke naiad as a real subprocess."""

import shutil
import sys
from pathlib import Path

import pytest


def _installed_naiad() -> str | None:
    """The naiad belonging to the interpreter running the tests.

    Searching PATH alone is not enough: another naiad earlier on PATH would be
    exercised instead of this one, and the tests would pass or fail describing
    a different program entirely.
    """
    alongside = Path(sys.executable).parent / "naiad"
    if alongside.is_file():
        return str(alongside)
    return shutil.which("naiad")


NAIAD = _installed_naiad()

requires_installed_naiad = pytest.mark.skipif(
    NAIAD is None,
    reason="the naiad command is not installed; run `uv sync` or `pip install -e .`",
)


def naiad_environment(run, *, run_id: str) -> dict[str, str]:
    """The environment the agent's commands meet: a Naiad directory and the Run
    the session belongs to, and nothing else that could leak in."""
    return {
        "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin",
        "NAIAD_HOME": str(run.root.parents[1]),
        "NAIAD_RUN_ID": run_id,
    }
