"""The Queue's rules, as data in and Actions out. No tmux, no subprocess, no clock.

One scan produces the behaviours — sequential ordering within a repository,
repositories running concurrently, a parked Run blocking its own
lane, and crash recovery — with no special case for any of them. Each is
asserted separately here because each would be a different bug.
"""

from dataclasses import replace
from pathlib import Path

from naiad.domain.entry import Attachment, Entry
from naiad.domain.supervise import (
    CEILING,
    DISK,
    DRAINED,
    IDLE,
    MEMORY,
    AtCapacity,
    Resume,
    Signals,
    Start,
    supervise,
)

REPO = Path("/repos/naiad")
ANOTHER_REPO = Path("/repos/acme")


def entry(identifier, **overrides):
    fields = dict(
        id=identifier,
        workflow_path=REPO / "workflow.toml",
        task="add dark mode",
        target_repo=REPO,
        working_branch=f"TASK-{identifier}",
        created_at="2026-07-22T12:00:00Z",
    )
    fields.update(overrides)
    return Entry(**fields)


def draining(*entries, finished=(), declared=None):
    return Signals(entries=entries, finished=finished, following=False, declared=declared or {})


def following(*entries, finished=()):
    return Signals(entries=entries, finished=finished, following=True)


# An empty Queue is the whole of the difference between the two modes: one
# returns, the other comes round again.


def test_an_empty_queue_drains_when_draining():
    assert supervise(draining()) == DRAINED


def test_an_empty_queue_idles_when_following():
    """Following means Entries added later are picked up, so nothing to do now
    is not the same as nothing to do."""
    assert supervise(following()) == IDLE


# The scan: per lane, the first Entry that is not done — started if it has no
# Run and resumed if it has.


def test_the_first_entry_with_no_run_is_started():
    first, second = entry("one"), entry("two")

    assert supervise(draining(first, second)) == [Start(entry=first, predecessor=None)]


def test_a_started_entry_carries_its_pinned_base_as_its_predecessor():
    """Resolution rides on the Action, so the rule that picks an Entry and the
    rule that decides what it stands on are one decision rather than two."""
    pinned = entry("one", pinned_base="TASK-8000")

    assert supervise(draining(pinned)) == [Start(entry=pinned, predecessor="TASK-8000")]


def test_an_entry_whose_run_has_not_finished_is_resumed():
    running = entry("one", run_id="a-run")

    assert supervise(draining(running)) == [Resume(entry=running)]


def test_an_entry_whose_run_has_not_finished_stops_the_next_from_starting():
    """Sequential ordering within a repository and a parked Run blocking its
    lane are the same case: the lane's scan stops at the first Entry that is
    not done, and a parked Run is not finished."""
    running, waiting = entry("one", run_id="a-run"), entry("two")

    assert supervise(draining(running, waiting)) == [Resume(entry=running)]


def test_a_supervisor_restarted_mid_run_resumes_the_same_entry():
    """Crash recovery needs no resume path: a restarted Supervisor is handed
    the same signals and finds the same Entry."""
    interrupted, waiting = entry("one", run_id="a-run"), entry("two")
    signals = draining(interrupted, waiting)

    assert supervise(signals) == supervise(signals) == [Resume(entry=interrupted)]


def test_a_finished_entry_is_scanned_past_to_the_next():
    done, waiting = entry("one", run_id="a-run"), entry("two")

    # Which Entry the scan reaches, and not what it stands on: the Predecessor
    # is resolved by its own table of cases below, and asserting it here as well
    # is what made this test break when the rule for it changed.
    scanned_past = supervise(draining(done, waiting, finished={"a-run"}))

    assert isinstance(scanned_past, list) and len(scanned_past) == 1
    assert isinstance(scanned_past[0], Start)
    assert scanned_past[0].entry is waiting


def test_a_finished_entry_is_scanned_past_to_the_next_unfinished_run():
    done, running = entry("one", run_id="a-run"), entry("two", run_id="another-run")

    assert supervise(draining(done, running, finished={"a-run"})) == [Resume(entry=running)]


# Repositories are lanes: sequential within one, concurrent across them. The
# exclusion unit is the working tree, named by the target path.


def test_entries_for_two_repositories_both_run():
    """The collision one-at-a-time exists to prevent cannot happen between two
    working trees, so neither waits for the other to finish — only for the
    next scan, since a scan starts one Run."""
    ours, theirs = entry("one"), entry("two", target_repo=ANOTHER_REPO)

    assert supervise(draining(ours, theirs)) == [Start(entry=ours, predecessor=None)]
    assert supervise(draining(replace(ours, run_id="a-run"), theirs)) == [
        Resume(entry=replace(ours, run_id="a-run")),
        Start(entry=theirs, predecessor=None),
    ]


