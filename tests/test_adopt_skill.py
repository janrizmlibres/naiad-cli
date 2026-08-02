"""The skill document that teaches the adopt contract.

Asserted on what an agent must be able to read out of it — the intents that
trigger it, the command it must run, and each step of the contract it cannot
work out for itself — rather than on exact wording, which is prose and will be
tuned. The document is plain text, so the rules about it are tested here rather
than by inspecting an installed copy (tests/test_skill_install.py).
"""

import pytest

from naiad.skills.adopt import SKILL_NAME, installed_by_naiad, render_adopt_skill

COMMAND = "/opt/naiad/bin/naiad"


@pytest.fixture
def skill():
    return render_adopt_skill(naiad=COMMAND)


def frontmatter(document):
    """The YAML block Claude Code reads to decide whether the skill applies."""
    opening, block, _ = document.split("---\n", 2)
    assert opening == ""
    return block


def test_it_carries_the_name_the_skill_is_installed_under(skill):
    assert f"name: {SKILL_NAME}" in frontmatter(skill)


def test_its_description_triggers_on_the_intents_that_ask_for_an_adoption(skill):
    """The description is the whole of what Claude Code matches on, so an
    intent absent from it is one the operator states and nothing happens."""
    description = frontmatter(skill).lower()

    assert "description:" in description
    assert "start to-spec" in description
    assert "take over" in description


def test_it_names_the_command_that_adopts_the_session(skill):
    assert f"{COMMAND} adopt" in skill


def test_it_says_the_workflow_and_the_start_state_are_named(skill):
    """Both are the operator's to say and neither has a default worth
    guessing: a Workflow started at its first State re-runs the phases the
    operator already did by hand."""
    assert "--at" in skill
    assert "workflow" in skill.lower()


def test_it_says_the_task_is_distilled_from_the_conversation(skill):
    """The agent is the one party holding that conversation, and `--task` is
    required (ADR 0028)."""
    assert "--task" in skill
    assert "conversation" in skill.lower()


def test_it_carries_both_halves_of_settling_the_working_branch(skill):
    """A branch the human made is passed and never second-guessed; absent one,
    the agent derives, creates and declares it (ADR 0022) — and an agent told
    only 'settle the branch' has to guess which case it stands in."""
    assert "--branch" in skill
    assert f"{COMMAND} branch" in skill


def test_it_says_the_commands_output_is_relayed_to_the_operator(skill):
    """The warning that nothing is supervising reaches the human only through
    the agent, and an unrelayed one leaves the Entry queued forever."""
    lowered = skill.lower()

    assert "relay" in lowered or "tell the human" in lowered
    assert "supervisor" in lowered


def test_it_says_the_turn_ends_there(skill):
    """Nothing arrives while the turn is still running, so an agent that
    carries on after adopting is working against the Prompt about to land."""
    assert "end your turn" in skill.lower()


def test_it_names_the_naiad_that_installed_it(skill):
    """A session's PATH is whatever the human's shell held, so the command the
    agent is told to type is the absolute path of the naiad that wrote it."""
    assert "\nnaiad adopt" not in skill
    assert COMMAND in skill


def test_a_document_it_rendered_is_recognised_as_its_own(skill):
    assert installed_by_naiad(skill)


def test_a_document_naiad_did_not_write_is_not_recognised_as_its_own():
    """What tells an operator's own skill of the same name from a copy Naiad
    may replace."""
    assert not installed_by_naiad("---\nname: naiad-adopt\n---\n\nmy own notes\n")
