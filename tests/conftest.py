import pytest


class RecordingSessions:
    """Stands in for the tmux adapter. Records the SessionSpec it was handed;
    the command a spec produces is covered by tests/test_session_spec.py.

    Both ways a Run meets a session: one opened for it, and one already running
    that it joins (ADR 0028). An attachment answers with the name of the tmux
    session holding that pane, which is the human's own rather than Naiad's.

    Clearing is recorded although starting a Run never asks for it, because
    that is exactly what wants asserting: kickoff ignores its first State's
    Clear flag, and a fake missing the verb could only report the omission as
    an AttributeError from somewhere unrelated (ADR 0028).
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