def test_a_run_in_one_repository_does_not_stop_another_repository_starting():
    """One repository running, another
    waiting behind it for no reason the working tree can name."""
    running = entry("one", run_id="a-run")
    waiting = entry("two", target_repo=ANOTHER_REPO)

    assert supervise(draining(running, waiting)) == [
        Resume(entry=running),
        Start(entry=waiting, predecessor=None),
    ]


def test_a_lane_that_yielded_its_action_yields_nothing_more():
    """One Run per working tree: behind a lane's live Run, that lane's later
    Entries wait exactly as the whole Queue used to."""
    running = entry("one", run_id="a-run")
    behind = entry("two")
    elsewhere = entry("three", target_repo=ANOTHER_REPO)

    assert supervise(draining(running, behind, elsewhere)) == [
        Resume(entry=running),
        Start(entry=elsewhere, predecessor=None),
    ]


def test_lanes_come_out_in_the_order_their_first_unfinished_entries_were_queued():
    theirs = entry("one", target_repo=ANOTHER_REPO, run_id="a-run")
    ours = entry("two", run_id="another-run")

    resumed = supervise(draining(theirs, ours))

    assert [action.entry for action in resumed] == [theirs, ours]


def test_two_worktrees_of_one_repository_are_two_lanes():
    """Not a loophole but the rule meaning what it says: the
    exclusion unit is the working tree, named by the target path, and two
    worktrees of one repository are two working trees."""
    main_tree = entry("one", target_repo=Path("/repos/acme"), run_id="a-run")
    worktree = entry("two", target_repo=Path("/repos/acme-orion"))

    assert supervise(draining(main_tree, worktree)) == [
        Resume(entry=main_tree),
        Start(entry=worktree, predecessor=None),
    ]


def test_a_queue_parked_in_one_lane_still_works_in_the_others():
    """A parked Run blocks only its own lane: a night
    parked at review in one repository is still a night of work in the other
    two."""
    parked = entry("one", run_id="a-run")
    other_repo = entry("two", target_repo=ANOTHER_REPO, run_id="another-run")
    third_repo = entry("three", target_repo=Path("/repos/third"))

    assert supervise(draining(parked, other_repo, third_repo)) == [
        Resume(entry=parked),
        Resume(entry=other_repo),
        Start(entry=third_repo, predecessor=None),
    ]


# Every Entry done is the empty Queue again, and answers the same way.


def test_a_queue_whose_every_entry_is_done_drains():
    first, second = entry("one", run_id="a-run"), entry("two", run_id="another-run")

    assert supervise(draining(first, second, finished={"a-run", "another-run"})) == DRAINED


def test_a_queue_whose_every_entry_is_done_idles_when_following():
    first, second = entry("one", run_id="a-run"), entry("two", run_id="another-run")

    assert supervise(following(first, second, finished={"a-run", "another-run"})) == IDLE


def test_the_entries_are_taken_in_the_order_they_are_given():
    """Queue order is id order, settled by whoever gathered the signals. The
    rule reads the sequence it was handed and sorts nothing itself."""
    first, second, third = entry("one"), entry("two"), entry("three")

    assert supervise(draining(first, second, third))[0].entry is first


# Resolving the Predecessor: the pinned base, else the nearest preceding Entry
# for the same repository, else nothing. Exercised through Start, because
# resolution rides on the Action rather than living behind a seam of its own.


def test_an_entry_with_no_pinned_base_stands_on_the_entry_before_it():
    """Stacking is the default: a later Entry sees the code an earlier one
    wrote, or the second agent builds the same thing differently and the
    conflict surfaces at merge."""
    first = entry("one", run_id="a-run")
    second = entry("two")

    assert supervise(draining(first, second, finished={"a-run"})) == [
        Start(entry=second, predecessor="TASK-one")
    ]


def test_a_pinned_base_wins_over_the_entry_before_it():
    """Work unrelated to what came before is not stacked onto it, whatever
    precedes it in the Queue."""
    first = entry("one", run_id="a-run")
    second = entry("two", pinned_base="develop")

    assert supervise(draining(first, second, finished={"a-run"})) == [
        Start(entry=second, predecessor="develop")
    ]


