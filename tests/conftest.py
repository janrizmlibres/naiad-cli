import os

import pytest

from fake_machine import install_healthy


class RecordingSessions:
    """Stands in for the tmux adapter. Records the SessionSpec it was handed;
    the command a spec produces is covered by tests/test_session_spec.py.

    Both ways a Run meets a session: one opened for it, and one already running
    that it joins. An attachment answers with the name of the tmux
    session holding that pane, which is the human's own rather than Naiad's.

    Clearing is recorded although starting a Run never asks for it, because
    that is exactly what wants asserting: kickoff ignores its first State's
    Clear flag, and a fake missing the verb could only report the omission as
    an AttributeError from somewhere unrelated.
    """

    def __init__(self):
        self.spawned = []
        self.attached = []
        self.cleared = []

    def spawn(self, spec):
        self.spawned.append(spec)
        return "%42"

    def attach(self, pane):
        self.attached.append(pane)
        return "the-humans-session"

    def clear(self, pane):
        self.cleared.append(pane)


@pytest.fixture
def sessions():
    return RecordingSessions()


@pytest.fixture(autouse=True)
def isolated_machine(monkeypatch, tmp_path_factory):
    """No test reaches the operator's real Claude configuration or Naiad home.

    Both are read from the environment, so a test that forgets to name its own
    would install hooks and a library into the machine it runs on. A test that
    cares sets them again, and the later setting wins.
    """
    root = tmp_path_factory.mktemp("machine")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root / "claude"))
    monkeypatch.setenv("NAIAD_HOME", str(root / "naiad"))


@pytest.fixture(autouse=True)
def ready_machine(monkeypatch, tmp_path_factory):
    """A machine where the doctor finds tmux and claude, whatever this one has.

    Every entrance checks the machine before it starts, and most tests are about
    what an entrance does once it has. The tests of the check itself put the
    real one back and build the machine they mean to break.
    """
    directory = tmp_path_factory.mktemp("bin")
    install_healthy(directory)
    monkeypatch.setenv("PATH", f"{directory}:{os.environ['PATH']}")
    monkeypatch.setattr("naiad.cli.main.entrance_refusal", lambda: None)


@pytest.fixture(autouse=True)
def no_capacity_set(monkeypatch):
    """A ceiling the operator's shell sets is not one any test asked for."""
    monkeypatch.delenv("NAIAD_CAPACITY", raising=False)
