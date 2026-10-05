"""The Queue commands as an operator meets them: exit status, what lands on
disk, what is printed.

`naiad queue add` is also the command an agent inside a session uses, so the
tests hold it to returning without supervising anything.
"""

import json
import re
import time

import pytest
from rich.text import Text

from fake_terminal import ESCAPE, styles_of, to_terminal
from naiad.adapters.lock import SupervisorLock
from naiad.cli.hold import declare_hold
from naiad.cli.main import _cancellation_line, _drive, _ticker, main
from naiad.cli.style import GLYPHS, Styled
from naiad.cli.wait import declare_wait
from naiad.domain.decide import NUDGE_LIMIT, SILENCE_SECONDS, Finish, Notify
from naiad.domain.entry import Entry
from naiad.domain.question import Question
from naiad.domain.settings import StateSetting
from naiad.domain.short_ids import short_ids
from naiad.domain.workflow import parse_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.answers import AnswerLog
from naiad.runtime.home import default_queue_root
from naiad.runtime.log import RunLog
from naiad.runtime.loop import tick
from naiad.runtime.queue import Queue
from naiad.runtime.records import Children, Handled, Notices, Turns
from naiad.runtime.resolve import RunResolver
from naiad.runtime.run import RunStore

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "implement"
prompt = "/implement the ticket at {subject}"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def home(monkeypatch, tmp_path):
    """A Naiad home of this test's own, beside the repositories rather than
    inside one."""
    monkeypatch.setenv("NAIAD_HOME", str(tmp_path / "naiad"))
    return tmp_path / "naiad"


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    (path / "workflow.toml").write_text(WORKFLOW)
    return path


@pytest.fixture(autouse=True)
def no_tmux(monkeypatch, sessions):
    """Nothing in this file may open a session. Wired for every test so that a
    command which tried to would be caught rather than reaching real tmux."""
    monkeypatch.setattr("naiad.cli.main.TmuxSessions", lambda: sessions)
    return sessions


def queue_of(home):
    return Queue(home / "queue")


def add(repo, *arguments):
    return main(
        [
            "queue",
            "add",
            str(repo / "workflow.toml"),
            "add dark mode",
            "--repo",
            str(repo),
            *arguments,
        ]
    )


def test_adding_an_entry_reports_it_in_the_words_an_agent_reads(home, repo, capsys):
    """Agents run `naiad queue add`, and adopt and spawn report through the
    same lines, so their words and layout are held whole."""
    assert add(repo, "--branch", "TASK-8546") == 0

    (queued,) = queue_of(home).all()
    assert capsys.readouterr().out == (
        f"queued {queued.id}\n  branch TASK-8546   in {repo}\n"
    )


def test_adding_an_entry_reports_the_same_words_coloured_at_a_terminal(
    home, repo, monkeypatch
):
    terminal = to_terminal(monkeypatch)

    assert add(repo, "--branch", "TASK-8546") == 0

    (queued,) = queue_of(home).all()
    lines = terminal.getvalue().splitlines()
    assert all(ESCAPE in line for line in lines)
    assert [words_of(line) for line in lines] == [
        f"queued {queued.id}",
        f"  branch TASK-8546   in {repo}",
    ]


def test_adding_an_entry_records_it_under_the_naiad_home(home, repo, capsys):
    assert add(repo, "--branch", "TASK-8546") == 0

    (queued,) = queue_of(home).all()
    assert queued.task == "add dark mode"
    assert queued.target_repo == repo
    assert queued.working_branch == "TASK-8546"
    assert queued.id in capsys.readouterr().out


def test_adding_an_entry_records_every_field_it_was_given(home, repo):
    add(
        repo,
        "--branch",
        "TASK-8546",
        "--base",
        "TASK-8000",
        "--at",
        "implement",
        "--subject",
        "docs/ticket.md",
        "--skip-gates",
    )

    (queued,) = queue_of(home).all()
    assert queued.pinned_base == "TASK-8000"
    assert queued.start_state == "implement"
    assert queued.subject == "docs/ticket.md"
    assert queued.skip_gates is True


def test_adding_an_entry_records_the_settings_it_names_for_states(home, repo):
    add(
        repo,
        "--model",
        "implement=sonnet",
        "--effort",
        "implement=medium",
        "--model",
        "grill=haiku",
    )

    (queued,) = queue_of(home).all()
    assert set(queued.settings) == {
        StateSetting(state="implement", setting="model", value="sonnet"),
        StateSetting(state="implement", setting="effort", value="medium"),
        StateSetting(state="grill", setting="model", value="haiku"),
    }


def test_a_setting_that_names_no_state_is_refused_before_anything_is_queued(
    home, repo, capsys
):
    """Every setting names its State; a bare value is not read as meaning all
    of them."""
    with pytest.raises(SystemExit) as refused:
        add(repo, "--model", "sonnet")

    assert refused.value.code == 2
    assert "STATE=VALUE" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_a_setting_naming_an_undeclared_state_is_refused_in_a_sentence(home, repo, capsys):
    assert add(repo, "--effort", "implemnt=low") == 2

    assert "implemnt" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_adding_an_entry_supervises_nothing(home, repo, no_tmux):
    """It must return promptly: a tool call that becomes a process blocking for
    hours is the failure the Queue exists to avoid."""
    add(repo, "--branch", "TASK-8546")

    assert no_tmux.spawned == []
    assert RunStore(home / "runs").all() == []
    assert queue_of(home).all()[0].run_id is None


def test_entries_added_in_a_row_each_get_their_own_place_in_the_queue(home, repo):
    """Ids are sortable timestamps, so adding twice in quick succession queues
    two Entries in the order they arrived rather than colliding."""
    add(repo, "--branch", "TASK-8546")
    add(repo, "--branch", "TASK-8547")

    ids = [held.id for held in queue_of(home).all()]
    assert ids == sorted(ids)
    assert [held.working_branch for held in queue_of(home).all()] == [
        "TASK-8546",
        "TASK-8547",
    ]


def test_adding_an_entry_with_no_working_branch_queues_branchless_work(home, repo, capsys):
    """Omission is intent: the Entry records no Working branch, and
    the agent at the head of its Run derives and declares one there."""
    assert add(repo) == 0

    (queued,) = queue_of(home).all()
    assert queued.working_branch is None
    assert "None" not in capsys.readouterr().out


def test_two_branchless_entries_for_the_same_repository_coexist(home, repo):
    assert add(repo) == 0
    assert add(repo) == 0

    assert [held.working_branch for held in queue_of(home).all()] == [None, None]


def test_adding_an_entry_on_a_branch_another_entry_claims_is_refused(home, repo, capsys):
    add(repo, "--branch", "TASK-8546")

    assert add(repo, "--branch", "TASK-8546") == 2

    assert "TASK-8546" in capsys.readouterr().err
    assert len(queue_of(home).all()) == 1


def test_adding_an_entry_starting_at_an_undeclared_state_is_refused(home, repo, capsys):
    assert add(repo, "--branch", "TASK-8546", "--at", "grrill") == 2

    assert "grrill" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_adding_a_workflow_with_an_unknown_key_is_refused_in_a_sentence(home, repo, capsys):
    (repo / "workflow.toml").write_text(
        WORKFLOW.replace('name = "grill"', 'name = "grill"\nquestons = "human"')
    )

    assert add(repo, "--branch", "TASK-8546") == 2

    err = capsys.readouterr().err
    assert "unknown key 'questons' in state 'grill'" in err
    assert "allowed: name, prompt, clear, terminal, next, model, effort, questions" in err
    assert "Traceback" not in err
    assert queue_of(home).all() == []


def test_adding_by_bare_name_queues_the_library_file_of_that_stem(home, repo, capsys):
    """A bare name is entrance-side shorthand: the Entry stores the resolved
    library path exactly as it stores one typed explicitly."""
    library = home / "workflows"
    library.mkdir(parents=True)
    (library / "feature.toml").write_text(WORKFLOW)

    assert main(["queue", "add", "feature", "add dark mode", "--repo", str(repo)]) == 0

    (queued,) = queue_of(home).all()
    assert queued.workflow_path == library / "feature.toml"


def test_adding_by_a_name_the_library_does_not_hold_is_refused(home, repo, capsys):
    assert main(["queue", "add", "featuer", "add dark mode", "--repo", str(repo)]) == 2

    err = capsys.readouterr().err
    assert "no workflow named 'featuer'" in err
    assert queue_of(home).all() == []