def test_an_entry_for_another_repository_is_walked_over():
    """The Queue is global, so a branch name from another repository is not a
    fact about this one — and handing one over would have the agent run the
    ancestry test, get nothing useful, and quietly base on the base branch."""
    first = entry("one", run_id="a-run")
    interloper = entry("two", target_repo=ANOTHER_REPO, run_id="another-run")
    third = entry("three")

    assert supervise(
        draining(first, interloper, third, finished={"a-run", "another-run"})
    ) == [Start(entry=third, predecessor="TASK-one")]


def test_the_first_entry_for_a_repository_stands_on_nothing():
    """First for *its* repository rather than first in the Queue: everything
    ahead of it belongs to another project, so there is nothing here to stand
    on and it is handed nothing rather than something from elsewhere."""
    interloper = entry("one", target_repo=ANOTHER_REPO, run_id="a-run")
    second = entry("two")

    assert supervise(draining(interloper, second, finished={"a-run"})) == [
        Start(entry=second, predecessor=None)
    ]


def test_an_entry_whose_immediate_predecessor_was_removed_takes_the_one_before_it():
    """A removed Entry is absent from disk and so is naturally passed over.
    That is the intended consequence of removing one: dropped work should not
    be in the stack."""
    first = entry("one", run_id="a-run")
    # "two" was queued between them and removed; it is simply not here.
    third = entry("three")

    assert supervise(draining(first, third, finished={"a-run"})) == [
        Start(entry=third, predecessor="TASK-one")
    ]


def test_a_branchless_entry_stands_on_the_branch_the_preceding_run_declared():
    """A preceding Entry whose own record carries no branch yields the branch
    its Run declared: the stacking chain works for Derived branches
    exactly as for given ones."""
    derived = entry("one", working_branch=None, run_id="a-run")
    second = entry("two")

    assert supervise(
        draining(derived, second, finished={"a-run"}, declared={"one": "feat/dark-mode"})
    ) == [Start(entry=second, predecessor="feat/dark-mode")]


def test_a_pinned_base_wins_over_a_declared_branch():
    derived = entry("one", working_branch=None, run_id="a-run")
    pinned = entry("two", pinned_base="develop")

    assert supervise(
        draining(derived, pinned, finished={"a-run"}, declared={"one": "feat/dark-mode"})
    ) == [Start(entry=pinned, predecessor="develop")]


def test_an_entry_with_no_branch_anywhere_is_walked_past():
    """A preceding Entry whose Run never recorded a branch (it never reached a
    head) contributes none, exactly as a missing Predecessor renders: absent,
    ordinary, walked past to the next preceding Entry for the repository."""
    first = entry("one", run_id="a-run")
    headless = entry("two", working_branch=None, run_id="another-run")
    third = entry("three")

    assert supervise(
        draining(first, headless, third, finished={"a-run", "another-run"})
    ) == [Start(entry=third, predecessor="TASK-one")]


def test_a_declared_branch_in_another_repository_is_still_walked_over():
    """A Derived branch is as much another repository's fact as a given one:
    declared or not, an Entry for another repository contributes nothing here."""
    interloper = entry("one", target_repo=ANOTHER_REPO, working_branch=None, run_id="a-run")
    second = entry("two")

    assert supervise(
        draining(interloper, second, finished={"a-run"}, declared={"one": "feat/theirs"})
    ) == [Start(entry=second, predecessor=None)]


def test_a_preceding_entry_for_the_same_repository_is_never_skipped():
    """Naiad does not skip one on the grounds that its work has already landed:
    that is a question about git and the answer belongs to the agent.
    The stack collapses correctly without Naiad knowing anything."""
    landed = entry("one", run_id="a-run")
    stacked = entry("two", run_id="another-run")
    third = entry("three")

    assert supervise(
        draining(landed, stacked, third, finished={"a-run", "another-run"})
    ) == [Start(entry=third, predecessor="TASK-two")]


# A Child limit: a Parent with as many live Children as its limit holds back the
# rest, each in its own Lane, until one finishes.

PARENT_RUN = "parent-run"


def parent(**overrides):
    return entry("parent", run_id=PARENT_RUN, **overrides)


def child(identifier, **overrides):
    return entry(
        identifier,
        target_repo=Path(f"/repos/naiad-wt--{identifier}"),
        parent=PARENT_RUN,
        pinned_base="feature",
        **overrides,
    )


def started(scan):
    return [action.entry.id for action in scan if isinstance(action, Start)]


def test_a_child_limit_of_two_holds_the_third_child():
    scan = supervise(
        draining(
            parent(child_limit=2),
            child("c1", run_id="c1-run"),
            child("c2", run_id="c2-run"),
            child("c3"),
        )
    )

    assert started(scan) == []


