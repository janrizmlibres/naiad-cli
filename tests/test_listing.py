"""What a Workflow declares, as an agent reads it to choose a start State.

The listing exists for one job: the operator says "spec this out", and the
agent has to turn that into a State name the Workflow actually declares. So
what is asserted here is what the agent must be able to read off a line —
the name, the slash command that name hides behind, and whether landing on
that State would park the Run or end it (ADR 0032).

Column positions are not asserted. They are alignment, and alignment is prose.
"""

from naiad.domain.listing import render_states
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
    assert "branches: grill, diagnose" in line_for("classify")
