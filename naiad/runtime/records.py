"""What Naiad records about a Run, as distinct from what the agent records.

A few facts, a file each. The State file is the agent's and Naiad never writes
it, so Naiad's own bookkeeping lives beside it rather than in it.
The records are also written by different processes — a Stop hook fires while
the tick loop is running — so they stay separate files rather than racing over
one.

Their modification times carry a second fact for free: when Naiad last had any
sign of life from the Run. That is what makes silence and hanging measurable
without a clock inside any rule.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from naiad.domain.announcement import Announcement
from naiad.domain.answerer import Answered, Consultation, Escalated
from naiad.domain.decide import WAIT_BUDGET_SECONDS, WAIT_DEFAULT_SECONDS, Submission
from naiad.domain.submission import Verdict
from naiad.runtime.announcements import STATE_FILENAME
from naiad.runtime.atomic import write_atomically
from naiad.runtime.run import METADATA_FILENAME

TURNS_FILENAME = "turns.json"
HANDLED_FILENAME = "handled.json"
NOTICES_FILENAME = "notices.json"
REPORTS_FILENAME = "reports.json"
CONSULTATIONS_FILENAME = "consultations.json"
CLEARS_FILENAME = "clears.json"
CLEAR_ATTEMPTS_FILENAME = "clearattempts.json"
SWITCHES_FILENAME = "switches.json"
DELIVERIES_FILENAME = "deliveries.json"
SUBMISSIONS_FILENAME = "submissions.json"
WAITS_FILENAME = "waits.json"
HOLDS_FILENAME = "holds.json"

# Beside the Entry in the queue directory, under the Entry's id. Not `.json`,
# which the Queue reads as an Entry file.
ENTRY_TURNS_SUFFIX = ".turns"

# Every file whose writing means something happened. The Run's own metadata is
# among them so that a Run which has produced no signal at all is idle since it
# started rather than since the epoch.
SIGNAL_FILENAMES = (
    STATE_FILENAME,
    TURNS_FILENAME,
    HANDLED_FILENAME,
    NOTICES_FILENAME,
    REPORTS_FILENAME,
    CONSULTATIONS_FILENAME,
    CLEARS_FILENAME,
    CLEAR_ATTEMPTS_FILENAME,
    SWITCHES_FILENAME,
    DELIVERIES_FILENAME,
    SUBMISSIONS_FILENAME,
    WAITS_FILENAME,
    HOLDS_FILENAME,
    METADATA_FILENAME,
)

Document = dict[str, int | float | bool | str | None]


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
    function so that no rule reads a clock.

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


class EntryTurns:
    """A Turn end that arrived before an Adoption's Run existed, kept beside
    the Entry that will become it.

    Written by the Stop hook alone, in its own file rather than on the Entry,
    so the hook and the Supervisor's attach never race over one rewrite. The
    filename deliberately does not end in `.json`: everything so named in the
    queue directory is read as an Entry.
    """

    def __init__(self, queue_root: Path, entry_id: str) -> None:
        self.path = Path(queue_root) / f"{entry_id}{ENTRY_TURNS_SUFFIX}"

    def record_end(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _write(self.path, {"count": self.count() + 1})

    def count(self) -> int:
        count = _read(self.path).get("count")
        return count if isinstance(count, int) else 0

    def relocate_into(self, run_root: Path) -> None:
        """Move the record into the Run at attach — a move rather than a copy,
        so the fact keeps one home.

        Write-if-absent: a Stop that fired after the Run was created wrote a
        fresher record there already, and the sidecar is then deleted unread.
        The opening only ever asks whether the count is above zero, so no merge
        is owed."""
        count = self.count()
        turns = Turns(run_root)
        if count and not turns.path.exists():
            _write(turns.path, {"after_seq": None, "count": count})
        self.path.unlink(missing_ok=True)


class Clears:
    """How many times a Clear has landed, written by the SessionStart hook when
    a fresh context is one a /clear made — read from the hook's own `source`,
    rather than a startup or a compaction.

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


