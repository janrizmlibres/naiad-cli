"""What Naiad records about a Run, as distinct from what the agent records.

A few facts, a file each. The State file is the agent's and Naiad never writes
it (ADR 0001), so Naiad's own bookkeeping lives beside it rather than in it.
The records are also written by different processes — a Stop hook fires while
the tick loop is running — so they stay separate files rather than racing over
one.

Their modification times carry a second fact for free: when Naiad last had any
sign of life from the Run. That is what makes silence and hanging measurable
without a clock inside any rule.
"""

from __future__ import annotations

import json
from pathlib import Path

from naiad.domain.announcement import Announcement
from naiad.domain.answerer import Answered, Consultation, Escalated
from naiad.runtime.announcements import STATE_FILENAME
from naiad.runtime.atomic import write_atomically
from naiad.runtime.run import METADATA_FILENAME

TURNS_FILENAME = "turns.json"
HANDLED_FILENAME = "handled.json"
NOTICES_FILENAME = "notices.json"
CONSULTATIONS_FILENAME = "consultations.json"
CLEARS_FILENAME = "clears.json"
CLEAR_ATTEMPTS_FILENAME = "clearattempts.json"

# Every file whose writing means something happened. The Run's own metadata is
# among them so that a Run which has produced no signal at all is idle since it
# started rather than since the epoch.
SIGNAL_FILENAMES = (
    STATE_FILENAME,
    TURNS_FILENAME,
    HANDLED_FILENAME,
    NOTICES_FILENAME,
    CONSULTATIONS_FILENAME,
    CLEARS_FILENAME,
    CLEAR_ATTEMPTS_FILENAME,
    METADATA_FILENAME,
)

Document = dict[str, int | bool | str | None]


def _read(path: Path) -> Document:
    try:
        document: Document = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    return document


def _write(path: Path, document: Document) -> None:
    write_atomically(path, json.dumps(document, indent=2) + "\n")


def _seq(announcement: Announcement | None) -> int | None:
    return announcement.seq if announcement else None


def _current(path: Path, announcement: Announcement | None) -> Document:
    """A record kept against one Announcement, read as nothing for any other.

    Shared by everything Naiad remembers per Announcement rather than per Run:
    whether the operator has been told, how many Nudges it cost, what the
    Answerer said. The next Announcement re-arms all of them, which is what
    lets a Run that needed a human once need one again.
    """
    document = _read(path)
    return document if document.get("seq") == _seq(announcement) else {}


def idle_seconds(run_root: Path, *, now: float) -> float:
    """How long since the last signal of any kind, handed to the decision
    function so that no rule reads a clock (ADR 0004).

    Measured from the records rather than from a timestamp Naiad keeps, because
    the signals are written by three processes and their arrival is exactly
    what a file appearing means.
    """
    signals = [Path(run_root) / name for name in SIGNAL_FILENAMES]
    times = [path.stat().st_mtime for path in signals if path.exists()]
    if not times:
        return 0.0
    return max(0.0, now - max(times))


class Turns:
    """When a turn last ended, written by the Stop hook.

    The end of a turn is recorded against the Announcement that was current
    when it happened, rather than against a clock. A turn that ended while
    Announcement 2 was current says nothing about Announcement 3, which the
    agent made afterwards and is still working on.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / TURNS_FILENAME

    def record_end(self, *, latest_seq: int | None) -> None:
        _write(self.path, {"after_seq": latest_seq, "count": self.count() + 1})

    def count(self) -> int:
        """How many turns have ended in this Run, ever.

        A count rather than a flag because the question Naiad asks about a turn
        end is asked from two ends: has one happened since the Announcement,
        and has one happened since Naiad last acted. A flag can only answer the
        first, and answering the second with it nudges a working agent.
        """
        count = _read(self.path).get("count")
        return count if isinstance(count, int) else 0

    def ended_since_action(self, handled: Handled) -> bool:
        """Whether the agent has stopped since Naiad last delivered something.

        The turn end that let a Prompt be delivered is spent by that delivery:
        the agent then works on what it was given, ending no turn and writing
        nothing, so without this every phase longer than the silence bound
        would be read as a silent agent.
        """
        return self.count() > handled.turns()

    def ended_since(self, announcement: Announcement | None) -> bool:
        """Whether the agent has stopped working since the Announcement given.

        With nothing announced there is no Announcement for a turn end to be
        stale against, so any recorded end counts: an agent that ended a turn
        having announced nothing is silent, which is what a Nudge is for.
        """
        document = _read(self.path)
        if not document:
            return False
        if announcement is None:
            return True
        after = document.get("after_seq")
        return isinstance(after, int) and after >= announcement.seq


class Clears:
    """How many times a Clear has landed, written by the SessionStart hook when
    a fresh context is one a /clear made — read from the hook's own `source`,
    rather than a startup or a compaction (ADR 0019).

    The counterpart to Turns. A Stop hook says a turn ended and counts them; a
    SessionStart(clear) hook says a Clear landed and counts them. A count rather
    than a flag for the same reason Turns keeps one: the question 'has this
    State's Clear landed?' is asked against a baseline the loop stamped when it
    typed /clear, and only a count can tell one State's Clear from the last.

    Its own file, because the hook that writes it and the loop that writes the
    attempts against it are different processes and must not race over one
    document (the rule this module opens with).
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / CLEARS_FILENAME

    def record_landing(self) -> None:
        _write(self.path, {"count": self.count() + 1})

    def count(self) -> int:
        count = _read(self.path).get("count")
        return count if isinstance(count, int) else 0


