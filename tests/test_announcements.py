"""The State file: the agent's Announcements, ordered and readable at any moment."""

import json
import threading

import pytest

from naiad.domain.announcement import Announcement
from naiad.runtime.announcements import Announcements


@pytest.fixture
def announcements(tmp_path):
    return Announcements(tmp_path)


def test_nothing_has_been_announced_before_the_agent_announces(announcements):
    assert announcements.latest() is None


def test_announcing_records_the_state(announcements):
    announcements.announce("grill")

    assert announcements.latest().state == "grill"


def test_successive_announcements_allocate_a_strictly_increasing_sequence(announcements):
    seqs = [announcements.announce(name).seq for name in ("grill", "spec", "implement")]

    assert seqs == sorted(set(seqs)) == seqs
    assert seqs[0] > 0


def test_the_same_state_announced_twice_is_two_distinct_announcements(announcements):
    first = announcements.announce("implement")
    second = announcements.announce("implement")

    assert second.seq > first.seq
    assert announcements.latest() == Announcement(seq=second.seq, state="implement")


def test_announcements_survive_a_fresh_reader(announcements, tmp_path):
    announcements.announce("grill")
    announcements.announce("spec")

    assert Announcements(tmp_path).latest() == announcements.latest()


def test_a_concurrent_read_never_observes_a_partial_write(announcements):
    """A tick reads this file while the agent is writing it. Every read must
    see a whole Announcement or no file at all — never half of one."""
    torn = []
    finished = threading.Event()

    def read_continuously():
        while not finished.is_set():
            try:
                document = json.loads(announcements.path.read_text())
            except FileNotFoundError:
                continue
            except (ValueError, UnicodeDecodeError) as error:
                torn.append(error)
                return
            if not isinstance(document.get("seq"), int):
                torn.append(document)
                return

    reader = threading.Thread(target=read_continuously)
    reader.start()
    try:
        for _ in range(200):
            announcements.announce("implement" * 500)
    finally:
        finished.set()
        reader.join()

    assert torn == []