class Switches:
    """How many of a State's Switches the loop has typed for the current
    Announcement.

    Kept against the Announcement it belongs to and read as nothing for any
    other, like ClearAttempts and Notices: the next Announcement re-arms it, so
    a delivery counts its own Switches from zero however far the delivery before
    it got. How many it owes at all is another question, and not this one — a
    Switch carries only what the Session is not believed to hold,
    and that belief is read from the Run log.

    A count and nothing else. There is no baseline to hold and no landing to
    compare against, because a Switch is never confirmed — what the
    count buys is a tick between one Switch and the next, which is the whole of
    what the session needs.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / SWITCHES_FILENAME

    def typed(self, announcement: Announcement | None) -> int:
        return int(_current(self.path, announcement).get("typed", 0) or 0)

    def record_typed(self, announcement: Announcement | None) -> None:
        _write(
            self.path,
            {"seq": _seq(announcement), "typed": self.typed(announcement) + 1},
        )


@dataclass(frozen=True)
class TypedPrompt:
    """The latest Prompt the loop typed, as the UserPromptSubmit hook needs it:
    what to compare a submission against, when it was typed, and which attempt
    of which Announcement a verdict on it answers."""

    seq: int | None
    attempt: int
    prompt: str
    at: float


class Deliveries:
    """What the loop has typed to get a State's Prompt into the Session: how
    many times for the current Announcement, the rendered Prompt the hook
    judges a submission against, when it was typed, and how many Turns had
    ended then — the baseline the Confirm hands to Handled.

    The Clear's ClearAttempts, for the Prompt, and kept against the
    Announcement like it: the next one re-arms the count. Written by the loop
    alone; the hook's verdicts go in Submissions, because the two are
    different processes.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / DELIVERIES_FILENAME

    def attempts(self, announcement: Announcement | None) -> int:
        return int(_current(self.path, announcement).get("attempts", 0) or 0)

    def turns(self, announcement: Announcement | None) -> int:
        return int(_current(self.path, announcement).get("turns", 0) or 0)

    def latest(self) -> TypedPrompt | None:
        """The latest attempt whichever Announcement it answers, read by the
        hook, which knows no Announcement."""
        document = _read(self.path)
        prompt = document.get("prompt")
        if not isinstance(prompt, str):
            return None
        seq = document.get("seq")
        return TypedPrompt(
            seq=seq if isinstance(seq, int) else None,
            attempt=int(document.get("attempts", 0) or 0),
            prompt=prompt,
            at=float(document.get("at", 0.0) or 0.0),
        )

    def record_attempt(
        self, announcement: Announcement | None, *, prompt: str, turns: int, at: float
    ) -> None:
        """turns is taken afresh on every attempt: a turned-away attempt starts
        no Turn, so the count when the one that lands was typed is the
        baseline its agent's next Turn end is measured from."""
        _write(
            self.path,
            {
                "seq": _seq(announcement),
                "attempts": self.attempts(announcement) + 1,
                "prompt": prompt,
                "at": at,
                "turns": turns,
            },
        )


