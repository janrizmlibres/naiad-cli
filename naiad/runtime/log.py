"""The Run log: every Announcement received and every Action taken, in order.

The diagnostic. A Run that produced something strange overnight is otherwise
only readable by scrolling a tmux session that has since been Cleared several
times; this turns it into a sequence — which State, which Action, and why.

Written by Naiad rather than by the agent for the same reason the Answer log
is: Naiad is the only party holding both halves, and an audit trail kept by the
party being audited is worth little. It is also what makes the deferred
Protocol-leakage instrumentation possible, since a Run that ended in a
notification after Nudges is countable from here.

Recorded per Action rather than per tick. Most ticks decide Nothing — an agent
working normally — and writing those down would bury a Run's handful of real
events under thousands of lines.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from naiad.domain.announcement import Announcement
from naiad.domain.decide import Action, Clear, Consult, Deliver, Finish, Notify, Nudge, Respond
from naiad.domain.prompt import render_candidates
from naiad.domain.question import Question
from naiad.runtime.atomic import write_atomically

LOG_FILENAME = "log.json"

# The kinds that are the agent talking rather than Naiad acting. Named as a set
# because that distinction is asked for — where the agent stood, whether it
# deviated — while the individual kinds are only ever written and read back.
ANNOUNCEMENT_KINDS = ("announced", "asked")


@dataclass(frozen=True)
class LogLine:
    """One thing that happened: one line of a Run's narrative.

    Named for the line rather than for the entry it once was, because Entry is
    the glossary's word for a Run that does not exist yet — a collision the
    glossary is the place to prevent, as it does for Branch and Working branch.

    kind names it — 'announced' and 'asked' for what the agent said, and the
    Action's own past tense for what Naiad did about it.

    seq ties an entry to the Announcement it belongs to, so the Actions taken
    over one Announcement can be read together.

    state is the State the entry is about: the one announced, the one whose
    Prompt was delivered, the one a Run ended at. detail is whatever else the
    entry needs to explain itself — the reason for a notification, the Question
    put to the Answerer, the answer sent back.

    expected is set only on a Deviation, and names the State the Workflow
    expected instead of the one in state — or, at a fork, every candidate it
    expected, joined into that one string. Deliberately inconsistent with the
    domain, which is plural throughout: this is a human-readable diagnostic,
    deviations() only tests whether it is present, and widening the persisted
    shape would strand existing Run logs for no gain.

    It belongs to an Announcement rather than to the Action taken about it,
    because an Announcement that is never delivered — a jump to a Gate State,
    or straight to the end — deviates just as loudly as one that is.
    """

    kind: str
    seq: int | None = None
    state: str | None = None
    detail: str | None = None
    expected: str | None = None


class RunLog:
    """A Run's log. Constructed with the Run's directory rather than reading a
    module-level path, so a second Run is a second log (ADR 0004)."""

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / LOG_FILENAME

    def entries(self) -> list[LogLine]:
        try:
            document = json.loads(self.path.read_text())
        except FileNotFoundError:
            # A Run that has done nothing yet, which is not an absence of
            # information but the information itself.
            return []
        return [
            LogLine(
                kind=entry["kind"],
                seq=entry.get("seq"),
                state=entry.get("state"),
                detail=entry.get("detail"),
                expected=entry.get("expected"),
            )
            for entry in document
        ]

    def deviations(self) -> list[LogLine]:
        """Every Announcement that left the expected path. Read on its own
        because it is the question asked of a Run that went wrong, and reading
        it should not mean scanning the whole narrative for one field."""
        return [entry for entry in self.entries() if entry.expected is not None]

    def finished(self) -> bool:
        """Whether this Run has reached a Terminal State.

        Read back from the log rather than kept as a flag of its own, because
        the ending is already written here and one fact deserves one home. It
        is what makes finishing final: a watch started again over a Run that
        ended must find nothing to do, however much the agent says afterwards.
        """
        return any(entry.kind == "finished" for entry in self.entries())

    def previous_state(self, announcement: Announcement | None) -> str | None:
        """Where the agent stood before this Announcement, which is what a
        Deviation is measured from.

        Read back from the log because the State file keeps only the latest
        Announcement — deliberately, so that it stays single-writer (ADR 0001)
        — and this is the one place the ones before it are written down.

        None before anything has been announced. Where a Run begins is the
        Run's own business, and answering it here would put that rule in two
        places.

        Two limits are inherited from the State file keeping only the latest
        Announcement (naiad.runtime.announcements). A Run adopted mid-flight has
        no earlier entries to read, and two Announcements made between one tick
        and the next leave only the second — so in both cases this answers with
        the last one Naiad actually saw, which is the most that was ever known.
        """
        if announcement is None:
            return None
        earlier = [
            entry
            for entry in self.entries()
            if entry.kind in ANNOUNCEMENT_KINDS and entry.seq is not None
            if entry.seq < announcement.seq
        ]
        return earlier[-1].state if earlier else None

    def record_announcement(
        self, announcement: Announcement | None, *, deviated_from: Sequence[str] = ()
    ) -> None:
        """What the agent said, written once however often it is read.

        The tick loop reads the latest Announcement several times a minute and
        acts on it once; the log follows the acting rather than the reading.

        deviated_from is the States expected instead, when this Announcement was
        none of them (naiad.domain.transitions.deviation), and empty when it was
        expected. It is recorded here rather than against the Action so that an
        Announcement Naiad delivers nothing for still shows the Run leaving its
        path — joined into one string, for the reason LogLine.expected gives.

        A Subject is recorded for the same reason, and matters most in the same
        case: a Gate State has no Prompt to substitute it into, so the log is
        the only place it is written down, and it is what tells the operator
        which item they have been handed (ADR 0009).
        """
        if announcement is None or self._holds(announcement.seq):
            return
        question = announcement.question
        self._append(
            LogLine(
                kind="asked" if question is not None else "announced",
                seq=announcement.seq,
                # A Question carries the State the agent is standing in rather
                # than one it has moved to, which is why the two kinds are told
                # apart: a log reading them alike shows a State that never was.
                state=announcement.state,
                detail=_detail(announcement),
                expected=render_candidates(deviated_from) or None,
            )
        )

    def record(self, action: Action, *, seq: int | None = None) -> None:
        """What Naiad did about it. Nothing is not written down."""
        entry = _entry_for(action)
        if entry is None:
            return
        self._append(replace(entry, seq=seq))

    def _holds(self, seq: int) -> bool:
        return any(
            entry.seq == seq and entry.kind in ANNOUNCEMENT_KINDS for entry in self.entries()
        )

    def _append(self, entry: LogLine) -> None:
        entries = [*self.entries(), entry]
        write_atomically(
            self.path, json.dumps([_document(e) for e in entries], indent=2) + "\n"
        )


def _detail(announcement: Announcement) -> str | None:
    """What an Announcement says beyond naming a State. A Question and a
    Subject never appear together — a Question is asked from the State the
    agent is standing in, which it announced already — so one field carries
    whichever is present."""
    if announcement.question is not None:
        return _question(announcement.question)
    if announcement.subject is not None:
        return f"about: {announcement.subject}"
    return None


def _entry_for(action: Action) -> LogLine | None:
    """One Action as one line of the narrative. Delivering a State's Prompt and
    sending an answer to a Question are separate kinds because they are what a
    reader must be able to tell apart: both type into the same session, and
    conflating them shows an answered Question as a phase begun twice."""
    if isinstance(action, Deliver):
        # Joined for the same reason LogLine.expected is: the log is prose for a
        # human, not a shape anything queries.
        successors = render_candidates(action.next_states)
        return LogLine(
            kind="delivered",
            state=action.state,
            detail=f"next: {successors}" if successors else None,
        )
    if isinstance(action, Clear):
        # The attempt is always carried, but only a retry is worth a word: a
        # first Clear is the ordinary case and its number would be noise, while
        # a second reads as the dropped-Clear it records (ADR 0019).
        return LogLine(
            kind="cleared",
            state=action.state,
            detail=f"attempt {action.attempt}" if action.attempt > 1 else None,
        )
    if isinstance(action, Respond):
        return LogLine(kind="answered", detail=f"{_question(action.question)} -> {action.answer}")
    if isinstance(action, Consult):
        return LogLine(kind="consulted", detail=_question(action.question))
    if isinstance(action, Nudge):
        return LogLine(kind="nudged", detail=f"attempt {action.attempt}")
    if isinstance(action, Notify):
        return LogLine(kind="notified", detail=action.reason)
    if isinstance(action, Finish):
        return LogLine(kind="finished", state=action.state)
    return None


def _question(question: Question) -> str:
    """A Question as one line: what was asked, and what it was chosen from.
    The options belong beside it for the reason the Answer log keeps them —
    an answer is only judgeable against the alternatives."""
    if not question.options:
        return question.text
    return f"{question.text} ({', '.join(question.options)})"


def _document(entry: LogLine) -> dict[str, object]:
    return {
        "kind": entry.kind,
        "seq": entry.seq,
        "state": entry.state,
        "detail": entry.detail,
        "expected": entry.expected,
    }


__all__ = ["ANNOUNCEMENT_KINDS", "LOG_FILENAME", "LogLine", "RunLog"]