def test_listing_shows_entries_in_queue_order_with_what_became_of_each(home, repo, capsys):
    add(repo, "--branch", "TASK-8546")
    add(repo, "--branch", "TASK-8547")
    first, second = queue_of(home).all()

    assert main(["queue", "list"]) == 0

    printed = capsys.readouterr().out
    assert printed.index(shown_as(first.id)) < printed.index(shown_as(second.id))
    assert printed.count("waiting") == 2
    assert "TASK-8546" in printed and "add dark mode" in printed


def run_entry(home, repo, name, *, start_state="grill"):
    """An Entry whose Run exists, named so its line can be found in a listing."""
    run = RunStore(home / "runs").create(
        run_id=f"{name}-run",
        workflow_path=repo / "workflow.toml",
        task=f"task of {name}",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
        start_state=start_state,
    )
    queue_of(home).add(
        Entry(
            id=name,
            workflow_path=repo / "workflow.toml",
            task=f"task of {name}",
            target_repo=repo,
            working_branch=None,
            created_at="2026-07-22T12:00:00Z",
            run_id=run.id,
        )
    )
    return run


# The lines drawn before a Child's id, joining it to its Parent's row.
TREE = re.compile(r"^[├└] ")

COLUMNS = ["ID", "STATUS", "STATE", "REPO", "BRANCH", "TASK"]


def shown_as(entry_id):
    """The short form a listing shows an Entry by, among the Queue's Entries
    as they are now."""
    return short_ids(entry.id for entry in Queue(default_queue_root()).all())[entry_id]


def listed(capsys):
    """The lines `naiad queue list` prints, with nothing printed before it."""
    capsys.readouterr()
    assert main(["queue", "list"]) == 0
    return capsys.readouterr().out.splitlines()


def row_of(lines, entry_id):
    """One Entry's row among a listing's lines."""
    (row,) = [line for line in lines if TREE.sub("", line).split("  ")[0] == shown_as(entry_id)]
    return row


def _cells(capsys, entry_id):
    """One Entry's row in a listing, split into cells told apart by two
    spaces or more, with any tree drawn before a Child's id left off."""
    return re.split(r"\s{2,}", TREE.sub("", row_of(listed(capsys), entry_id)))


def status_shown(capsys, entry_id):
    """The word in the status column of one Entry's row, after its mark."""
    mark, word = _cells(capsys, entry_id)[1].split(" ")
    assert mark == GLYPHS[word]
    return word


def standing_shown(capsys, entry_id):
    """The State column of one Entry's line: the third cell, after the id and
    the status."""
    return _cells(capsys, entry_id)[2]


def test_listing_shows_the_settings_an_entry_names_beneath_its_line(home, repo, capsys):
    """What a night's work will run on is read before it is committed to, so
    the settings an Entry names are shown where its line is."""
    add(repo, "--model", "implement=sonnet", "--effort", "implement=medium")
    add(repo, "--branch", "TASK-8547")
    named, plain = queue_of(home).all()

    lines = listed(capsys)

    under_named = lines[lines.index(row_of(lines, named.id)) + 1]
    assert under_named.startswith("  ")
    assert under_named.split() == ["implement:", "model", "sonnet,", "effort", "medium"]
    assert "model" not in row_of(lines, plain.id)
    assert sum("model" in line for line in lines) == 1


def test_listing_shows_a_dash_for_a_waiting_entry(home, repo, capsys):
    add(repo)
    (waiting,) = queue_of(home).all()

    assert standing_shown(capsys, waiting.id) == "—"


def test_listing_shows_the_recorded_start_state_of_a_run_that_has_not_announced(
    home, repo, capsys
):
    run_entry(home, repo, "fresh", start_state="implement")

    assert standing_shown(capsys, "fresh") == "implement"


def test_listing_shows_the_gate_a_parked_run_stands_at(home, repo, capsys):
    run = run_entry(home, repo, "parked")
    Notices(run.root).record_notified(Announcements(run.root).announce("review"))

    assert standing_shown(capsys, "parked") == "review"


class _Quiet:
    """Session, Notifier and Answerer at once for a tick that only parks: the
    loop's records are what these tests read, not what it sent anywhere."""

    def send(self, pane, text): ...

    def clear(self, pane): ...

    def notify(self, title, message, kind): ...

    def consult(self, spec): ...


def tick_at(run, seconds_idle):
    """One tick of the real loop, idle for this long since the Run's newest
    record, so the park it writes is the loop's own."""
    newest = max(path.stat().st_mtime for path in run.root.iterdir() if path.is_file())
    quiet = _Quiet()
    return tick(
        run=RunStore(run.root.parent).load(run.id),
        workflow=parse_workflow(WORKFLOW),
        session=quiet,
        notifier=quiet,
        answerer=quiet,
        now=newest + seconds_idle,
    )


def announced_and_handled(run):
    """A Run whose agent was given its Prompt and has since ended a turn."""
    run.attach_session(tmux_session=f"naiad-{run.id}", tmux_pane="%42")
    announcement = Announcements(run.root).announce("implement")
    Handled(run.root).record(announcement.seq)
    Turns(run.root).record_end(latest_seq=announcement.seq)


def held(run):
    """A Run whose agent relayed the human's 'pause', parked by the loop."""
    announced_and_handled(run)
    declare_hold("user typed 'pause'", run=run)
    assert isinstance(tick_at(run, 1), Notify)


def parked_after_a_hold(run):
    """A Hold, then the usual silence rule: Nudges run out and the loop parks
    the Run. A Wait stands between them because only a Wait or a new
    Announcement lifts a Hold, and the Hold count outlives the lifting."""
    announced_and_handled(run)
    declare_hold("user typed 'pause'", run=run)
    tick_at(run, 1)
    declare_wait("a background agent", run=run, now=time.time(), seconds=1)
    for _ in range(NUDGE_LIMIT + 1):
        action = tick_at(run, SILENCE_SECONDS * 2)
    assert isinstance(action, Notify) and "silent" in action.reason


JOINING = """
name = "fan-out"

[[states]]
name = "implement"
prompt = "take in {children}"
join = true

[[states]]
name = "done"
terminal = true

[[states]]
name = "build"
prompt = "build {subject}"
"""


def joining_parent(home, repo, *, child_finished, announced=True):
    """A Parent that has announced its Join State, with one started Child
    listed beneath it. Answers with the Child's working tree."""
    (repo / "workflow.toml").write_text(JOINING)
    parent = run_entry(home, repo, "parent", start_state="implement")
    worktree = repo.parent / "repo-wt--01"
    worktree.mkdir()
    child = RunStore(home / "runs").create(
        run_id="child-run",
        workflow_path=repo / "workflow.toml",
        task="t",
        target_repo=worktree,
        created_at="2026-07-22T12:00:00Z",
        start_state="build",
    )
    queue_of(home).add(
        Entry(
            id="child",
            workflow_path=repo / "workflow.toml",
            task="t",
            target_repo=worktree,
            working_branch="feat--01",
            created_at="2026-07-22T12:00:01Z",
            parent=parent.id,
            run_id=child.id,
        )
    )
    Children(parent.root).record_spawn("child", subject="01.md", worktree=worktree)
    Children(parent.root).record_start("child", run_id=child.id)
    if child_finished:
        RunLog(child.root).record(Finish(state="done"), seq=1)
    if announced:
        Announcements(parent.root).announce("implement")
    return worktree


def test_a_parent_held_at_a_join_state_reads_joining(home, repo, capsys):
    joining_parent(home, repo, child_finished=False)

    assert status_shown(capsys, "parent") == "joining"


def test_a_parent_adopted_at_a_held_join_state_reads_joining(home, repo, capsys):
    """Before it announces anything, an adopted Run is owed the Prompt of the
    State it was adopted at, and the tick holds that one too."""
    joining_parent(home, repo, child_finished=False, announced=False)
    parent = RunStore(home / "runs").load("parent-run")
    parent.adopted = True
    parent.save()

    assert status_shown(capsys, "parent") == "joining"


def test_a_parent_whose_join_is_released_reads_running(home, repo, capsys):
    joining_parent(home, repo, child_finished=True)

    assert status_shown(capsys, "parent") == "running"