class Submissions:
    """What the UserPromptSubmit hook made of the latest typed Prompt — landed
    or turned away — keyed by the Announcement and the attempt it judged.

    Written by the hook alone, apart from Deliveries, as Clears is apart from
    ClearAttempts. Keyed by the attempt as well as the Announcement because a
    verdict answers one typing: a rejection read as the retry's would have it
    typed a third time at once.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / SUBMISSIONS_FILENAME

    def of(self, announcement: Announcement | None, *, attempt: int) -> Submission:
        return self.verdict(seq=_seq(announcement), attempt=attempt)

    def verdict(self, *, seq: int | None, attempt: int) -> Submission:
        document = _read(self.path)
        if not document or document.get("seq") != seq or document.get("attempt") != attempt:
            return None
        verdict = document.get("verdict")
        if verdict == "landed":
            return "landed"
        if verdict == "rejected":
            return "rejected"
        return None

    def record(self, *, seq: int | None, attempt: int, verdict: Verdict) -> None:
        _write(self.path, {"seq": seq, "attempt": attempt, "verdict": verdict})


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

    def record(self, seq: int | None, *, turns: int = 0) -> None:
        """A seq of None is an adopted Run's first Prompt, which answers no
        Announcement: nothing has been acted on, and what is being
        recorded is the turn baseline the next silence is measured against."""
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

    def of(
        self, announcement: Announcement | None, *, wait_count: int = 0, hold_count: int = 0
    ) -> tuple[bool, int]:
        """wait_count is how many Waits the Announcement has declared, and a
        mismatch re-arms the record exactly as a new Announcement does: a
        re-declared Wait after a wake answers a new silence, so it earns a
        fresh allowance rather than inheriting the count an earlier one ran up.
        hold_count re-arms it the same way, because the likeliest Hold arrives
        after a notification — silence, Nudges, the operator told, and only then
        the human's 'pause' relayed — and a Hold whose own notification the
        earlier alarm swallowed would park the Run silently, the exact failure
        its notification is load-bearing against. Every reader must pass the
        counts the writer keyed with — notice_key gives both — or a parked
        Run reads as running."""
        document = _current(self.path, announcement)
        if int(document.get("wait", 0) or 0) != wait_count:
            return False, 0
        if int(document.get("hold", 0) or 0) != hold_count:
            return False, 0
        return bool(document.get("notified", False)), int(document.get("nudges", 0) or 0)

    def record_notified(
        self, announcement: Announcement | None, *, wait_count: int = 0, hold_count: int = 0
    ) -> None:
        notified, nudges = self.of(announcement, wait_count=wait_count, hold_count=hold_count)
        self._write(
            announcement, notified=True, nudges=nudges, wait_count=wait_count, hold_count=hold_count
        )

    def record_nudge(
        self, announcement: Announcement | None, *, wait_count: int = 0, hold_count: int = 0
    ) -> None:
        notified, nudges = self.of(announcement, wait_count=wait_count, hold_count=hold_count)
        self._write(
            announcement,
            notified=notified,
            nudges=nudges + 1,
            wait_count=wait_count,
            hold_count=hold_count,
        )

    def _write(
        self,
        announcement: Announcement | None,
        *,
        notified: bool,
        nudges: int,
        wait_count: int,
        hold_count: int,
    ) -> None:
        _write(
            self.path,
            {
                "seq": _seq(announcement),
                "notified": notified,
                "nudges": nudges,
                "wait": wait_count,
                "hold": hold_count,
            },
        )


class NoticeKey(TypedDict):
    wait_count: int
    hold_count: int


def notice_key(run_root: Path, announcement: Announcement | None) -> NoticeKey:
    """The counts the Notices record is keyed with for this Announcement, as
    keyword arguments to every Notices call. One home for the key, so the loop
    that writes a park and a status reading that asks after it cannot pass
    different counts and see a parked Run as running."""
    return {
        "wait_count": Waits(run_root).count(announcement),
        "hold_count": Holds(run_root).count(announcement),
    }


class Reports:
    """Whether the operator has been told the Run entered the current
    Announcement's State.

    Kept against the Announcement it belongs to and read as nothing for any
    other one, like Notices: the next Announcement re-arms it, so a State
    announced for the fifth ticket reports a fifth time. A record of its own
    rather than a field of Notices, because everything that reads a hand-off
    reads Notices, and a Report is not one. Nothing that decides parking can
    see it.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / REPORTS_FILENAME

    def of(self, announcement: Announcement | None) -> bool:
        return bool(_current(self.path, announcement).get("reported", False))

    def record(self, announcement: Announcement | None) -> None:
        _write(self.path, {"seq": _seq(announcement), "reported": True})


