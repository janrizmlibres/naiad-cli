"""Where Naiad keeps what it owns.

One home, one override, and the roots under it. The Queue lives beside the Runs
rather than reading the environment a second time, so moving the home moves
everything Naiad holds together.
"""

from pathlib import Path

from naiad.runtime.home import default_queue_root, default_runs_root, naiad_home


def test_naiad_keeps_what_it_owns_under_the_operators_home(monkeypatch):
    monkeypatch.delenv("NAIAD_HOME", raising=False)

    assert naiad_home() == Path.home() / ".naiad"


def test_the_naiad_directory_can_be_moved(monkeypatch, tmp_path):
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "elsewhere"))

    assert naiad_home() == tmp_path / "elsewhere"


def test_runs_live_under_the_naiad_home(monkeypatch):
    monkeypatch.delenv("NAIAD_HOME", raising=False)

    assert default_runs_root() == Path.home() / ".naiad" / "runs"


def test_the_queue_lives_beside_the_runs_under_the_same_home(monkeypatch, tmp_path):
    """The Queue honours the same override rather than re-reading the
    environment in a second place, so one move moves both."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "elsewhere"))

    assert default_queue_root() == tmp_path / "elsewhere" / "queue"
    assert default_runs_root() == tmp_path / "elsewhere" / "runs"