def test_a_held_run_reads_parked(home, repo, capsys):
    """The Hold count keys the park the loop records, so a reading that asks
    without it finds the record stale and calls a Held Run running."""
    held(run_entry(home, repo, "held"))

    assert status_shown(capsys, "held") == "parked"


def test_a_run_parked_by_silence_after_a_hold_reads_parked(home, repo, capsys):
    parked_after_a_hold(run_entry(home, repo, "silent"))

    assert status_shown(capsys, "silent") == "parked"


def test_listing_shows_the_final_state_of_a_done_run(home, repo, capsys):
    run = run_entry(home, repo, "finished")
    Announcements(run.root).announce("done")
    RunLog(run.root).record(Finish(state="done"))

    assert standing_shown(capsys, "finished") == "done"


def test_listing_shows_an_announced_state_the_workflow_no_longer_declares(home, repo, capsys):
    """The Standing State is read from the Run alone, so editing the Workflow
    under a live Run cannot change or lose it."""
    run = run_entry(home, repo, "edited")
    Announcements(run.root).announce("implement")
    (repo / "workflow.toml").write_text(WORKFLOW.replace('name = "implement"', 'name = "build"'))

    assert standing_shown(capsys, "edited") == "implement"


def test_listing_marks_neither_a_question_nor_a_subject(home, repo, capsys):
    asking = run_entry(home, repo, "asking")
    Announcements(asking.root).ask(Question(text="which?", options=("a", "b")), state="implement")
    working = run_entry(home, repo, "working")
    Announcements(working.root).announce("implement", subject="docs/04-x.md")

    assert standing_shown(capsys, "asking") == "implement"
    assert standing_shown(capsys, "working") == "implement"


def test_listing_shows_a_dash_for_a_run_with_no_recorded_start_and_no_announcement(
    home, repo, capsys
):
    run_entry(home, repo, "legacy", start_state=None)

    assert standing_shown(capsys, "legacy") == "—"


def test_listing_heads_its_columns_and_pads_each_to_its_longest_cell(home, repo, capsys):
    """Padded to the cells rather than to fixed widths, because a State is
    named by the Workflow and Naiad knows no name in advance."""
    run_entry(home, repo, "longer", start_state="implement")
    add(repo)
    (waiting,) = [entry for entry in queue_of(home).all() if entry.id != "longer"]

    header, *rows = listed(capsys)

    assert header.split() == COLUMNS
    assert len(rows) == 2
    state_at = header.index("STATE")
    assert row_of(rows, "longer")[state_at:].startswith("implement  ")
    assert row_of(rows, waiting.id)[state_at:].startswith(f"{'—':<9}  ")
    branch_at = header.index("BRANCH")
    assert all(row[branch_at - 2 : branch_at] == "  " for row in rows)


def test_listing_shows_each_entry_by_the_shortest_form_of_its_id(home, repo, capsys):
    """What tells Entries apart is mostly the process id that ends theirs, so
    that is what is shown, lengthened where two Entries share it."""
    for entry_id in (PARENT_ID, CHILD_ID, SIBLING_ID):
        queued_as(home, repo, entry_id)

    _, *rows = listed(capsys)

    assert [row.split()[0] for row in rows] == [
        "51695",
        "573056-matt-pocock-56055",
        "573057-matt-pocock-56055",
    ]
    assert not any(PARENT_ID in row for row in rows)


def test_listing_shows_a_status_as_its_mark_and_its_word(home, repo, capsys):
    add(repo)
    (waiting,) = queue_of(home).all()

    assert _cells(capsys, waiting.id)[1] == f"{GLYPHS['waiting']} waiting"


def test_listing_shows_the_branch_a_run_declared_when_its_entry_named_none(
    home, repo, capsys
):
    """An Entry queued without a branch leaves the agent to derive one and
    declare it on the Run, so the Run is where the branch is read from."""
    declared = run_entry(home, repo, "declared")
    declared.working_branch = "feat/burrow-system"
    declared.save()
    run_entry(home, repo, "undeclared")

    assert _cells(capsys, "declared")[4] == "feat/burrow-system"
    assert _cells(capsys, "undeclared")[4] == "—"


def test_listing_shows_the_repository_whole_and_cuts_only_the_task(
    home, repo, capsys, monkeypatch
):
    """An agent tells a Child in flight by the working tree its row names, so
    the repository is never shortened to fit; the task gives way instead."""
    queued_as(home, repo, PARENT_ID, task="Build Burrow from the 55 tickets " * 10)
    header, *_ = listed(capsys)
    task_at = header.index("TASK")
    monkeypatch.setenv("COLUMNS", str(task_at + 30))

    row = row_of(listed(capsys), PARENT_ID)

    assert len(row) == task_at + 30
    assert row.endswith("…")
    assert str(repo) in row


def test_a_task_written_over_several_lines_is_listed_on_one(
    home, repo, capsys, monkeypatch
):
    """A batch file can hold a Task over several lines, and a row is one line."""
    monkeypatch.setenv("COLUMNS", "1000")
    queued_as(home, repo, PARENT_ID, task="Build Burrow\n\nfrom the tickets")
    queued_as(home, repo, CHILD_ID)

    header, first, second = listed(capsys)

    assert first.endswith("Build Burrow from the tickets")


def test_a_terminal_too_narrow_for_the_other_columns_still_shows_some_of_the_task(
    home, repo, capsys, monkeypatch
):
    queued_as(home, repo, PARENT_ID, task="Build Burrow from the 55 tickets " * 10)
    monkeypatch.setenv("COLUMNS", "40")

    lines = listed(capsys)

    row = row_of(lines, PARENT_ID)
    shown_task = row[lines[0].index("TASK") :]
    assert shown_task.startswith("Build Burrow from")
    assert shown_task.endswith("…")
    assert str(repo) in row


def test_listing_tells_apart_two_repositories_that_share_a_name(home, repo, tmp_path, capsys):
    """One Queue spans every repository, so two checkouts called `repo` are
    exactly the case a list has to distinguish."""
    namesake = tmp_path / "elsewhere" / "repo"
    namesake.mkdir(parents=True)
    (namesake / "workflow.toml").write_text(WORKFLOW)
    add(repo, "--branch", "TASK-8546")
    add(namesake, "--branch", "TASK-8546")
    capsys.readouterr()

    assert main(["queue", "list"]) == 0

    printed = capsys.readouterr().out
    assert str(repo) in printed and str(namesake) in printed