class Waits:
    """The agent's declared Wait — what it said it was waiting on, until when,
    and how much of the Announcement's wait budget has gone.

    Written by the wait command in the agent's process and read by the loop,
    like the State file — and like it, single-writer. Kept against the
    Announcement it belongs to and read as nothing for any other, exactly like
    Notices: the next Announcement re-arms the budget.

    The budget is charged for a Wait's lifetime rather than its claim: from
    declaration until it is replaced or expires, capped at what it claimed.
    Several background tasks finishing at different moments is the honest
    pattern the verb exists for, and charging each full claim would exhaust
    the budget in a few wakes. The wake itself is invisible to Naiad, so time
    the woken agent spends working before re-declaring is charged as waited — an
    over-charge, accepted as the price of not reading the session. An expired
    Wait charges no more than it claimed: silence past the deadline is the
    silence rule's to spend.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / WAITS_FILENAME

    def waiting(self, announcement: Announcement | None, *, now: float) -> bool:
        until = _current(self.path, announcement).get("until")
        return isinstance(until, (int, float)) and now < until

    def reason(self, announcement: Announcement | None) -> str | None:
        reason = _current(self.path, announcement).get("reason")
        return reason if isinstance(reason, str) else None

    def count(self, announcement: Announcement | None) -> int:
        return int(_current(self.path, announcement).get("count", 0) or 0)

    def remaining(self, announcement: Announcement | None, *, now: float) -> float:
        return max(0.0, WAIT_BUDGET_SECONDS - self._spent(announcement, now=now))

    def record(
        self,
        announcement: Announcement | None,
        *,
        reason: str,
        now: float,
        seconds: float | None = None,
    ) -> float:
        """Declare a Wait, replacing any outstanding one, and return what it
        was granted. A claim past the remaining budget is clamped to it rather
        than refused — the refusal, when the budget is spent entirely, is the
        caller's, which is where its wording lives."""
        spent = self._spent(announcement, now=now)
        claim = seconds if seconds is not None else WAIT_DEFAULT_SECONDS
        granted = min(claim, max(0.0, WAIT_BUDGET_SECONDS - spent))
        _write(
            self.path,
            {
                "seq": _seq(announcement),
                "count": self.count(announcement) + 1,
                "reason": reason,
                "at": now,
                "until": now + granted,
                "granted": granted,
                "spent": spent,
            },
        )
        return granted

    def _spent(self, announcement: Announcement | None, *, now: float) -> float:
        """The budget gone: what earlier Waits settled at, plus what the
        outstanding one has actually consumed — elapsed time, capped at its
        claim."""
        document = _current(self.path, announcement)
        if not document:
            return 0.0
        settled = float(document.get("spent", 0.0) or 0.0)
        at = float(document.get("at", 0.0) or 0.0)
        granted = float(document.get("granted", 0.0) or 0.0)
        return settled + min(granted, max(0.0, now - at))


class Holds:
    """The agent's declared Hold — the human's instruction to park the Run,
    and what the agent said when relaying it.

    Written by the hold command in the agent's process and read by the loop,
    like Waits, and single-writer for the same reason. Kept against the
    Announcement it belongs to and read as nothing for any other, so the
    agent announcing again is what lifts it — no release is needed on that
    path. The one explicit release is the wait command's: a fresh Wait
    supersedes a Hold, and both records standing would leave the Run held by
    a declaration the agent has already moved past.

    No deadline and no budget, deliberately: a Hold waits on a person, and
    nothing about a person comes back on a timer. What bounds it is
    visibility — declaring one notifies the operator — rather than a clock.
    """

    def __init__(self, run_root: Path) -> None:
        self.path = Path(run_root) / HOLDS_FILENAME

    def holding(self, announcement: Announcement | None) -> bool:
        return bool(_current(self.path, announcement).get("held", False))

    def reason(self, announcement: Announcement | None) -> str | None:
        reason = _current(self.path, announcement).get("reason")
        return reason if isinstance(reason, str) else None

    def count(self, announcement: Announcement | None) -> int:
        """How many Holds this Announcement has declared. It keys the Notices
        record the way Waits.count does: a declared Hold is a fresh signal, so
        its notification is owed even where an earlier alarm already fired."""
        return int(_current(self.path, announcement).get("count", 0) or 0)

    def record(self, announcement: Announcement | None, *, reason: str) -> None:
        _write(
            self.path,
            {
                "seq": _seq(announcement),
                "count": self.count(announcement) + 1,
                "held": True,
                "reason": reason,
            },
        )

    def release(self, announcement: Announcement | None) -> None:
        """Lift the Hold: only the held flag drops. The count survives because
        it keys the Notices record — zeroing it would hand the next silence a
        re-armed notification it never earned."""
        document = _current(self.path, announcement)
        if not document:
            return
        _write(self.path, {**document, "held": False})


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
    "Deliveries",
    "EntryTurns",
    "Handled",
    "Holds",
    "Notices",
    "Reports",
    "Submissions",
    "Switches",
    "TypedPrompt",
    "Turns",
    "Waits",
    "idle_seconds",
]