class ClearAttempts:
    """What the loop has done to get a State's context cleared: how many times
    it has typed /clear for the current Announcement, and the Clear count it
    read the first time it did — the baseline a later landing is judged against.

    Kept against the Announcement it belongs to and read as nothing for any
    other, exactly like Notices: the next Announcement re-arms it, so a Run that
    had one Clear dropped delivers the State after it cleanly. Written by the
    loop, apart from the hook's count, because the two are different processes.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / CLEAR_ATTEMPTS_FILENAME

    def attempts(self, announcement: Announcement | None) -> int:
        return int(_current(self.path, announcement).get("attempts", 0) or 0)

    def confirmed(self, announcement: Announcement | None, clears: Clears) -> bool:
        """Whether this Announcement's Clear has landed since it was typed.

        Takes the Clears count as an argument, the way Turns.ended_since_action
        takes the Handled baseline: the fact lives in two files written by two
        processes, and comparing them is the reader's job rather than either
        writer's. False until a /clear has been typed for this Announcement, so
        a landing left over from an earlier State cannot confirm this one.
        """
        document = _current(self.path, announcement)
        attempts = int(document.get("attempts", 0) or 0)
        baseline = int(document.get("baseline", 0) or 0)
        return attempts > 0 and clears.count() > baseline

    def record_attempt(self, announcement: Announcement | None, *, landed: int) -> None:
        """Record that /clear was typed, holding the first attempt's baseline
        across every retry: a Clear that was merely slow, and lands after a
        retry, must still confirm rather than have its target moved past it."""
        document = _current(self.path, announcement)
        attempts = int(document.get("attempts", 0) or 0)
        held = document.get("baseline")
        baseline = held if attempts and isinstance(held, int) else landed
        _write(
            self.path,
            {"seq": _seq(announcement), "baseline": baseline, "attempts": attempts + 1},
        )


class Handled:
    """The last Announcement Naiad acted on, so that it acts once per
    Announcement rather than once per change of value."""

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / HANDLED_FILENAME

    def seq(self) -> int | None:
        seq = _read(self.path).get("seq")
        return seq if isinstance(seq, int) else None

    def turns(self) -> int:
        """How many turns had ended when Naiad last delivered. The baseline the
        next silence is measured against."""
        turns = _read(self.path).get("turns")
        return turns if isinstance(turns, int) else 0

    def record(self, seq: int, *, turns: int = 0) -> None:
        _write(self.path, {"seq": seq, "turns": turns})


class Notices:
    """What Naiad has already done about the agent falling quiet: whether the
    operator has been told, and how many Nudges it has cost.

    Both are kept against the Announcement they belong to, and both read as
    nothing for any other one. That is the whole of 'once per Announcement, not
    once per tick': the conditions that need a human persist with identical
    signals until the human acts, and the next Announcement is what re-arms
    them.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / NOTICES_FILENAME

    def of(self, announcement: Announcement | None) -> tuple[bool, int]:
        document = _current(self.path, announcement)
        return bool(document.get("notified", False)), int(document.get("nudges", 0) or 0)

    def record_notified(self, announcement: Announcement | None) -> None:
        notified, nudges = self.of(announcement)
        self._write(announcement, notified=True, nudges=nudges)

    def record_nudge(self, announcement: Announcement | None) -> None:
        notified, nudges = self.of(announcement)
        self._write(announcement, notified=notified, nudges=nudges + 1)

    def _write(self, announcement: Announcement | None, *, notified: bool, nudges: int) -> None:
        _write(
            self.path,
            {"seq": _seq(announcement), "notified": notified, "nudges": nudges},
        )


class Consultations:
    """What the Answerer has said about the Question currently announced.

    Kept against the Announcement it belongs to and read as nothing for any
    other one, exactly like Notices: the next Question re-arms it, so a Run
    whose first Question was escalated can have its second one answered.

    It exists at all because resolving a Question takes two decisions — consult,
    then act on what came back — and the tick between them needs somewhere to
    put the outcome. Without it the Answerer would be consulted afresh on every
    tick, which is a headless Claude call every couple of seconds and an answer
    that may contradict the one already sent.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / CONSULTATIONS_FILENAME

    def of(self, announcement: Announcement | None) -> Consultation:
        document = _current(self.path, announcement)
        text = document.get("text")
        if not isinstance(text, str):
            return None
        return Escalated(reason=text) if document.get("escalated") else Answered(text=text)

    def record(self, announcement: Announcement | None, consultation: Answered | Escalated) -> None:
        _write(
            self.path,
            {
                "seq": _seq(announcement),
                "escalated": isinstance(consultation, Escalated),
                "text": (
                    consultation.reason
                    if isinstance(consultation, Escalated)
                    else consultation.text
                ),
            },
        )


__all__ = [
    "ClearAttempts",
    "Clears",
    "Consultations",
    "Handled",
    "Notices",
    "Turns",
    "idle_seconds",
]
