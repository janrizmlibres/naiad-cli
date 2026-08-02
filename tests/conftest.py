import pytest


class RecordingSessions:
    """Stands in for the tmux adapter. Records the SessionSpec it was handed;
    the command a spec produces is covered by tests/test_session_spec.py.

    Both ways a Run meets a session: one opened for it, and one already running
    that it joins (ADR 0028). An attachment answers with the name of the tmux
    session holding that pane, which is the human's own rather than Naiad's.
    """

    def __init__(self):
        self.spawned = []
        self.attached = []

    def spawn(self, spec):
        self.spawned.append(spec)
        return "%42"

    def attach(self, pane):
        self.attached.append(pane)
        return "the-humans-session"


@pytest.fixture
def sessions():
    return RecordingSessions()
