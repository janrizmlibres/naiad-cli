"""The command the SessionStart hook runs, as a real subprocess.

This is the contract the agent meets in every fresh context, and its failures
are the silent ones: a Protocol that does not print leaves the agent unable to
participate, after which the Run dies quietly.
"""

import json
import subprocess

import pytest

from naiad.domain.answerer import Escalated
from naiad.domain.question import Question
from naiad.runtime.announcements import Announcements
from naiad.runtime.log import RunLog
from naiad.runtime.records import Clears, Consultations, Handled
from naiad.runtime.run import RunStore
from naiad_command import NAIAD, naiad_environment, requires_installed_naiad

pytestmark = requires_installed_naiad

WORKFLOW = """
name = "feature"

[[states]]
name = "grill"
prompt = "/grill-with-docs {task}"

[[states]]
name = "review"

[[states]]
name = "spec"
prompt = "/to-spec"

[[states]]
name = "done"
terminal = true
"""


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "naiad" / "runs")


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    (path / "workflow.toml").write_text(WORKFLOW)
    return path


def make_run(store, repo, **options):
    return store.create(
        run_id="a-run",
        workflow_path=repo / "workflow.toml",
        task="add dark mode",
        target_repo=repo,
        created_at="2026-07-19T12:00:00Z",
        **options,
    )


def protocol(run, *, run_id="a-run", source="startup"):
    """The SessionStart hook feeds the command its JSON on stdin, `source` among
    it (a documented field, ADR 0002). Passed here so the command is met with
    exactly the shape a real hook gives it, and so stdin is a pipe rather than
    the test runner's terminal."""
    return subprocess.run(
        [NAIAD, "protocol"],
        input=json.dumps({"hook_event_name": "SessionStart", "source": source}),
        capture_output=True,
        text=True,
        env=naiad_environment(run, run_id=run_id),
        cwd=str(run.target_repo),
    )