def test_a_held_child_starts_once_a_live_one_finishes():
    first = child("c1", run_id="c1-run")
    second = child("c2", run_id="c2-run")

    scan = supervise(
        draining(parent(child_limit=2), first, second, child("c3"), finished={"c1-run"})
    )

    assert started(scan) == ["c3"]


def test_a_child_limit_of_one_takes_the_children_one_at_a_time_in_id_order():
    """The old serial behaviour without a mode: id order is spawn order."""
    limited = parent(child_limit=1)

    assert started(supervise(draining(limited, child("c1"), child("c2")))) == ["c1"]
    assert (
        started(
            supervise(
                draining(
                    limited,
                    child("c1", run_id="c1-run"),
                    child("c2"),
                    finished={"c1-run"},
                )
            )
        )
        == ["c2"]
    )


def test_no_child_limit_holds_no_child_back():
    scan = supervise(
        draining(
            parent(), child("c1", run_id="c1-run"), child("c2", run_id="c2-run"), child("c3")
        )
    )

    assert started(scan) == ["c3"]


def test_a_parked_child_counts_toward_the_limit():
    """Parked is not finished: its Session is live, so it holds a place."""
    parked = child("c1", run_id="c1-run")

    scan = supervise(draining(parent(child_limit=1), parked, child("c2")))

    assert scan == [Resume(entry=parent(child_limit=1)), Resume(entry=parked)]


def test_a_held_child_keeps_its_lane_waiting_behind_it():
    """Held, it is still that working tree's first Entry not done, so a later
    Entry for the same tree does not jump ahead of it."""
    held = child("c2")
    behind = entry("later", target_repo=held.target_repo)

    scan = supervise(
        draining(parent(child_limit=1), child("c1", run_id="c1-run"), held, behind)
    )

    assert started(scan) == []


# Capacity: a ceiling on live Runs, counted across every lane. It bounds
# starting only — whatever Capacity says, a live Run is always ticked.


def capped(
    *entries, ceiling=None, finished=(), joining=(), strained=False, low_disk=()
):
    return Signals(
        entries=entries,
        finished=finished,
        following=False,
        ceiling=ceiling,
        joining=joining,
        strained=strained,
        low_disk=low_disk,
    )


def test_at_the_ceiling_nothing_starts_but_every_live_run_is_resumed():
    first = entry("one", run_id="a-run")
    second = entry("two", target_repo=ANOTHER_REPO, run_id="another-run")
    waiting = entry("three", target_repo=Path("/repos/third"))

    scan = supervise(capped(first, second, waiting, ceiling=2))

    assert started(scan) == []
    assert [action for action in scan if isinstance(action, Resume)] == [
        Resume(entry=first),
        Resume(entry=second),
    ]


def test_below_the_ceiling_a_waiting_entry_starts():
    running = entry("one", run_id="a-run")
    waiting = entry("two", target_repo=ANOTHER_REPO)

    assert supervise(capped(running, waiting, ceiling=2)) == [
        Resume(entry=running),
        Start(entry=waiting, predecessor=None),
    ]


def test_finished_runs_are_not_counted():
    done = entry("one", run_id="a-run")
    waiting = entry("two", target_repo=ANOTHER_REPO)

    assert started(supervise(capped(done, waiting, ceiling=1, finished={"a-run"}))) == ["two"]


def test_one_start_per_scan_however_much_room_there_is():
    """So that what the machine reads after one start can catch up before the
    next. The first waiting lane head in id order is the one."""
    first = entry("one")
    second = entry("two", target_repo=ANOTHER_REPO)

    assert supervise(capped(first, second, ceiling=10)) == [Start(entry=first, predecessor=None)]


def test_a_parked_run_is_counted():
    """Parked is not finished: its Session is live, so it holds a place."""
    parked = entry("one", run_id="a-run")
    waiting = entry("two", target_repo=ANOTHER_REPO)

    assert started(supervise(capped(parked, waiting, ceiling=1))) == []


def test_a_joining_parent_is_not_counted_so_a_ceiling_of_one_starts_its_child():
    """Counted, a Parent held at its Join and its only Child would wait on each
    other for ever."""
    joining_parent = parent()

    scan = supervise(capped(joining_parent, child("c1"), ceiling=1, joining={PARENT_RUN}))

    assert scan == [
        Resume(entry=joining_parent),
        Start(entry=child("c1"), predecessor="feature"),
    ]


