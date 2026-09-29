"""The Queue's rules, as data in and Actions out. No tmux, no subprocess, no clock.

One scan produces the behaviours — sequential ordering within a repository,
repositories running concurrently, a parked Run blocking its own
lane, and crash recovery — with no special case for any of them. Each is
asserted separately here because each would be a different bug.
"""

from pathlib import Path

from naiad.domain.entry import Entry
from naiad.domain.supervise import DRAINED, IDLE, Resume, Signals, Start, supervise

REPO = Path("/repos/naiad")
ANOTHER_REPO = Path("/repos/acme")


def entry(identifier, **overrides):
    fields = dict(
        id=identifier,
        workflow_path=REPO / "workflow.toml",
        task="add dark mode",
        target_repo=REPO,
        working_branch=f"MC-AGENT-{identifier}",
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
    pinned = entry("one", pinned_base="MC-AGENT-8000")

    assert supervise(draining(pinned)) == [Start(entry=pinned, predecessor="MC-AGENT-8000")]


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


def test_entries_for_two_repositories_are_both_started():
    """The collision one-at-a-time exists to prevent cannot happen between two
    working trees, so neither waits for the other."""
    ours, theirs = entry("one"), entry("two", target_repo=ANOTHER_REPO)

    assert supervise(draining(ours, theirs)) == [
        Start(entry=ours, predecessor=None),
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
    theirs = entry("one", target_repo=ANOTHER_REPO)
    ours = entry("two")

    started = supervise(draining(theirs, ours))

    assert [action.entry for action in started] == [theirs, ours]


def test_two_worktrees_of_one_repository_are_two_lanes():
    """Not a loophole but the rule meaning what it says: the
    exclusion unit is the working tree, named by the target path, and two
    worktrees of one repository are two working trees."""
    main_tree = entry("one", target_repo=Path("/repos/acme"))
    worktree = entry("two", target_repo=Path("/repos/acme-orion"))

    assert supervise(draining(main_tree, worktree)) == [
        Start(entry=main_tree, predecessor=None),
        Start(entry=worktree, predecessor=None),
    ]


def test_a_queue_parked_in_one_lane_still_works_in_the_others():
    """A parked Run blocks only its own lane: a night
    parked at review in one repository is still a night of work in the other
    two."""
    parked = entry("one", run_id="a-run")
    other_repo = entry("two", target_repo=ANOTHER_REPO)
    third_repo = entry("three", target_repo=Path("/repos/third"))

    assert supervise(draining(parked, other_repo, third_repo)) == [
        Resume(entry=parked),
        Start(entry=other_repo, predecessor=None),
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
        Start(entry=second, predecessor="MC-AGENT-one")
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
    ) == [Start(entry=third, predecessor="MC-AGENT-one")]


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
        Start(entry=third, predecessor="MC-AGENT-one")
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
    ) == [Start(entry=third, predecessor="MC-AGENT-one")]


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
    ) == [Start(entry=third, predecessor="MC-AGENT-two")]