def test_listing_derives_what_became_of_an_entry_from_its_run(home, repo, capsys):
    """No status is stored, so a finished Run is what makes an Entry done."""
    run = RunStore(home / "runs").create(
        run_id="a-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )
    RunLog(run.root).record(Finish(state="done"))
    queue_of(home).add(
        Entry(
            id="an-entry",
            workflow_path=repo / "workflow.toml",
            task="add dark mode",
            target_repo=repo,
            working_branch="TASK-8546",
            created_at="2026-07-22T12:00:00Z",
            run_id="a-run",
        )
    )

    assert main(["queue", "list"]) == 0

    printed = capsys.readouterr().out
    assert "done" in printed
    # The Run is reached through its Entry, which `naiad queue answers` takes.
    assert "a-run" not in printed


def test_listing_a_queue_holding_an_unreadable_entry_reports_it(home, repo, capsys):
    """Read as a message rather than a traceback: the operator can see these
    files and so can damage one, and a stack trace is not something they can
    act on."""
    add(repo, "--branch", "TASK-8546")
    (document,) = (home / "queue").iterdir()
    document.write_text("{ not json")

    assert main(["queue", "list"]) == 2

    assert str(document) in capsys.readouterr().err


def test_listing_an_empty_queue_says_so_rather_than_printing_nothing(home, capsys):
    assert main(["queue", "list"]) == 0

    assert capsys.readouterr().out.strip() != ""


# `naiad queue watch`. The Supervisor against a real Queue is manual smoke — a
# loop that drives a real session through a fake tmux would be green over a
# system that does not work — so what is held here is the wiring: that the
# command supervises in follow mode, and that an Entry reaches the Run it
# becomes with everything it was queued with. The loop itself is covered in
# tests/test_supervisor.py and its rules in tests/test_supervise.py.


def supervision(monkeypatch):
    """Stand in for the Supervisor's loop, and record what it was wired with."""
    wiring = {}

    def fake(**arguments):
        wiring.update(arguments)

    monkeypatch.setattr("naiad.cli.main.supervise_queue", fake)
    return wiring


def test_watching_the_queue_supervises_in_follow_mode(home, monkeypatch):
    """Follow rather than drain, so that Entries added after the Supervisor
    started are picked up without starting anything again."""
    wiring = supervision(monkeypatch)

    assert main(["queue", "watch"]) == 0

    assert wiring["following"] is True
    assert wiring["queue"].root == home / "queue"
    assert wiring["runs"].root == home / "runs"


def test_watching_the_queue_starts_a_run_carrying_everything_the_entry_held(
    home, repo, monkeypatch, no_tmux
):
    """An Entry is a Run that does not exist yet, so every field it was queued
    with has to arrive at the Run — including the Predecessor the rules
    resolved, which is the Entry's alone to be told."""
    add(
        repo,
        "--branch",
        "TASK-8546",
        "--at",
        "implement",
        "--subject",
        "docs/ticket.md",
        "--skip-gates",
    )
    wiring = supervision(monkeypatch)

    assert main(["queue", "watch"]) == 0

    (queued,) = wiring["queue"].all()
    run = wiring["start"](queued, "TASK-8000")
    assert run.task == "add dark mode"
    assert run.target_repo == repo
    assert run.working_branch == "TASK-8546"
    assert run.predecessor == "TASK-8000"
    assert run.start_state == "implement"
    assert run.skip_gates is True
    assert no_tmux.spawned


# The ceiling is resolved once, as the Supervisor starts: the option, then the
# environment variable, then what the machine's memory allows.


class SixteenGibibytes:
    def total_memory(self):
        return 16 * (1 << 30)


def test_the_capacity_option_beats_the_environment_variable(home, monkeypatch):
    monkeypatch.setenv("NAIAD_CAPACITY", "20")
    wiring = supervision(monkeypatch)

    assert main(["queue", "watch", "--capacity", "3"]) == 0

    assert wiring["ceiling"] == 3


def test_the_environment_variable_beats_the_derived_ceiling(home, monkeypatch):
    monkeypatch.setenv("NAIAD_CAPACITY", "20")
    monkeypatch.setattr("naiad.cli.main.Machine", SixteenGibibytes)
    wiring = supervision(monkeypatch)

    assert main(["queue", "watch"]) == 0

    assert wiring["ceiling"] == 20


def test_with_neither_the_ceiling_is_derived_from_the_machines_memory(home, monkeypatch):
    monkeypatch.setattr("naiad.cli.main.Machine", SixteenGibibytes)
    wiring = supervision(monkeypatch)

    assert main(["queue", "watch"]) == 0

    assert wiring["ceiling"] == 5


def test_the_supervisor_reads_this_machine_for_pressure_and_disk(home, monkeypatch):
    monkeypatch.setattr("naiad.cli.main.Machine", SixteenGibibytes)
    wiring = supervision(monkeypatch)

    assert main(["queue", "watch"]) == 0

    assert isinstance(wiring["machine"], SixteenGibibytes)


@pytest.mark.parametrize("capacity", ["0", "-1", "two", "2.5"])
def test_a_capacity_option_that_is_not_a_positive_whole_number_is_refused(
    home, monkeypatch, capsys, capacity
):
    refused = supervision(monkeypatch)

    with pytest.raises(SystemExit):
        main(["queue", "watch", "--capacity", capacity])

    assert refused == {}
    assert "positive whole number" in capsys.readouterr().err


def test_a_capacity_variable_that_is_not_a_positive_whole_number_is_refused(
    home, monkeypatch, capsys
):
    monkeypatch.setenv("NAIAD_CAPACITY", "twenty")
    refused = supervision(monkeypatch)

    assert main(["queue", "watch"]) == 2

    assert refused == {}
    assert "NAIAD_CAPACITY" in capsys.readouterr().err


def test_a_second_supervisor_is_refused(home, monkeypatch, capsys):
    """Two Supervisors each take the first waiting Entry and put two agents in
    one working tree, which is the single thing one-at-a-time exists to
    prevent. Refused rather than queued behind the first, since a command that
    silently waited for hours would look like one that had started."""

    def fake(**_arguments):
        raise AssertionError("a second supervisor was started")

    monkeypatch.setattr("naiad.cli.main.supervise_queue", fake)

    with SupervisorLock(home / "supervisor.lock").taken() as mine:
        assert mine
        assert main(["queue", "watch"]) == 2

    assert "already running" in capsys.readouterr().err


def test_interrupting_the_supervisor_leaves_nothing_to_clean_up(home, monkeypatch):
    """Ctrl-C is how an operator stops the night. It stops a Supervisor exactly
    as it stops a watch: the Queue is on disk and the sessions are left alive."""

    def interrupted(**_arguments):
        raise KeyboardInterrupt

    monkeypatch.setattr("naiad.cli.main.supervise_queue", interrupted)

    assert main(["queue", "watch"]) == 0


def test_a_damaged_entry_stops_the_supervisor_with_a_message(home, repo, capsys):
    """Read as a message rather than a traceback, as listing one is: an
    operator can see these files and so can damage one."""
    add(repo, "--branch", "TASK-8546")
    (document,) = (home / "queue").iterdir()
    document.write_text("{ not json")

    assert main(["queue", "watch"]) == 2

    assert str(document) in capsys.readouterr().err


def test_removing_an_entry_takes_it_out_of_the_queue(home, repo, capsys):
    add(repo, "--branch", "TASK-8546")
    add(repo, "--branch", "TASK-8547")
    first, second = queue_of(home).all()

    assert main(["queue", "rm", first.id]) == 0

    assert [held.id for held in queue_of(home).all()] == [second.id]
    assert first.id in capsys.readouterr().out


def queued_run(home, repo, *, pane="%7", state="implement"):
    """An Entry that has become a Run, standing in a State with a session of
    its own — which is the case removal has to release."""
    run = RunStore(home / "runs").create(
        run_id="a-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )
    run.attach_session(tmux_session="naiad-a-run", tmux_pane=pane)
    Announcements(run.root).announce(state)
    queue_of(home).add(
        Entry(
            id="an-entry",
            workflow_path=repo / "workflow.toml",
            task="add dark mode",
            target_repo=repo,
            working_branch="TASK-8546",
            created_at="2026-07-22T12:00:00Z",
            run_id="a-run",
        )
    )
    return run


def test_removing_an_entry_keeps_the_run_it_produced(home, repo):
    """Nothing is deleted: the Run log is the diagnostic, and only a Prune ever
    removes a Run."""
    run = queued_run(home, repo)

    assert main(["queue", "rm", "an-entry"]) == 0

    assert queue_of(home).all() == []
    assert json.loads(run.metadata_path.read_text())["task"] == "add dark mode"


def test_removing_an_entry_cancels_the_run_and_releases_its_session(home, repo):
    """The Session is released by the Run ending, and the seam every hook and
    Protocol verb asks is what stops answering."""
    run = queued_run(home, repo)

    assert main(["queue", "rm", "an-entry"]) == 0

    assert RunLog(run.root).ended() is True
    resolver = RunResolver(RunStore(home / "runs"), environ={})
    assert resolver.resolve(tmux_pane="%7") is None


def test_removing_an_entry_names_the_session_the_operator_now_has(home, repo, capsys):
    """Nothing is typed into that session — the agent learns at its next verb,
    from the refusal. So the one thing said out loud is said to the operator,
    who can go and read what the agent was doing."""
    queued_run(home, repo)

    assert main(["queue", "rm", "an-entry"]) == 0

    printed = capsys.readouterr().out
    assert "a-run" in printed
    assert "%7" in printed


def words_of(printed):
    """What a terminal was shown, without its escape codes: the words a reader
    off a terminal is given."""
    return re.sub(r"\x1b\[[0-9;]*m", "", printed)


def test_removing_an_entry_says_what_was_removed_and_cancelled_in_these_words(
    home, repo, capsys
):
    queued_run(home, repo)

    assert main(["queue", "rm", "an-entry"]) == 0

    assert capsys.readouterr().out == (
        "removed an-entry\ncancelled run a-run; its session at pane %7 is yours\n"
    )


def test_removing_an_entry_says_the_same_words_coloured_at_a_terminal(home, repo, monkeypatch):
    queued_run(home, repo)
    terminal = to_terminal(monkeypatch)

    assert main(["queue", "rm", "an-entry"]) == 0

    printed = terminal.getvalue()
    assert ESCAPE in printed
    assert words_of(printed) == (
        "removed an-entry\ncancelled run a-run; its session at pane %7 is yours\n"
    )


def test_a_cancellation_names_its_run_and_pane_as_ids(home, repo):
    run = queued_run(home, repo)

    assert styles_of(_cancellation_line(run)) == {"a-run": "id", "%7": "id"}


def test_removing_a_waiting_entry_says_nothing_about_a_session(home, repo, capsys):
    """There is no Run and so no Session, and a line about one would send the
    operator looking for a session that was never opened."""
    add(repo, "--branch", "TASK-8546")
    (waiting,) = queue_of(home).all()

    assert main(["queue", "rm", waiting.id]) == 0

    assert "session" not in capsys.readouterr().out


def test_an_entry_whose_run_will_not_take_the_ending_stays_in_the_queue(
    home, repo, capsys, monkeypatch
):
    """The refusal question 5 settles: the ending goes first, so a Run that
    cannot take it leaves the Entry where the operator can see it and try
    again — rather than an orphan still driving its Session."""
    queued_run(home, repo)

    def refuse(_self, *, state):
        raise OSError("read-only file system")

    monkeypatch.setattr(RunLog, "record_cancellation", refuse)

    assert main(["queue", "rm", "an-entry"]) == 2

    assert [held.id for held in queue_of(home).all()] == ["an-entry"]
    assert "a-run" in capsys.readouterr().err


def test_removing_an_entry_that_is_not_there_is_reported(home, repo, capsys):
    assert main(["queue", "rm", "no-such-entry"]) == 2

    assert "no-such-entry" in capsys.readouterr().err


PARENT_ID = "20261005-012208-211125-matt-pocock-51695"
CHILD_ID = "20261005-012443-573056-matt-pocock-56055"
SIBLING_ID = "20261005-012443-573057-matt-pocock-56055"


def queued_as(home, repo, entry_id, *, task=None, **fields):
    """A waiting Entry under an id shaped as Naiad makes them, so that the
    short form a listing shows can be typed back."""
    entry = Entry(
        id=entry_id,
        workflow_path=repo / "workflow.toml",
        task=task or f"task of {entry_id}",
        target_repo=repo,
        working_branch=None,
        created_at="2026-10-05T01:22:08Z",
        **fields,
    )
    queue_of(home).add(entry)
    return entry


def test_removing_an_entry_by_the_short_form_the_listing_shows(home, repo, capsys):
    queued_as(home, repo, PARENT_ID)
    queued_as(home, repo, CHILD_ID)

    assert main(["queue", "rm", "51695"]) == 0

    assert [held.id for held in queue_of(home).all()] == [CHILD_ID]
    assert f"removed {PARENT_ID}" in capsys.readouterr().out


def test_a_short_form_naming_several_entries_is_refused_and_removes_nothing(
    home, repo, capsys
):
    """Two Entries one agent queued in a turn share a process id. Choosing
    between them would cancel work nobody named."""
    queued_as(home, repo, CHILD_ID)
    queued_as(home, repo, SIBLING_ID)

    assert main(["queue", "rm", "56055"]) == 2

    assert len(queue_of(home).all()) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("naiad: ")
    assert CHILD_ID in captured.err and SIBLING_ID in captured.err


def test_a_part_of_an_id_that_is_not_whole_names_nothing(home, repo, capsys):
    queued_as(home, repo, PARENT_ID)

    assert main(["queue", "rm", "1695"]) == 2

    assert len(queue_of(home).all()) == 1


# `naiad queue add --file`. A night's work as one document, which is how an
# operator reviews it before committing to it — so what is held here is that
# the file reaches the Queue whole or not at all, and that the entrance refuses
# anything it would otherwise have to ignore. Reading the file is tested in
# tests/test_batch.py and queueing what it declares in tests/test_enqueue.py.


BATCH = """
workflow = "{workflow}"
repo = "{repo}"

[[entries]]
task = "the login redirect loops"
branch = "TASK-8546"
at = "grill"

[[entries]]
task = "design the audit log"
branch = "TASK-8547"
at = "implement"
subject = "docs/ticket.md"
base = "TASK-8000"
skip-gates = true
"""


def batch_file(repo, text=BATCH):
    path = repo / "batch.toml"
    path.write_text(text.format(workflow=repo / "workflow.toml", repo=repo))
    return path


def test_a_batch_file_queues_every_entry_it_declares_in_file_order(home, repo, capsys):
    assert main(["queue", "add", "--file", str(batch_file(repo))]) == 0

    first, second = queue_of(home).all()
    assert first.task == "the login redirect loops"
    assert second.task == "design the audit log"
    printed = capsys.readouterr().out
    assert first.id in printed and second.id in printed


def test_each_entry_in_a_batch_carries_what_it_declared_for_itself(home, repo):
    main(["queue", "add", "--file", str(batch_file(repo))])

    first, second = queue_of(home).all()
    assert first.working_branch == "TASK-8546"
    assert first.start_state == "grill"
    assert first.skip_gates is False
    assert second.working_branch == "TASK-8547"
    assert second.start_state == "implement"
    assert second.subject == "docs/ticket.md"
    assert second.pinned_base == "TASK-8000"
    assert second.skip_gates is True


def test_a_batch_naming_a_different_workflow_per_entry_still_queues_in_file_order(home, repo):
    """Queue order is id order, and file order is what the Predecessor rule
    reads — so an Entry's place in the file has to outrank the name of the
    Workflow its id is built from."""
    (repo / "zebra.toml").write_text(WORKFLOW)
    (repo / "alpha.toml").write_text(WORKFLOW)
    path = repo / "batch.toml"
    path.write_text(
        f"""
        repo = "{repo}"

        [[entries]]
        workflow = "{repo / "zebra.toml"}"
        task = "first"
        branch = "TASK-8546"

        [[entries]]
        workflow = "{repo / "alpha.toml"}"
        task = "second"
        branch = "TASK-8547"
        """
    )

    assert main(["queue", "add", "--file", str(path)]) == 0

    assert [held.task for held in queue_of(home).all()] == ["first", "second"]


def test_an_entry_naming_no_repository_stands_in_the_working_directory(
    home, repo, monkeypatch
):
    monkeypatch.chdir(repo)
    path = repo / "batch.toml"
    path.write_text(
        f"""
        workflow = "{repo / "workflow.toml"}"

        [[entries]]
        task = "one"
        branch = "TASK-8546"
        """
    )

    assert main(["queue", "add", "--file", "batch.toml"]) == 0

    assert queue_of(home).all()[0].target_repo == repo


def test_a_batch_with_one_bad_entry_queues_none_of_them(home, repo, capsys):
    path = batch_file(
        repo,
        BATCH.replace('at = "grill"', 'at = "grrill"'),
    )

    assert main(["queue", "add", "--file", str(path)]) == 2

    reported = capsys.readouterr().err
    assert str(path) in reported and "entry 1" in reported
    assert queue_of(home).all() == []


def test_a_batch_file_that_is_not_valid_toml_is_reported_naming_the_file(home, repo, capsys):
    path = repo / "batch.toml"
    path.write_text("[[entries]\ntask = ")

    assert main(["queue", "add", "--file", str(path)]) == 2

    assert str(path) in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_a_batch_file_that_cannot_be_read_is_reported(home, repo, capsys):
    assert main(["queue", "add", "--file", str(repo / "nowhere.toml")]) == 2

    assert "nowhere.toml" in capsys.readouterr().err


def test_a_batch_file_with_settings_on_the_command_line_says_no_file_can_hold_them(
    home, repo, capsys
):
    """A batch file has no key for a setting, so the usual advice — move the
    option into the file — would send the operator to a refusal."""
    assert (
        main(["queue", "add", "--file", str(batch_file(repo)), "--model", "implement=sonnet"])
        == 2
    )

    refused = capsys.readouterr().err
    assert "--model" in refused and "batch file" in refused and "belong in the file" not in refused
    assert queue_of(home).all() == []


def test_a_batch_file_and_options_describing_one_entry_cannot_be_given_together(
    home, repo, capsys
):
    """Refused rather than one silently ignoring the other: an operator who
    typed both believes both were read."""
    assert (
        main(
            [
                "queue",
                "add",
                str(repo / "workflow.toml"),
                "add dark mode",
                "--branch",
                "TASK-8546",
                "--file",
                str(batch_file(repo)),
            ]
        )
        == 2
    )

    assert "--file" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_adding_with_neither_a_file_nor_a_task_is_refused(home, capsys):
    assert main(["queue", "add"]) == 2

    assert "--file" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_adding_with_only_a_subject_takes_it_as_the_task(home, repo):
    """Work described mid-workflow — `--at implement --subject
    <ticket>` — needs no task typed twice; the Subject stands in."""
    assert (
        main(
            [
                "queue",
                "add",
                str(repo / "workflow.toml"),
                "--repo",
                str(repo),
                "--at",
                "implement",
                "--subject",
                "docs/ticket.md",
            ]
        )
        == 0
    )

    (queued,) = queue_of(home).all()
    assert queued.task == "docs/ticket.md"


def test_adding_a_workflow_with_neither_a_task_nor_a_subject_is_refused(home, repo, capsys):
    assert main(["queue", "add", str(repo / "workflow.toml"), "--repo", str(repo)]) == 2

    err = capsys.readouterr().err
    assert "--subject" in err
    # The remedy speaks this command's vocabulary, not naiad run's.
    assert "naiad queue add" in err
    assert queue_of(home).all() == []


def test_a_batched_entry_carries_no_mark_of_the_file_it_came_from(home, repo):
    """An id sorts, and that is the whole of its job. One that carried its place
    in a file would be the Queue knowing a batch arrived — which it does not,
    because nothing has been asked of it that requires knowing."""
    main(["queue", "add", "--file", str(batch_file(repo))])
    add(repo, "--branch", "TASK-8548")

    batched, also_batched, alone = queue_of(home).all()
    assert len(batched.id.split("-")) == len(alone.id.split("-"))
    assert batched.id < also_batched.id < alone.id


# `naiad queue prune`. Which Entries it takes is tested against the store in
# tests/test_queue_store.py; what is held here is the command an operator meets
# — exit status, what is printed, and that it needs nothing typed to be safe.


def finished(home, repo, entry_id, run_id):
    """A done Entry: a Run whose log records an ending, and the Entry that
    became it."""
    run = RunStore(home / "runs").create(
        run_id=run_id,
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )
    RunLog(run.root).record(Finish(state="done"))
    queue_of(home).add(
        Entry(
            id=entry_id,
            workflow_path=repo / "workflow.toml",
            task="add dark mode",
            target_repo=repo,
            working_branch="TASK-8546",
            created_at="2026-07-22T12:00:00Z",
            run_id=run_id,
        )
    )
    return run


def test_pruning_reaches_both_stores_from_the_command(home, repo):
    """The wiring rather than the rule: that the command reaches the Queue and
    the Runs under the Naiad home, and that both give up what a Prune takes.
    Which Entries qualify is held in tests/test_queue_store.py."""
    run = finished(home, repo, entry_id="done-entry", run_id="a-run")

    assert main(["queue", "prune"]) == 0

    assert queue_of(home).all() == []
    assert not run.root.exists()


def test_pruning_leaves_everything_that_is_not_done(home, repo):
    """Waiting work is future work, and a Prune is not the way to cancel it."""
    add(repo, "--branch", "TASK-8547")
    finished(home, repo, entry_id="done-entry", run_id="a-run")

    assert main(["queue", "prune"]) == 0

    (left,) = queue_of(home).all()
    assert left.working_branch == "TASK-8547"


def test_pruning_names_each_entry_it_took_and_says_how_many(home, repo, capsys):
    """The printed lines are the report. Nothing is typed to confirm, because a
    Prune can reach nothing but done work — so there is nothing to confirm."""
    finished(home, repo, entry_id="first-entry", run_id="first-run")
    finished(home, repo, entry_id="second-entry", run_id="second-run")

    assert main(["queue", "prune"]) == 0

    printed = capsys.readouterr().out
    assert "first-entry" in printed and "second-entry" in printed
    assert "add dark mode" in printed
    assert "2" in printed


def test_pruning_says_the_same_words_coloured_at_a_terminal(home, repo, monkeypatch, capsys):
    finished(home, repo, entry_id="first-entry", run_id="first-run")
    RunLog(orphan(home, repo).root).record(Finish(state="done"))
    terminal = to_terminal(monkeypatch)

    assert main(["queue", "prune"]) == 0

    printed = terminal.getvalue()
    assert ESCAPE in printed
    assert words_of(printed) == (
        "pruned first-entry  add dark mode\npruned orphaned run orphaned-run\n2 pruned\n"
    )


def test_pruning_a_queue_with_nothing_done_says_so_rather_than_printing_nothing(
    home, repo, capsys
):
    add(repo, "--branch", "TASK-8546")

    assert main(["queue", "prune"]) == 0

    assert capsys.readouterr().out.strip() != ""
    assert len(queue_of(home).all()) == 1


def test_pruning_an_empty_queue_is_not_a_failure(home, capsys):
    assert main(["queue", "prune"]) == 0


def test_pruning_reports_a_run_directory_that_would_not_go(home, repo, capsys, monkeypatch):
    """The Entry is gone and the Run stayed, which is an orphan the operator can
    only act on if they are told its path. Reported as a failure, since
    something they asked for did not happen."""
    run = finished(home, repo, entry_id="done-entry", run_id="a-run")

    def refuse(*_arguments, **_keywords):
        raise OSError("device or resource busy")

    monkeypatch.setattr("naiad.runtime.run.shutil.rmtree", refuse)

    assert main(["queue", "prune"]) == 2

    assert queue_of(home).all() == []
    assert str(run.root) in capsys.readouterr().err


def orphan(home, repo, run_id="orphaned-run"):
    """A Run directory no Entry names."""
    return RunStore(home / "runs").create(
        run_id=run_id,
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )


def test_pruning_takes_a_finished_orphaned_run_and_prints_its_line(home, repo, capsys):
    """An orphan has no line in the listing, so the removal's printed line is
    the only record it ever gets."""
    run = orphan(home, repo)
    RunLog(run.root).record(Finish(state="done"))

    assert main(["queue", "prune"]) == 0

    assert not run.root.exists()
    assert "orphaned-run" in capsys.readouterr().out


def test_a_running_orphan_is_left_and_named_without_failing(home, repo, capsys):
    """Skipping a running orphan is a judgment deferred to the operator, not
    something that went wrong — so it is named on stdout and the exit is 0."""
    run = orphan(home, repo)
    Announcements(run.root).announce("implement")

    assert main(["queue", "prune"]) == 0

    assert run.root.is_dir()
    assert str(run.root) in capsys.readouterr().out


def test_pruning_takes_an_orphan_parked_after_a_hold(home, repo):
    """Parked is finished history to a Prune, Held or not."""
    run = orphan(home, repo)
    parked_after_a_hold(run)

    assert main(["queue", "prune"]) == 0

    assert not run.root.exists()


def test_pruning_takes_a_held_orphan(home, repo):
    run = orphan(home, repo)
    held(run)

    assert main(["queue", "prune"]) == 0

    assert not run.root.exists()


def test_pruning_a_queue_holding_a_damaged_entry_reports_it_and_takes_nothing(
    home, repo, capsys
):
    """Read as a message rather than a traceback, as listing one is — and read
    whole before anything is deleted, because the unreadable file might be the
    done one."""
    run = finished(home, repo, entry_id="done-entry", run_id="a-run")
    (home / "queue" / "damaged.json").write_text("{ not json")

    assert main(["queue", "prune"]) == 2

    assert "damaged.json" in capsys.readouterr().err
    assert run.root.is_dir()


def test_removing_a_done_entry_claims_no_cancellation(home, repo, capsys):
    """Its Run ended on its own and released its Session then. Saying it was
    cancelled would hand the operator a session that was never theirs to take,
    and would claim an act this removal did not make."""
    run = queued_run(home, repo)
    RunLog(run.root).record(Finish(state="done"), seq=2)

    assert main(["queue", "rm", "an-entry"]) == 0

    printed = capsys.readouterr().out
    assert "cancelled" not in printed
    assert [line.kind for line in RunLog(run.root).entries()] == ["finished"]


def test_a_run_cancelled_before_its_session_was_recorded_offers_no_pane(home, repo, capsys):
    """The window between a Run's directory being made and its session being
    attached. Offering a session here would send the operator looking for one
    that was never opened."""
    run = RunStore(home / "runs").create(
        run_id="a-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )
    queue_of(home).add(
        Entry(
            id="an-entry",
            workflow_path=repo / "workflow.toml",
            task="add dark mode",
            target_repo=repo,
            working_branch="TASK-8546",
            created_at="2026-07-22T12:00:00Z",
            run_id="a-run",
        )
    )

    assert main(["queue", "rm", "an-entry"]) == 0

    printed = capsys.readouterr().out
    assert "cancelled run a-run" in printed
    assert "pane" not in printed
    assert RunLog(run.root).ended() is True


# `naiad queue answers` is the operator's only way to read what the Answerer,
# the Workflow and the agent between them did with every Question.

RETRIES = Question(text="Which module owns retries?", options=("the client", "the caller"))
VENDOR = Question(text="Which SMS vendor?", options=("Twilio", "Vonage"))
CACHE = Question(text="Should the cache be flushed?", options=("yes", "no"))
PORT = Question(text="May I stop the server on :3939?", options=("Yes", "No"))


def answers_printed(capsys, argument):
    capsys.readouterr()
    status = main(["queue", "answers", argument])
    printed = capsys.readouterr()
    return status, printed.out, printed.err


def test_a_run_prints_one_block_per_question_with_the_outcome_of_each(home, repo, capsys):
    run = run_entry(home, repo, "night")
    log = AnswerLog(run.root)
    log.record(question=RETRIES, answer="the client, since it backs off", state="implement")
    log.record(
        question=VENDOR, answer="picking a vendor is not in this repository",
        state="grill", escalated=True,
    )
    log.record(
        question=CACHE, answer="the implement State reserves its Questions for the human",
        state="implement", escalated=True,
    )
    log.record(
        question=PORT, answer="the agent announced 'done' and moved on",
        state="implement", abandoned=True,
    )

    status, out, _ = answers_printed(capsys, "night")

    assert status == 0
    assert out == (
        "1  implement\n"
        "   Which module owns retries?\n"
        "   options:\n"
        "     - the client\n"
        "     - the caller\n"
        "   → answerer: the client, since it backs off\n"
        "\n"
        "2  grill\n"
        "   Which SMS vendor?\n"
        "   options:\n"
        "     - Twilio\n"
        "     - Vonage\n"
        "   → yours: picking a vendor is not in this repository\n"
        "\n"
        "3  implement\n"
        "   Should the cache be flushed?\n"
        "   options:\n"
        "     - yes\n"
        "     - no\n"
        "   → yours: the implement State reserves its Questions for the human\n"
        "\n"
        "4  implement\n"
        "   May I stop the server on :3939?\n"
        "   options:\n"
        "     - Yes\n"
        "     - No\n"
        "   → abandoned: the agent announced 'done' and moved on\n"
    )


def test_a_run_id_is_accepted_as_well_as_an_entry_id(home, repo, capsys):
    run = run_entry(home, repo, "night")
    AnswerLog(run.root).record(question=RETRIES, answer="the client", state="implement")

    by_entry = answers_printed(capsys, "night")
    by_run = answers_printed(capsys, run.id)

    assert by_run == by_entry
    assert "→ answerer: the client" in by_run[1]


def test_a_run_no_entry_became_is_read_by_its_run_id(home, repo, capsys):
    run = RunStore(home / "runs").create(
        run_id="loose-run",
        workflow_path=repo / "workflow.toml",
        task="adopted work",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )
    AnswerLog(run.root).record(question=RETRIES, answer="the client")

    status, out, _ = answers_printed(capsys, "loose-run")

    assert status == 0
    assert out.startswith("1\n   Which module owns retries?")


def test_an_answer_logged_before_states_were_recorded_prints_no_state(home, repo, capsys):
    run = run_entry(home, repo, "night")
    (run.root / "answers.json").write_text(
        json.dumps(
            [{"question": "Q?", "options": ["a"], "answer": "a", "escalated": False, "abandoned": False}]
        )
    )

    _, out, _ = answers_printed(capsys, "night")

    assert out.splitlines()[0] == "1"


def test_a_run_that_was_asked_nothing_says_so(home, repo, capsys):
    run = run_entry(home, repo, "night")

    status, out, _ = answers_printed(capsys, "night")

    assert status == 0
    assert out == f"no questions were asked in {run.id}\n"


def test_answers_are_coloured_at_a_terminal_with_the_same_words(home, repo, monkeypatch):
    run = run_entry(home, repo, "night")
    AnswerLog(run.root).record(question=RETRIES, answer="the client", state="implement")
    terminal = to_terminal(monkeypatch)

    assert main(["queue", "answers", "night"]) == 0

    printed = terminal.getvalue()
    assert ESCAPE in printed
    assert "→ answerer:" in printed and "Which module owns retries?" in printed


def test_an_entry_that_has_not_started_names_its_entry_as_an_id(home, repo, monkeypatch):
    add(repo)
    (waiting,) = queue_of(home).all()
    terminal = to_terminal(monkeypatch)

    assert main(["queue", "answers", waiting.id]) == 0

    assert ESCAPE in terminal.getvalue()


def test_an_entry_that_has_not_started_says_so(home, repo, capsys):
    add(repo)
    (waiting,) = queue_of(home).all()

    status, out, _ = answers_printed(capsys, waiting.id)

    assert status == 0
    assert out == f"{waiting.id} has not started, so it has no answers yet\n"


def test_naming_nothing_is_a_usage_error_and_never_defaults_to_the_latest_run(
    home, repo, capsys
):
    run_entry(home, repo, "night")

    with pytest.raises(SystemExit) as exited:
        main(["queue", "answers"])

    assert exited.value.code == 2


def test_an_argument_naming_neither_an_entry_nor_a_run_is_refused(home, repo, capsys):
    run_entry(home, repo, "night")

    status, out, err = answers_printed(capsys, "nigth")

    assert status == 2
    assert out == ""
    assert "nigth" in err


def test_an_entry_is_read_by_the_short_form_the_listing_shows(home, repo, capsys):
    run = run_entry(home, repo, PARENT_ID)
    AnswerLog(run.root).record(question=RETRIES, answer="the client", state="implement")

    status, out, _ = answers_printed(capsys, "51695")

    assert status == 0
    assert "→ answerer: the client" in out


def test_a_short_form_naming_several_entries_reads_no_answers(home, repo, capsys):
    run_entry(home, repo, CHILD_ID)
    run_entry(home, repo, SIBLING_ID)

    status, out, err = answers_printed(capsys, "56055")

    assert status == 2
    assert out == ""
    assert err.startswith("naiad: ")
    assert CHILD_ID in err and SIBLING_ID in err


def test_the_question_is_wrapped_to_the_terminal_width(home, repo, capsys, monkeypatch):
    run = run_entry(home, repo, "night")
    long = Question(text="word " * 30, options=("a",))
    AnswerLog(run.root).record(question=long, answer="a", state="implement")
    monkeypatch.setenv("COLUMNS", "40")

    _, out, _ = answers_printed(capsys, "night")

    wrapped = out.splitlines()[1:-4]
    assert len(wrapped) > 1
    assert all(len(line) <= 40 and line.startswith("   ") for line in wrapped)


def test_a_piped_run_wraps_at_eighty_columns(home, repo, capsys, monkeypatch):
    run = run_entry(home, repo, "night")
    long = Question(text="word " * 40, options=("a",))
    AnswerLog(run.root).record(question=long, answer="a", state="implement")
    monkeypatch.delenv("COLUMNS", raising=False)

    _, out, _ = answers_printed(capsys, "night")

    wrapped = out.splitlines()[1:-4]
    assert len(wrapped) > 1
    assert max(len(line) for line in wrapped) <= 80


def test_a_supervised_tick_names_the_entry_and_leaves_room_for_the_run_prefix(
    home, repo, monkeypatch
):
    run = run_entry(home, repo, "night")
    ticked = {}
    monkeypatch.setattr("naiad.cli.main.tick_once", lambda **arguments: ticked.update(arguments))

    _ticker()(run)

    assert ticked["entry_id"] == "night"
    assert ticked["lead"] == len(f"{run.id}  ")


CLEARING = Styled(Text.assemble(("clearing", "event.progress"), " ", ("grill", "state")))


def test_a_supervised_tick_says_each_line_after_the_run_it_belongs_to(
    home, repo, monkeypatch, capsys
):
    run = run_entry(home, repo, "night")
    ticked = {}
    monkeypatch.setattr("naiad.cli.main.tick_once", lambda **arguments: ticked.update(arguments))
    _ticker()(run)
    assert capsys.readouterr().out == f"watching {run.id}   (tmux attach -t {run.tmux_session})\n"

    ticked["report"](CLEARING)

    assert capsys.readouterr().out == f"{run.id}  clearing grill\n"


def test_a_supervised_tick_keeps_the_lines_styles_at_a_terminal(home, repo, monkeypatch):
    run = run_entry(home, repo, "night")
    ticked = {}
    monkeypatch.setattr("naiad.cli.main.tick_once", lambda **arguments: ticked.update(arguments))
    terminal = to_terminal(monkeypatch)

    _ticker()(run)
    ticked["report"](CLEARING)

    lines = terminal.getvalue().splitlines()
    assert len(lines) == 2
    assert all(ESCAPE in line for line in lines)


def test_watching_one_run_says_where_to_attach_styled_at_a_terminal(home, repo, monkeypatch):
    run = run_entry(home, repo, "night")
    monkeypatch.setattr("naiad.cli.main.watch", lambda **arguments: None)
    terminal = to_terminal(monkeypatch)

    _drive(run)

    assert ESCAPE in terminal.getvalue()


def test_a_watched_run_that_was_queued_names_its_entry_to_the_loop(home, repo, monkeypatch):
    run = run_entry(home, repo, "night")
    watched = {}
    monkeypatch.setattr("naiad.cli.main.watch", lambda **arguments: watched.update(arguments))

    _drive(run)

    assert watched["entry_id"] == "night"


def test_a_watched_run_that_was_never_queued_names_no_entry(home, repo, monkeypatch):
    run = RunStore(home / "runs").create(
        run_id="loose-run",
        workflow_path=repo / "workflow.toml",
        task="adopted work",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
    )
    watched = {}
    monkeypatch.setattr("naiad.cli.main.watch", lambda **arguments: watched.update(arguments))

    _drive(run)

    assert watched["entry_id"] is None


def test_listing_shows_each_child_beneath_its_parent_joined_by_a_tree(
    home, repo, tmp_path, capsys
):
    """A fan-out reads as one piece of work: each Child under the Entry whose
    Run spawned it, with its own status, whatever Queue order says."""
    parent = run_entry(home, repo, "a-parent")
    add(repo, "--branch", "TASK-8547")
    (unrelated,) = [entry for entry in queue_of(home).all() if entry.id != "a-parent"]
    for number in ("01", "02"):
        worktree = tmp_path / f"repo-wt--{number}"
        worktree.mkdir()
        queue_of(home).add(
            Entry(
                id=f"0-child{number}",
                workflow_path=repo / "workflow.toml",
                task=f"build ticket {number}",
                target_repo=worktree,
                working_branch=f"TASK-8546--{number}",
                created_at="2026-07-22T12:00:00Z",
                parent=parent.id,
                settings=(StateSetting(state="build", setting="model", value="sonnet"),),
            )
        )

    lines = listed(capsys)

    at = lines.index(row_of(lines, "a-parent"))
    first, first_settings, last, last_settings = lines[at + 1 : at + 5]
    assert first.startswith(f"├ {shown_as('0-child01')}  ") and "waiting" in first
    assert first_settings.startswith("│ ") and "build: model sonnet" in first_settings
    assert last.startswith(f"└ {shown_as('0-child02')}  ")
    assert last_settings.startswith("  ") and "build: model sonnet" in last_settings
    assert str(tmp_path / "repo-wt--01") in first
    assert not row_of(lines, unrelated.id).startswith((" ", "├", "└"))


# A Child limit, given at the entrance that queues the Parent.


def test_adding_an_entry_records_its_child_limit(home, repo):
    assert add(repo, "--branch", "TASK-8546", "--child-limit", "2") == 0

    (queued,) = queue_of(home).all()
    assert queued.child_limit == 2


def test_adding_an_entry_with_no_child_limit_records_none(home, repo):
    add(repo, "--branch", "TASK-8546")

    (queued,) = queue_of(home).all()
    assert queued.child_limit is None


@pytest.mark.parametrize("limit", ["0", "-1", "two", "1.5", "2_0", "+3", " 3"])
def test_a_child_limit_that_is_not_a_positive_whole_number_is_refused(
    home, repo, capsys, limit
):
    """A typo must not silently mean no limit."""
    with pytest.raises(SystemExit) as refused:
        add(repo, "--branch", "TASK-8546", f"--child-limit={limit}")

    assert refused.value.code == 2
    assert "--child-limit" in capsys.readouterr().err
    assert queue_of(home).all() == []


def test_a_batch_file_carries_a_child_limit_as_a_default_and_per_entry(home, repo):
    path = batch_file(repo, "child-limit = 1\n" + BATCH.replace(
        'skip-gates = true', 'skip-gates = true\nchild-limit = 3'
    ))

    assert main(["queue", "add", "--file", str(path)]) == 0

    first, second = queue_of(home).all()
    assert first.child_limit == 1
    assert second.child_limit == 3


def test_a_child_limit_beside_a_batch_file_is_refused(home, repo, capsys):
    """The option describes one Entry, and the file has its own key for it."""
    assert main(
        ["queue", "add", "--file", str(batch_file(repo)), "--child-limit", "2"]
    ) == 2

    assert queue_of(home).all() == []


def test_a_child_held_by_its_parents_limit_reads_waiting(home, repo, tmp_path, capsys):
    parent = RunStore(home / "runs").create(
        run_id="a-parent-run",
        workflow_path=repo / "workflow.toml",
        task="task of a-parent",
        target_repo=repo,
        created_at="2026-07-22T12:00:00Z",
        start_state="grill",
    )
    queue_of(home).add(
        Entry(
            id="a-parent",
            workflow_path=repo / "workflow.toml",
            task="task of a-parent",
            target_repo=repo,
            working_branch=None,
            created_at="2026-07-22T12:00:00Z",
            child_limit=1,
            run_id=parent.id,
        )
    )
    for name, run_id in (("0-live", "live-run"), ("1-held", None)):
        worktree = tmp_path / f"repo-wt-{name}"
        worktree.mkdir()
        if run_id is not None:
            RunStore(home / "runs").create(
                run_id=run_id,
                workflow_path=repo / "workflow.toml",
                task="build",
                target_repo=worktree,
                created_at="2026-07-22T12:00:00Z",
                start_state="grill",
            )
        queue_of(home).add(
            Entry(
                id=name,
                workflow_path=repo / "workflow.toml",
                task="build",
                target_repo=worktree,
                working_branch=f"TASK-8546--{name}",
                created_at="2026-07-22T12:00:00Z",
                parent=parent.id,
                run_id=run_id,
            )
        )

    assert _cells(capsys, "1-held")[0] == shown_as("1-held")
    assert status_shown(capsys, "1-held") == "waiting"
    assert row_of(listed(capsys), "1-held").startswith("└ ")


def test_cancelling_a_parent_prints_an_untold_childs_working_tree_as_left_to_remove(
    home, repo, capsys
):
    """Which Children are reached is held in tests/test_queue_store.py; here,
    that the command hands the operator their working trees."""
    worktree = joining_parent(home, repo, child_finished=False)
    capsys.readouterr()

    assert main(["queue", "rm", "parent"]) == 0

    printed = capsys.readouterr().out
    assert f"left for you to remove: {worktree}" in printed


def test_a_working_tree_left_to_remove_is_styled_as_a_path_at_a_terminal(
    home, repo, monkeypatch
):
    worktree = joining_parent(home, repo, child_finished=False)
    terminal = to_terminal(monkeypatch)

    assert main(["queue", "rm", "parent"]) == 0

    (line,) = [
        line for line in terminal.getvalue().splitlines() if "left for you to remove" in line
    ]
    assert ESCAPE in line
    assert words_of(line) == f"child working tree left for you to remove: {worktree}"