def test_the_ceiling_is_given_as_the_reason_nothing_started():
    running = entry("one", run_id="a-run")
    waiting = entry("two", target_repo=ANOTHER_REPO)

    scan = supervise(capped(running, waiting, ceiling=1))

    assert scan == [Resume(entry=running), AtCapacity(reason=CEILING)]


def test_no_reason_is_given_when_nothing_is_waiting():
    running = entry("one", run_id="a-run")

    assert supervise(capped(running, ceiling=1)) == [Resume(entry=running)]


def test_no_reason_is_given_when_something_started():
    """The one-start rule holding the rest back is not Capacity."""
    first = entry("one")
    second = entry("two", target_repo=ANOTHER_REPO)

    scan = supervise(capped(first, second, ceiling=2))

    assert not any(isinstance(action, AtCapacity) for action in scan)


def test_a_child_held_by_its_limit_is_not_a_capacity_reason():
    held = child("c2")

    scan = supervise(
        capped(parent(child_limit=1), child("c1", run_id="c1-run"), held, ceiling=1)
    )

    assert not any(isinstance(action, AtCapacity) for action in scan)


# Below the ceiling, the machine must be unstrained: memory pressure stops every
# start, and a working tree short of free disk is passed over.


def test_strained_memory_starts_nothing_but_every_live_run_is_resumed():
    running = entry("one", run_id="a-run")
    waiting = entry("two", target_repo=ANOTHER_REPO)

    scan = supervise(capped(running, waiting, ceiling=10, strained=True))

    assert scan == [Resume(entry=running), AtCapacity(reason=MEMORY)]


def test_strained_memory_holds_back_a_start_with_no_ceiling_set():
    waiting = entry("one")

    assert supervise(capped(waiting, strained=True)) == [AtCapacity(reason=MEMORY)]


def test_the_ceiling_is_the_reason_when_both_hold_a_start_back():
    running = entry("one", run_id="a-run")
    waiting = entry("two", target_repo=ANOTHER_REPO)

    scan = supervise(capped(running, waiting, ceiling=1, strained=True))

    assert scan == [Resume(entry=running), AtCapacity(reason=CEILING)]


def test_a_working_tree_low_on_disk_is_passed_over_and_a_later_lane_starts():
    low = entry("one")
    later = entry("two", target_repo=ANOTHER_REPO)

    scan = supervise(capped(low, later, ceiling=10, low_disk={REPO}))

    assert scan == [Start(entry=later, predecessor=None)]


def test_an_entry_behind_one_low_on_disk_in_its_own_lane_waits_too():
    low = entry("one")
    behind = entry("two")

    scan = supervise(capped(low, behind, low_disk={REPO}))

    assert started(scan) == []


def test_disk_is_the_reason_when_every_waiting_tree_is_low():
    running = entry("one", run_id="a-run")
    low = entry("two", target_repo=ANOTHER_REPO)

    scan = supervise(capped(running, low, ceiling=10, low_disk={ANOTHER_REPO}))

    assert scan == [Resume(entry=running), AtCapacity(reason=DISK)]


def test_a_live_run_on_a_low_disk_is_still_resumed():
    running = entry("one", run_id="a-run")

    assert supervise(capped(running, low_disk={REPO})) == [Resume(entry=running)]


# An Adoption joins a Session that is already live, so starting it adds nothing
# for memory or the ceiling to bound. Disk is still asked.


def adoption(identifier, **overrides):
    return entry(identifier, attachment=Attachment(tmux_pane="%7"), **overrides)


def test_an_adoption_starts_while_memory_is_strained():
    adopted = adoption("one")

    assert supervise(capped(adopted, strained=True)) == [Start(entry=adopted, predecessor=None)]


def test_an_adoption_starts_with_the_live_runs_at_the_ceiling():
    running = entry("one", run_id="a-run")
    adopted = adoption("two", target_repo=ANOTHER_REPO)

    assert supervise(capped(running, adopted, ceiling=1)) == [
        Resume(entry=running),
        Start(entry=adopted, predecessor=None),
    ]


def test_an_adoption_into_a_working_tree_low_on_disk_waits():
    adopted = adoption("one")

    assert supervise(capped(adopted, strained=True, low_disk={REPO})) == [
        AtCapacity(reason=DISK)
    ]


def test_a_live_adoption_is_counted():
    """Once started it is a Run like any other, and its Session is live."""
    adopted = adoption("one", run_id="a-run")
    waiting = entry("two", target_repo=ANOTHER_REPO)

    assert supervise(capped(adopted, waiting, ceiling=1)) == [
        Resume(entry=adopted),
        AtCapacity(reason=CEILING),
    ]
