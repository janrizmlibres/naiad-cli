"""What a Workflow declares, as an agent reads it to choose a start State.

The listing exists for one job: the operator says "spec this out", and the
agent has to turn that into a State name the Workflow actually declares. So
what is asserted here is what the agent must be able to read off a line —
the name, the slash command that name hides behind, and whether landing on
that State would park the Run or end it (ADR 0032).

Column positions are not asserted. They are alignment, and alignment is prose.
"""

from naiad.domain.listing import render_states, render_workflow
from naiad.domain.workflow import parse_workflow

WORKFLOW = """
name = "matt-pocock"

[[states]]
name = "classify"
next = ["grill", "diagnose"]
prompt = "Decide what kind of work the following task is."

[[states]]
name = "diagnose"
prompt = "/diagnosing-bugs {task}"

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


def listing():
    return render_states(parse_workflow(WORKFLOW))


def line_for(name):
    """The one line naming this State, found the way an agent finds it."""
    for line in listing().splitlines():
        if line.split()[:1] == [name]:
            return line
    raise AssertionError(f"no line names the state '{name}'")


def test_it_opens_with_the_workflows_name():
    """A listing of the whole library runs several of these together, so a
    block that did not say which Workflow it described would be unreadable."""
    assert listing().splitlines()[0] == "matt-pocock"


def test_it_names_every_state_in_declared_order():
    """Declared order is the order the Run takes them in, and the State to
    start at is chosen by where the human stopped along it."""
    named = [line.split()[0] for line in listing().splitlines()[1:]]
    assert named == ["classify", "diagnose", "grill", "review", "spec", "done"]


def test_a_state_carries_the_slash_command_its_prompt_opens_with():
    """The whole reason the listing exists: the operator says "to-spec" for a
    State called `spec`, and only this column joins the two (ADR 0032)."""
    assert "/to-spec" in line_for("spec")


def test_a_prompt_opening_with_prose_carries_no_command():
    """Not every State runs a skill. A State whose Prompt opens with prose has
    no command to show, and showing the first word of the prose would read as
    one."""
    assert "/" not in line_for("classify")


def test_a_state_with_no_prompt_is_marked_a_gate():
    """A Gate State parks the Run the moment it starts, so an agent that
    landed a loose word there would hand the human a Run and no reason."""
    assert "gate" in line_for("review")


def test_the_terminal_state_is_marked_terminal_and_never_a_gate():
    """A Terminal State with no Prompt ends the Run rather than holding it for
    a human, so the two marks are not interchangeable."""
    line = line_for("done")

    assert "terminal" in line
    assert "gate" not in line


def test_a_branching_state_names_the_states_it_may_go_to():
    """A Branching State's candidates are what the agent may announce next, so
    they say what starting there commits the Run to."""
    assert "→ grill, diagnose" in line_for("classify")


def test_the_kind_says_what_naiad_does_on_entry():
    """One word per State, ahead of its marks: a Prompt is delivered, a Gate
    hands the Run to a human, a Terminal State ends it."""
    kinds = {name: line_for(name).split()[1] for name in ("classify", "review", "done")}

    assert kinds == {"classify": "prompt", "review": "gate", "done": "terminal"}


MARKED = """
name = "marked"
model = "opus"

[answerer]
fallback = "sonnet"

[[states]]
name = "plan"
clear = true
report = true
effort = "high"
questions = "human"
next = ["build"]
prompt = "Plan {task}."

[[states]]
name = "build"
prompt = "Build it."

[[states]]
name = "done"
terminal = true
"""


def marked_line(name):
    for line in render_states(parse_workflow(MARKED)).splitlines():
        if line.split()[:1] == [name]:
            return line
    raise AssertionError(name)


def test_a_state_shows_the_marks_it_carries():
    line = marked_line("plan")

    for mark in ("→ build", "clears", "report", "questions: human", "model: opus", "effort: high"):
        assert mark in line


def test_questions_show_whose_they_are_resolved_against_the_files_default():
    """`build` wrote no key, and the file declares an [answerer], so the
    Answerer takes its Questions: the mark says so rather than staying silent."""
    assert "questions: answerer" in marked_line("build")


def test_a_state_carrying_nothing_shows_no_marks_it_does_not_carry():
    line = marked_line("build")

    assert "clears" not in line and "report" not in line and "→" not in line
    assert "effort" not in line


def test_a_terminal_state_asks_no_questions():
    assert "questions" not in marked_line("done")


def test_a_state_that_delivers_no_prompt_shows_no_model():
    """The file's model resolves into every State, but a Terminal State runs
    nothing and a Gate State types nothing, so it is not theirs to show."""
    assert "model" not in marked_line("done")


def test_the_file_level_keys_stand_above_the_states():
    shown = render_workflow(parse_workflow(MARKED)).splitlines()

    assert shown[0].split() == ["name", "marked"]
    assert ["model", "opus"] in [line.split() for line in shown[:4]]
    assert ["answerer.fallback", "sonnet"] in [line.split() for line in shown[:4]]
    assert shown.index("") < [line.split()[:1] for line in shown].index(["plan"])


def test_workflow_show_and_states_render_the_states_identically():
    """One renderer behind both readers, so a mark cannot mean one thing to the
    operator and another to the adopting agent."""
    workflow = parse_workflow(MARKED)

    listed = render_states(workflow).splitlines()[1:]
    shown = render_workflow(workflow).splitlines()

    assert shown[-len(listed):] == listed


def test_a_compaction_point_is_shown_so_an_adoption_can_relay_it():
    """An Adoption types nothing into the human's Session, so the point the
    Workflow wants is told to the human instead — and the listing is what the
    adopt skill reads (ADR 0047)."""
    shown = render_states(parse_workflow(WORKFLOW.replace('name = "matt-pocock"', 'name = "matt-pocock"\nautocompact = "200k"')))

    assert "autocompact" in shown.splitlines()[0]
    assert "200k" in shown.splitlines()[0]


def test_a_workflow_with_no_compaction_point_shows_none():
    assert "autocompact" not in listing()
