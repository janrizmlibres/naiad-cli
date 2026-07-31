import pytest


class RecordingSessions:
    """Stands in for the tmux adapter. Records the SessionSpec it was handed;
    the command a spec produces is covered by tests/test_session_spec.py."""

    def __init__(self):
        self.spawned = []

    def spawn(self, spec):
        self.spawned.append(spec)
        return "%42"


@pytest.fixture
def sessions():
    return RecordingSessions()