def injected(finished):
    """What the hook asks Claude Code to add to the fresh context."""
    document = json.loads(finished.stdout)
    assert document["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    return document["hookSpecificOutput"]["additionalContext"]


def test_prints_the_protocol_for_injection_into_a_fresh_context(store, repo):
    finished = protocol(make_run(store, repo))

    assert finished.returncode == 0, finished.stderr
    assert "naiad announce" in injected(finished)
    assert "naiad ask" in injected(finished)


def test_before_anything_is_announced_it_names_the_state_after_the_starting_one(store, repo):
    finished = protocol(make_run(store, repo))

    assert "announce: review" in injected(finished)


def test_after_an_announcement_it_names_the_state_after_the_announced_one(store, repo):
    run = make_run(store, repo)
    Announcements(run.root).announce("review")

    assert "announce: spec" in injected(protocol(run))


def test_a_run_with_gates_skipped_is_told_the_next_state_that_has_a_prompt(store, repo):
    finished = protocol(make_run(store, repo, skip_gates=True))

    assert "announce: spec" in injected(finished)


def test_a_run_started_at_a_named_state_is_told_what_follows_that_state(store, repo):
    finished = protocol(make_run(store, repo, start_state="review"))

    assert "announce: spec" in injected(finished)


def test_a_clear_source_records_that_the_clear_landed(store, repo):
    """The confirmation ADR 0019 turns on: a fresh context a /clear made says so
    through the hook's `source`, and the loop reads it as the Clear landing."""
    run = make_run(store, repo)

    finished = protocol(run, source="clear")

    assert finished.returncode == 0, finished.stderr
    assert Clears(run.root).count() == 1


def test_a_startup_source_records_no_clear(store, repo):
    """A fresh context at startup is not a Clear, so nothing is recorded — else
    every session's first context would read as a Clear that landed."""
    run = make_run(store, repo)

    protocol(run, source="startup")

    assert Clears(run.root).count() == 0


def test_a_compact_source_records_no_clear(store, repo):
    """A compaction fires the same hook, so it must be told from a Clear by the
    source — a running turn's auto-compaction is not this State's Clear."""
    run = make_run(store, repo)

    protocol(run, source="compact")

    assert Clears(run.root).count() == 0


def test_a_clear_source_still_injects_the_protocol(store, repo):
    """Recording the landing does not replace the hook's job: the fresh context
    a Clear made still needs the Protocol, like any other."""
    finished = protocol(make_run(store, repo), source="clear")

    assert "naiad announce" in injected(finished)


def test_no_run_attached_prints_nothing_and_succeeds(store, repo):
    """Hooks are installed independently of any Run, so a session that is not
    being driven must be left exactly as it was — not failed, not written to."""
    finished = protocol(make_run(store, repo), run_id="")

    assert finished.returncode == 0
    assert finished.stdout == ""


def test_a_workflow_carrying_no_protocol_text_still_yields_the_full_protocol(store, repo):
    """The Protocol is Naiad's responsibility and never the Workflow author's.
    The fixture Workflow's Prompts are bare — were an author obliged to paste
    the contract into each one, a single omission would produce a State that
    silently never advances."""
    assert "naiad" not in WORKFLOW

    finished = protocol(make_run(store, repo))

    assert "naiad announce" in injected(finished)
    assert "naiad ask" in injected(finished)
    assert "announce: review" in injected(finished)


def test_a_workflow_edited_out_from_under_the_run_does_not_break_the_session(store, repo):
    """A hook that raises interrupts the agent for a Run it cannot even
    describe; printing the contract without an expectation is the lesser harm."""
    run = make_run(store, repo, start_state="review")
    (repo / "workflow.toml").write_text(
        'name = "feature"\n[[states]]\nname = "other"\nterminal = true\n'
    )

    finished = protocol(run)

    assert finished.returncode == 0
    assert "naiad announce" in injected(finished)


def test_a_compact_source_records_that_the_context_was_summarised(store, repo):
    """The diagnostic ADR 0047 keeps: how many times, and in which State, the
    Session summarised itself is read from the Run log and nowhere else."""
    run = make_run(store, repo)
    Announcements(run.root).announce("review")

    finished = protocol(run, source="compact")

    assert finished.returncode == 0, finished.stderr
    assert [(e.kind, e.state) for e in RunLog(run.root).entries()] == [("compacted", "review")]


def test_a_startup_source_records_no_compaction(store, repo):
    run = make_run(store, repo)

    protocol(run, source="startup")

    assert RunLog(run.root).entries() == []


def test_a_compact_source_reminds_the_agent_of_its_state_and_subject(store, repo):
    run = make_run(store, repo)
    Announcements(run.root).announce("spec", subject="docs/spec.md")

    told = injected(protocol(run, source="compact"))

    assert "naiad announce" in told
    assert "spec" in told
    assert "docs/spec.md" in told


def test_a_compact_source_before_any_announcement_names_the_state_the_run_began_at(store, repo):
    told = injected(protocol(make_run(store, repo, start_state="spec"), source="compact"))

    assert "spec" in told


def test_a_compact_source_repeats_a_question_still_unanswered(store, repo):
    run = make_run(store, repo)
    Announcements(run.root).ask(Question(text="Which module owns retries?", options=()), state="grill")

    told = injected(protocol(run, source="compact"))

    assert "Which module owns retries?" in told


def test_a_compact_source_does_not_repeat_a_question_already_answered(store, repo):
    run = make_run(store, repo)
    asked = Announcements(run.root).ask(Question(text="Which module owns retries?", options=()), state="grill")
    Handled(run.root).record(asked.seq)

    told = injected(protocol(run, source="compact"))

    assert "Which module owns retries?" not in told


def test_a_startup_source_carries_no_reminder(store, repo):
    run = make_run(store, repo)
    Announcements(run.root).announce("spec", subject="docs/spec.md")

    assert "docs/spec.md" not in injected(protocol(run, source="startup"))


def test_a_compact_source_does_not_repeat_a_question_handed_to_a_human(store, repo):
    """An escalated Question is the human's to answer in the Session, and
    is no longer pending — the same rule `naiad ask` applies (ADR 0044)."""
    run = make_run(store, repo)
    asked = Announcements(run.root).ask(Question(text="Which module owns retries?", options=()), state="grill")
    Consultations(run.root).record(asked, Escalated(reason="needs a credential"))

    told = injected(protocol(run, source="compact"))

    assert "Which module owns retries?" not in told


def test_a_compact_source_after_an_announcement_survives_a_workflow_that_no_longer_parses(store, repo):
    """The State the agent stands in is its own Announcement's, which needs no
    Workflow to read; only a Run that announced nothing has to consult one."""
    run = make_run(store, repo)
    Announcements(run.root).announce("spec", subject="docs/spec.md")
    (repo / "workflow.toml").write_text("not = [toml")

    told = injected(protocol(run, source="compact"))

    assert "docs/spec.md" in told
    assert [(e.kind, e.state) for e in RunLog(run.root).entries()] == [("compacted", "spec")]
