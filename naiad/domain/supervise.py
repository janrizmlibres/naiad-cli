"""The one function holding the Queue's rules — the sibling of the engine's.

Signals in, Actions out. Nothing here reads a file, runs a subprocess or looks
at a clock: the Supervisor's loop gathers the signals, calls this, and carries
out what comes back, holding no rules of its own.

The rule is one scan. Take the Entries in order; the first for its working
tree that is not done is that lane's Action — Resume if it has a Run, Start
otherwise — and later Entries for the same tree wait behind it. If every Entry
is done, Drained or Idle by mode.

The exclusion unit is the working tree, named by the Entry's target path:
sequential within a path, concurrent across paths. That single scan produces the
behaviours with no special case for any of them. Sequential ordering per lane,
because a lane that has yielded its Action yields nothing more. A parked Run
blocking its own lane and only its own, because a parked Run is not finished,
so its lane keeps answering Resume while every other lane answers for itself. And crash recovery, because a restarted
Supervisor is handed the same signals and finds the same Entries.

The Entry the scan chooses to Start carries the Predecessor its work stands on,
resolved from the Entries before it. Resolution is deliberately not a seam of
its own: it rides on the Start Action, so the rule that picks an Entry and the
rule that decides what it stands on are exercised by one table of cases. It
happens when an Entry starts rather than when it is queued, because Entries may
be added or removed in between.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from naiad.domain.entry import Entry


@dataclass(frozen=True)
class Signals:
    """Everything the Supervisor's decision is made from.

    entries are the Queue in order. The order is settled by whoever gathered
    them — it is id order, and an id is a sortable timestamp — so the rule reads
    the sequence it was handed and sorts nothing itself.

    finished holds the ids of the Runs that are over, by either ending. It is
    handed in rather than asked of each Run here, so that every rule below is
    testable as data in, Action out. There is no matching signal for parked or
    running, and deliberately: the scan needs to know only whether an Entry is
    done, and asking for more would have the Queue keeping a status of its own.

    following says Entries added later are to be picked up. It is the whole of
    the difference between the two modes, and it changes nothing but the answer
    to an empty Queue.

    declared maps an Entry's id to the Working branch its Run declared, for
    Entries whose own record carries none. Handed in like finished,
    and for the same reason: the fact lives on the Run, and asking each Run
    here would keep the rules from being data in, Action out. An Entry absent
    from the mapping has no declared branch — its Run never reached a head, or
    never existed.
    """

    entries: Sequence[Entry]
    finished: Collection[str] = ()
    following: bool = False
    declared: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Start:
    """Start this Entry's Run, then tick it with the pass's other Lanes.

    predecessor is what the work stands on — the Entry's pinned base, or the
    Working branch of the nearest preceding Entry for the same repository —
    resolved here rather than by the loop afterwards, so that picking an Entry
    and deciding what it stands on are one decision exercised by one table of
    cases. An opaque string: whether to actually stand on it is the agent's to
    decide in the Prompt.
    """

    entry: Entry
    predecessor: str | None = None


@dataclass(frozen=True)
class Resume:
    """Tick the Run this Entry already has. It has not finished, so it is
    running, or parked and waiting for a human — and the two are the same
    Action, because ticking a parked Run is what keeps it revivable by their
    typing."""

    entry: Entry


@dataclass(frozen=True)
class Drained:
    """Nothing waiting, nothing running, and not following. The Supervisor
    returns and the operator gets their prompt back."""


@dataclass(frozen=True)
class Idle:
    """Nothing to do; come round again. The Queue may yet be added to."""


DRAINED = Drained()
IDLE = Idle()

Action = Start | Resume

# What one scan of the Queue says: an Action per Lane with something live, or
# the two nothing-to-do answers. Not called an Answer, a word reserved
# for what the Answerer settles a Question with.
Scan = list[Action] | Drained | Idle


def supervise(signals: Signals) -> Scan:
    """One scan, and no second rule beside it.

    Each lane's first Entry that is not done is its Action: an Entry with no
    Run has not been started, so it is Started, and one with a Run the
    finished ids do not name has not ended, so it is Resumed — whether that
    Run is working or parked is not asked, because both want ticking and the
    difference is the Run's to keep rather than the Queue's. A Child its
    Parent's Child limit holds back answers nothing, and keeps its lane. A lane
    that has answered is not asked again, which is one Run per working tree. No
    lane answering means every Entry is done, which is the empty Queue again and
    answers the same way.
    """
    actions: list[Action] = []
    answered: set[Path] = set()
    live = _live_children(signals)
    limits = {
        entry.run_id: entry.child_limit
        for entry in signals.entries
        if entry.run_id is not None and entry.child_limit is not None
    }
    for position, entry in enumerate(signals.entries):
        if entry.target_repo in answered:
            continue
        if entry.run_id is None:
            answered.add(entry.target_repo)
            if _held(entry, live=live, limits=limits):
                continue
            if entry.parent is not None:
                live[entry.parent] += 1
            actions.append(
                Start(
                    entry=entry,
                    predecessor=_predecessor(
                        entry,
                        preceding=signals.entries[:position],
                        declared=signals.declared,
                    ),
                )
            )
        elif entry.run_id not in signals.finished:
            answered.add(entry.target_repo)
            actions.append(Resume(entry=entry))

    if actions:
        return actions
    return IDLE if signals.following else DRAINED


def _live_children(signals: Signals) -> Counter[str]:
    """How many Children each Parent Run has started and not finished. A parked
    Child counts, because its Session is live."""
    return Counter(
        entry.parent
        for entry in signals.entries
        if entry.parent is not None
        and entry.run_id is not None
        and entry.run_id not in signals.finished
    )


def _held(entry: Entry, *, live: Counter[str], limits: Mapping[str, int]) -> bool:
    """Whether a Child is held back by its Parent's Child limit.

    It keeps its Lane while held — it is still that working tree's first Entry
    not done — and the Children are taken in id order, so a limit of one runs
    them one at a time in the order they were spawned. A Parent whose Entry is
    gone from the Queue, or that names no limit, holds nothing back.
    """
    if entry.parent is None or entry.parent not in limits:
        return False
    return live[entry.parent] >= limits[entry.parent]


def _predecessor(
    entry: Entry, *, preceding: Sequence[Entry], declared: Mapping[str, str]
) -> str | None:
    """What an Entry's work stands on: the pinned base if it has one, otherwise
    the Working branch of the nearest preceding Entry for the same repository,
    otherwise nothing.

    A preceding Entry whose own record carries no branch yields the branch its
    Run declared — the stacking chain works for Derived branches
    exactly as for given ones. One with no branch anywhere — its Run never
    reached a head — contributes none, exactly as a missing Predecessor
    renders: absent, ordinary, walked past to the Entry before it.

    Entries for other repositories are walked over, because the Queue is global
    and a branch name from another repository is not a fact about this one:
    handed one, the agent runs the ancestry test, gets nothing useful, and
    quietly bases on the base branch — silently wrong exactly when the global
    Queue is used as intended.

    Entries for the same repository are never walked over. Naiad does not skip
    one on the grounds that its work has already landed, because that is a
    question about git and the answer belongs to the agent; the stack
    collapses correctly without Naiad knowing anything, since an Entry built on
    the one before it carries that one's commits. Removed Entries are absent
    from the Queue and so are passed over here without being asked about, which
    is the intended consequence of removing one.

    Stacking rather than nothing is the default because the two failures are not
    symmetrical. Stacking needlessly couples unrelated pull requests, which costs
    review friction over correct work; not stacking when the work depends means
    the second agent never sees the first's code, and the conflict surfaces at
    merge.
    """
    if entry.pinned_base is not None:
        return entry.pinned_base

    for earlier in reversed(preceding):
        if earlier.target_repo != entry.target_repo:
            continue
        branch = earlier.working_branch
        if branch is None:
            branch = declared.get(earlier.id)
        if branch is not None:
            return branch

    return None


__all__ = [
    "DRAINED",
    "IDLE",
    "Action",
    "Scan",
    "Drained",
    "Idle",
    "Resume",
    "Signals",
    "Start",
    "supervise",
]
