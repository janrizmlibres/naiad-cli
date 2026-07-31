"""The one Workflow that ships: a classifying State, the bug branch and the
Matt Pocock feature chain, rejoining at the pull request.

Asserted as an operator and an agent meet it — the file on disk parses, its
Prompts read as delivered rather than as templates, and a Run starts from it.
How the Workflow behaves under a real agent is manual smoke, in
docs/smoke/matt-pocock.md; what is testable here is that the file is well-formed
and says what the Workflow requires.
"""

from pathlib import Path

import pytest

from naiad.cli.kickoff import start_run
from naiad.cli.refusals import MissingSubject
from naiad.domain.prompt import render_prompt
from naiad.domain.transitions import deviation, next_states
from naiad.domain.workflow import load_workflow
from naiad.runtime.run import RunStore

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / "workflows" / "matt-pocock.toml"

# Declared order: the classifying State, then the short branch, then the feature
# chain, then the tail they share. No Run walks this order end to end — it is
# the order the file reads in, and the order an implicit successor comes from.
STATES = [
    "classify",
    "diagnose",
    "no-repro",
    "grill",
    "review",
    "spec",
    "tickets",
    "implement",
    "handover",
    "pull-request",
    "review-fix",
    "done",
]

# Every State whose Prompt runs a skill of its own, and the skill it must
# invoke. Two States are deliberately absent: the classifying State runs none,
# and the pull-request State opens a pull request generically — naming /hcgps-pr
# only for the HCGPS monorepo, mid-Prompt rather than at the start (ADR 0016).
# So neither opens with a slash command.
SKILLS = {
    "diagnose": "/diagnosing-bugs",
    "grill": "/grill-with-docs",
    "spec": "/to-spec",
    "tickets": "/to-tickets",
    "implement": "/implement",
    "review-fix": "/fix-review",
}

# The States that declare candidates rather than inheriting the next State in
# the declared order, and what each may announce. Every other successor in the
# Workflow stays implicit.
CANDIDATES = {
    "classify": ("grill", "diagnose"),
    "diagnose": ("no-repro", "pull-request"),
    "no-repro": ("pull-request",),
    "tickets": ("implement", "handover"),
    "implement": ("implement", "handover", "pull-request"),
    "handover": ("implement", "pull-request"),
    "pull-request": ("review-fix", "done"),
}

# The feature chain as it stands today, asserted rather than assumed. `done`
# ends the Run and so has nothing after it.
#
# Two edges have moved since this table was first written, both deliberately.
# `implement` gained a third exit for a ticket it must decline (ADR 0010).
# `pull-request` gained `done` beside `review-fix`, so a Run whose host runs no
# automated review ends rather than passing through an empty fix (ADR 0017).
# Everything else is untouched, which is what this table is for.
FEATURE_CHAIN = {
    "grill": ("review",),
    "review": ("spec",),
    "spec": ("tickets",),
    "tickets": ("implement", "handover"),
    "implement": ("implement", "handover", "pull-request"),
    "handover": ("implement", "pull-request"),
    "pull-request": ("review-fix", "done"),
    "review-fix": ("done",),
    "done": (),
}

# The triage label a ticket must carry for the loop to implement it unattended,
# and the one meaning a person must. Named from docs/agents/triage-labels.md,
# which is where this repository maps the canonical roles to its own strings.
IMPLEMENTABLE = "ready-for-agent"
NEEDS_A_HUMAN = "ready-for-human"

# A Subject as the implement loop's Prompt actually receives one: a path to a
# ticket file under the local markdown tracker (docs/agents/issue-tracker.md).
SUBJECT = ".scratch/dark-mode/issues/04-toggle.md"

# The two States a Run may be started at directly, each the head of a branch —
# the escape hatch for an operator who already knows which kind of work they
# have and would rather not have it classified.
BRANCH_HEADS = ["diagnose", "grill"]

# Every State that delivers a Prompt at all: the skill-running ones, the
# classifier, and the pull-request State. The last two run no skill of their
# own, so their Prompts open with prose rather than a slash command.
DELIVERING = ["classify", "pull-request", *sorted(SKILLS)]

# The States told what the work stands on: the two heads, which decide what to
# base a new branch on, and the pull request, which asks the same question again
# because the Predecessor may have landed while the Run was working.
STANDING_ON_THE_PREDECESSOR = [*BRANCH_HEADS, "pull-request"]

# The States told the task in words. The classifier is told it because it has
# nothing else to read; the two branch heads because they Clear, and what the
# classifier made of the task is exactly what must not survive that Clear.
TOLD_THE_TASK = ["classify", *BRANCH_HEADS]

TASK = "add dark mode"
BRANCH = "MC-AGENT-8546"

# What the Entry before this one left behind, as a Run is handed it: an opaque
# branch name Naiad neither reads nor asks git about (ADR 0015). Distinct from
# BRANCH and not a substring of it, so an assertion about one cannot pass on the
# other.
PREDECESSOR = "MC-AGENT-8500"

# The one command the branch rule is allowed to be, written with its operands in
# the order that answers the question asked. One question with a terminal
# answer, needing no API and working offline; merge status is a taxonomy, and it
# answers wrongly for a Predecessor parked at `handover` — commits, and no pull
# request at all.
#
# The operands are part of the constant rather than left to prose. Reversed, the
# command answers every case backwards while still reading correctly, and the
# symptom is a wrong stack noticed at review time rather than a Run that fails.
ANCESTRY_TEST = "git merge-base --is-ancestor <predecessor> <base branch>"


@pytest.fixture
def workflow():
    return load_workflow(WORKFLOW_PATH)


def sentences(prompt):
    """A Prompt's sentences, so that a claim can be pinned to the case it
    belongs to.

    The branch rule names two outcomes and attaches an opposite instruction to
    each, so a whole-Prompt assertion passes just as well with the two swapped —
    which is the one way this rule can be wrong while reading correctly, and the
    way whose symptom is a wrong stack at review time rather than a Run that
    fails. The classifying State's criterion is asserted the same way and for
    the same reason.
    """
    return [part.strip() for part in prompt.replace("\n", " ").split(".") if part.strip()]


def only_sentence(prompt, phrase):
    """The one sentence carrying a phrase. Exactly one, because two sentences
    describing the same outcome are two places for the rule to disagree with
    itself."""
    matching = [sentence for sentence in sentences(prompt) if phrase in sentence]

    assert len(matching) == 1, f"expected one sentence containing {phrase!r}, found {matching}"
    return matching[0]


def delivered(workflow, state_name, subject=SUBJECT, predecessor=PREDECESSOR):
    """A State's Prompt as the agent actually reads it, with the successor the
    Workflow resolves interpolated — which is what Naiad sends (naiad.runtime.loop).

    A Subject is supplied to every State, not only the one that names it: a
    Prompt with no slot for one is unaffected, and passing it everywhere means
    no assertion here silently depends on which States use it. The Working
    branch and the Predecessor are supplied everywhere for the same reason, and
    because Naiad genuinely does interpolate them into every Prompt a Run
    delivers rather than only its first."""
    return render_prompt(
        workflow.state(state_name).prompt,
        task=TASK,
        next_states=next_states(workflow, state_name),
        subject=subject,
        branch=BRANCH,
        predecessor=predecessor,
    )


def test_declares_every_state_in_order(workflow):
    assert [state.name for state in workflow.states] == STATES


def test_the_workflow_has_exactly_three_gate_states(workflow):
    """Two kinds of stop, not three: `review` is a routine checkpoint in the
    declared order, while `no-repro` and `handover` are destinations the agent
    chose — work it has correctly declined. Which is which is asserted below,
    under gate-skipping.

    `handover` is the second of the chosen kind (ADR 0010), which is why the
    rule ADR 0007 wrote for the first one now carries a case it did not
    anticipate rather than an exception."""
    gate_states = [
        state.name for state in workflow.states if state.is_gate_state and not state.terminal
    ]

    assert gate_states == ["no-repro", "review", "handover"]


def test_the_no_reproduction_state_delivers_nothing(workflow):
    """No Prompt, so Naiad sends nothing and the operator types into the
    session (ADR 0008)."""
    assert workflow.state("no-repro").prompt is None


def test_the_last_state_is_the_only_terminal_one(workflow):
    terminal = [state.name for state in workflow.states if state.terminal]

    assert terminal == ["done"]


@pytest.mark.parametrize(("state_name", "skill"), sorted(SKILLS.items()))
def test_each_prompt_opens_by_invoking_its_skill(workflow, state_name, skill):
    """The slash command opens the Prompt because Claude Code reads one only at
    the start of a message: prose in front of it would send the skill's name as
    chat rather than invoking it."""
    assert delivered(workflow, state_name).startswith(skill)


@pytest.mark.parametrize("state_name", DELIVERING)
def test_each_prompt_names_the_state_to_announce_next(workflow, state_name):
    """The Workflow file owns the ordering, so a Prompt names its successors by
    interpolation rather than by hand — and the agent is told names it can
    announce rather than an unsubstituted placeholder.

    Every successor, at a fork too: a Prompt naming one exit of two would decide
    the branch in the place that is least visible, and the whole point of the
    fork is that the choice is the agent's."""
    prompt = delivered(workflow, state_name)

    for successor in next_states(workflow, state_name):
        assert f"announce {successor}" in prompt


@pytest.mark.parametrize(("state_name", "candidates"), sorted(CANDIDATES.items()))
def test_each_state_that_declares_candidates_declares_the_right_ones(
    workflow, state_name, candidates
):
    """Two of these three branch: `no-repro` declares a single candidate, and
    declares it because its implicit successor would be the feature chain it
    must not fall into. The rejoin is declared from the short branch, so it sits
    a line from its own head rather than reaching across the file."""
    assert workflow.state(state_name).next_candidates == candidates


def test_no_state_outside_that_table_declares_candidates(workflow):
    """Every other successor stays implicit, supplied by the declared order —
    which is what leaves the existing feature chain untouched."""
    declared = {state.name for state in workflow.states if state.next_candidates}

    assert declared == set(CANDIDATES)


@pytest.mark.parametrize(("state_name", "successors"), sorted(FEATURE_CHAIN.items()))
def test_the_feature_chain_keeps_every_successor_it_has_today(workflow, state_name, successors):
    """Adding a branch must not move a single edge of the path that already
    works, so each one is asserted rather than assumed."""
    assert next_states(workflow, state_name) == successors


def test_only_the_classifier_and_the_branch_heads_are_told_the_task(workflow):
    """Every later State reads the work from the Artifacts the earlier ones
    wrote, which is what makes Clearing safe. Both branch heads Clear, so both
    restate the task; Naiad holds it and interpolates it into every Prompt
    rather than only the first, which is what makes the fork safe by
    construction rather than by luck."""
    told = [name for name in DELIVERING if TASK in delivered(workflow, name)]

    assert sorted(told) == sorted(TOLD_THE_TASK)


def test_the_branch_heads_and_the_implement_loop_clear_and_the_design_phases_do_not(workflow):
    """Each ticket starts fresh; the spec and the tickets are synthesised from
    the grilling conversation and would lose it.

    Both branch heads Clear, which is what keeps the classifying State's
    reading of the task from reaching either of them — most of all the
    diagnosing State, whose job is to form a hypothesis from evidence rather
    than to inherit a guess."""
    clearing = [state.name for state in workflow.states if state.clear]

    assert clearing == ["diagnose", "grill", "implement", "pull-request", "review-fix"]


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_each_branch_head_clears_and_so_restates_the_task(workflow, head):
    """The Clear is why the task has to be restated, and Naiad interpolating it
    into every delivered Prompt rather than only the first is why that costs
    nothing: the one thing that must cross the fork is the only thing Naiad
    holds itself."""
    assert workflow.state(head).clear
    assert TASK in delivered(workflow, head)


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_each_branch_head_puts_the_run_on_its_working_branch(workflow, head):
    """The branch is prepared at the two heads rather than in a State of its
    own, because a State of its own would be skipped by exactly the Entries
    that pre-classify — a design Run starts at `grill` and a bug Run at
    `diagnose`, and both would step straight over it (ADR 0015).

    Named rather than described: Naiad holds the Working branch and
    interpolates it, so a Prompt saying 'your branch' would be telling an agent
    to find out something it has already been told. What to do with it once it
    exists and what to base it on when it does not are asserted below, each
    against its own case.

    Before anything is written, because the Prompt cannot be reordered: the
    slash command has to open the message or Claude Code reads it as chat, so
    the instruction that comes first in time is written second."""
    prompt = delivered(workflow, head)

    assert "{branch}" not in prompt
    assert BRANCH in prompt
    assert "Before you change anything" in prompt


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_each_branch_head_is_safe_to_repeat(workflow, head):
    """A resumed or re-entered Run finds the branch already there, which is
    ordinary rather than an error: a bare `git checkout -b` would fail the Run
    on its second entrance to the same State."""
    prompt = delivered(workflow, head)

    assert "check it out" in only_sentence(prompt, "already exists")


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_each_branch_head_chooses_the_base_before_it_creates_the_branch(workflow, head):
    """The working tree is shared, so whatever is checked out when a Run arrives
    is where the last Run left it. A branch created first and reasoned about
    afterwards is a branch cut from another Run's work — which looks like
    obedience and reads as a wrong stack days later, so the Prompt gives the
    command with its base as an operand."""
    prompt = delivered(workflow, head)

    assert f"git checkout -b {BRANCH} <the branch you chose>" in prompt
    assert "choose what to base it on before you create it" in prompt


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_each_branch_head_stands_on_a_predecessor_that_has_not_landed(workflow, head):
    """The Predecessor is what the Entry before this one left behind, and the
    default is to stand on it: not stacking when the work depends means this
    agent never sees the previous one's code, and the conflict surfaces at merge
    after the night is spent.

    Pinned to the sentence describing the failing test rather than to the whole
    Prompt, so that swapping the two outcomes fails here — a Prompt naming both
    passes the loose form with the rule inverted."""
    prompt = delivered(workflow, head)

    assert "{predecessor}" not in prompt
    assert PREDECESSOR in prompt
    assert ANCESTRY_TEST in prompt
    assert "base the new branch on the Predecessor" in only_sentence(prompt, "a non-zero exit")


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_each_branch_head_falls_back_to_the_base_branch_once_the_work_has_landed(workflow, head):
    """The other half of the rule, asserted against its own sentence for the
    reason the first half is: a Predecessor already merged into the base branch
    is work this Run does not stand on, and branching from it would stack on
    nothing."""
    prompt = delivered(workflow, head)

    assert "base the new branch on the base branch" in only_sentence(prompt, "A zero exit")


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_each_branch_head_settles_an_absent_predecessor_before_running_any_git(workflow, head):
    """The first Entry for a repository has no Predecessor, which is ordinary
    and renders as nothing rather than as a name. An agent reading in order must
    meet that case before the command, or it runs the ancestry test with an
    empty operand — which fails, and reads as 'not an ancestor', which is the
    answer that stacks this Run on a branch that does not exist."""
    prompt = delivered(workflow, head, predecessor=None)

    assert "Predecessor:" in prompt
    assert prompt.index("When no Predecessor is named above") < prompt.index(ANCESTRY_TEST)


@pytest.mark.parametrize("state_name", STANDING_ON_THE_PREDECESSOR)
def test_no_state_that_decides_a_base_asks_whether_the_predecessor_was_merged(
    workflow, state_name
):
    """Ancestry, not merge status (ADR 0015). Merge status is a taxonomy —
    open, closed, merged, closed-unmerged — that has to be enumerated correctly
    to be safe, and it answers wrongly for the case that matters most: a Run
    parked at `handover` has commits and no pull request at all, so 'not
    merged' would send this Run to the base branch and drop that work from
    underneath it."""
    assert "merged" not in delivered(workflow, state_name)


def test_only_the_branch_heads_prepare_the_working_branch(workflow):
    """The classifying State is unchanged: it writes nothing, so it needs no
    Working branch, and every State after a head inherits the checkout, which is
    git state and survives the Clear both heads perform.

    A State of its own would be skipped by exactly the Entries that
    pre-classify, which are most of them (ADR 0015) — so the two heads are the
    whole of it, and this is what says so."""
    naming = [name for name in DELIVERING if BRANCH in delivered(workflow, name)]

    assert sorted(naming) == sorted(BRANCH_HEADS)


def test_only_the_states_that_decide_a_base_are_told_the_predecessor(workflow):
    """Twice at the start and once at the end: the head chooses what to branch
    from, and the pull request chooses what to open against. Nothing in between
    has a use for it, and a Prompt carrying it anyway would read as though it
    had a decision to make."""
    naming = [name for name in DELIVERING if PREDECESSOR in delivered(workflow, name)]

    assert sorted(naming) == sorted(STANDING_ON_THE_PREDECESSOR)


def test_every_state_that_delivers_a_prompt_is_accounted_for(workflow):
    """The two tables above split the delivering States between those that run
    a skill and the one that does not, so a State added to the file without
    being added to a table would otherwise be asserted by nothing."""
    delivering = [state.name for state in workflow.states if state.prompt is not None]

    assert sorted(delivering) == sorted(DELIVERING)


def test_only_the_states_that_run_a_skill_open_with_a_slash_command(workflow):
    """The convention's reason is mechanical — a slash command is read only at
    the start of a message — not a requirement that every State run one. The
    classifying and pull-request States run no skill of their own, so their
    Prompts open with prose, and the file's comments say so rather than
    asserting the convention universally."""
    opening = [name for name in DELIVERING if delivered(workflow, name).startswith("/")]

    assert sorted(opening) == sorted(SKILLS)


def test_the_classifying_state_is_where_a_run_begins(workflow):
    """First in the declared order, so an operator who names no start State is
    classified rather than dropped into whichever branch happens to be first.
    Which candidates it declares is asserted from the table above."""
    assert workflow.states[0].name == "classify"


def test_the_classifying_state_neither_clears_nor_writes_anything(workflow):
    """Nothing precedes it, so there is no context to Clear; and its
    Announcement is the record the Run log already holds, which is all an
    Artifact could have carried to branch heads that Clear anyway.

    Naiad has no notion of an Artifact, so the only thing assertable about not
    writing one is that the Prompt asks for no work beyond the judgment."""
    assert not workflow.state("classify").clear

    prompt = delivered(workflow, "classify")
    assert "artifact" not in prompt.lower()
    assert "Do no other work." in prompt


@pytest.mark.parametrize(
    ("kind", "head"),
    [("feature", "grill"), ("bug", "diagnose")],
)
def test_the_classifying_state_attaches_its_criterion_to_the_right_branch(workflow, kind, head):
    """Naiad decides nothing about which branch a task belongs to, and no skill
    runs here, so if the criterion is not in the Prompt it is nowhere.

    Asserted per branch and within one sentence rather than as two words
    somewhere in the Prompt: a Prompt naming both kinds and both heads passes
    the loose form even with the two swapped, which is the one way this Prompt
    can be wrong while looking right."""
    prompt = delivered(workflow, "classify")

    sentences = [sentence for sentence in prompt.split(".") if f"announce {head}" in sentence]

    assert any(kind in sentence for sentence in sentences)


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_announcing_either_branch_head_from_the_classifier_is_not_a_deviation(workflow, head):
    """Both are declared candidates, so choosing correctly at the fork is not
    recorded as having left the path — whichever way the choice goes.

    The off-path case is asserted alongside it because an empty expectation is
    also reported as no Deviation: without it this passes just as well against
    a Workflow that has never heard of the classifying State."""
    assert deviation(workflow, announced=head, previous_state="classify") == ()
    assert deviation(workflow, announced="done", previous_state="classify") == CANDIDATES["classify"]


def test_the_diagnosing_state_runs_the_whole_discipline_in_one_state(workflow):
    """One State, all six phases, fix and post-mortem included. There is no
    fixing State to announce and no diagnosis Artifact to write: the only
    honest cut is mid-discipline, and the review it would enable is not wanted
    on the path where the hypothesis is confirmed (ADR 0008)."""
    assert [state.name for state in workflow.states if "fix" in state.name] == ["review-fix"]
    assert "end to end" in delivered(workflow, "diagnose")


def test_the_diagnosing_state_states_the_criterion_for_choosing_its_exit(workflow):
    """The Workflow supplies the candidate names; the Prompt supplies when each
    applies. Naiad decides nothing about which branch is right, so if the
    criterion is not in the Prompt it is nowhere."""
    prompt = delivered(workflow, "diagnose")

    assert "no-repro" in prompt
    assert "feedback loop" in prompt


@pytest.mark.parametrize(
    ("head", "before"),
    [("diagnose", "before you form a hypothesis"), ("grill", "before the interview")],
)
def test_each_branch_head_reads_a_referenced_image_first(workflow, head, before):
    """Both heads receive the raw task, and a bug report or a design brief often
    points at an image — a screenshot of the failure, a mockup to match. The
    agent meets an issue as markdown text with the image only as a URL, and
    Naiad reads no image itself (ADR 0002), so the instruction to fetch and Read
    it lives in the Prompt or nowhere. It is pinned here rather than in either
    skill for the reason the triage label and the seams are (ADR 0016): an input
    to the skill, asserted where the rest of the Workflow's behaviour is.

    Each head names its own moment — the read comes before the hypothesis on the
    bug branch and before the interview on the feature one — so the phrase is
    asserted per head rather than as the bare word somewhere in the Prompt."""
    image_sentence = only_sentence(delivered(workflow, head), "image")

    assert f"Read it {before}" in image_sentence


def test_the_diagnosing_state_restates_the_task_because_it_clears(workflow):
    assert workflow.state("diagnose").clear
    assert TASK in delivered(workflow, "diagnose")


def test_the_implement_loop_tells_the_agent_to_re_announce_itself(workflow):
    """One State, announced once per ticket. The interpolated successor is the
    State after the loop, so the loop's own name has to be in the Prompt or the
    agent has nothing to announce for the second ticket."""
    assert "announce implement" in delivered(workflow, "implement")


def test_the_implement_loop_declares_itself_among_its_candidates(workflow):
    """It does not have to — re-announcing the State the agent is standing in
    is exempt from Deviation, and that exemption is what makes the loop a loop.
    It is declared so the Protocol injected into every Cleared context renders
    it: a Protocol naming only the two exits omits the announcement this State
    makes more often than both of them together (ADR 0010)."""
    assert "implement" in workflow.state("implement").next_candidates


def test_the_implement_loop_is_given_its_ticket_rather_than_finding_one(workflow):
    """The Clear discards the context that chose the ticket, so the Prompt
    names it. Choosing happens in the context that has just seen the whole
    tracker rather than in the wiped one that has seen none of it (ADR 0009)."""
    prompt = delivered(workflow, "implement")

    assert SUBJECT in prompt
    assert "{subject}" not in prompt


def test_the_implement_loop_implements_only_agent_ready_tickets(workflow):
    """The failure this loop was rebuilt for: 'ready to start' was defined
    nowhere, so eight tickets marked for a human were met with no rule and the
    agent asked one directly, which the Protocol forbids (ADR 0010)."""
    assert IMPLEMENTABLE in delivered(workflow, "implement")


def test_the_implement_loop_sends_every_other_status_to_the_gate(workflow):
    """Not only `ready-for-human`. An unrecognised or missing status is routed
    the same way, because an unnecessary pause costs one operator interaction
    while implementing a `needs-info` ticket — one whose specification is known
    to be incomplete — costs a review cycle and a revert."""
    prompt = delivered(workflow, "implement")

    for status in (NEEDS_A_HUMAN, "needs-info", "needs-triage", "wontfix"):
        assert status in prompt
    assert "announce handover" in prompt


def test_the_implement_loop_reports_which_status_stopped_it(workflow):
    """Routing an unknown label and routing `ready-for-human` are the same
    action needing opposite responses — fix the label, or do the work. A gate
    that cannot tell the operator which it hit wastes their time every time."""
    prompt = delivered(workflow, "implement")

    sentences = [line for line in prompt.split("\n") if "handover" in line]

    assert any("status" in line for line in sentences)


def test_the_implement_loop_names_the_pull_request_rather_than_interpolating_it(workflow):
    """`{next_state}` renders every candidate as one joined phrase, which is
    wrong here twice over: the exhaustion line must name the pull request
    alone, and each exit carries a different condition. `diagnose` writes its
    successors out for the same reason."""
    prompt = delivered(workflow, "implement")

    exhausted = [line for line in prompt.split("\n") if "remain" in line or "no tickets" in line]

    assert any("pull-request" in line and "handover" not in line for line in exhausted)


def test_the_implement_loop_marks_the_finished_ticket_resolved(workflow):
    """Agents recorded completion unreliably — sometimes marking the ticket
    done, sometimes not — and the Status line is the only record the loop and a
    reader have. So the Prompt makes marking it resolved explicit and first,
    rather than left to the external skill to remember (ADR 0010, ADR 0016).
    `resolved` is issue-tracker.md's own completion status, reused here rather
    than a sixth triage role."""
    assert "set that ticket's Status line to resolved" in delivered(workflow, "implement")


def test_the_implement_loop_reads_only_unresolved_tickets_when_it_scans(workflow):
    """The scan routes every status other than ready-for-agent to handover, so a
    resolved ticket left in the frontier would park the loop on its own finished
    work. The frontier is the unresolved tickets alone, and a blocking edge is
    satisfied when the ticket it names is resolved — the meaning issue-tracker.md
    already gives `resolved`."""
    prompt = delivered(workflow, "implement")

    assert "lowest-numbered ticket that is not resolved" in prompt
    assert "no unresolved tickets remain" in prompt


def test_the_handover_gate_delivers_nothing(workflow):
    """No Prompt, so Naiad sends nothing and the operator types into the
    still-live session, exactly as at `no-repro` (ADR 0008, ADR 0010)."""
    assert workflow.state("handover").prompt is None


def test_the_handover_gate_returns_to_the_loop_or_ends_it(workflow):
    """After the human does the ticket, either tickets remain or they do not.
    Both are declared, because the implicit successor would be the pull request
    alone and a Run handing over its first ticket would never implement any."""
    assert workflow.state("handover").next_candidates == ("implement", "pull-request")


def test_an_unattended_run_still_parks_at_the_handover_gate(workflow):
    """A Gate State named as a branch candidate is never skipped: it is a
    destination the agent chose rather than a routine checkpoint on the path
    (ADR 0007). `ready-for-human` means the agent cannot proceed, not that a
    review is optional — so `--skip-gates` must not delete this exit."""
    assert "handover" in next_states(workflow, "implement", skip_gates=True)


def test_the_tickets_state_pins_the_triage_label_it_publishes(workflow):
    """/to-tickets applies `ready-for-agent` only on its real-issue-tracker
    branch; for local markdown it says nothing, so the label was improvised —
    three runs produced three vocabularies. The skill is external and not ours
    to edit, and it leaves the hook open itself: 'unless instructed otherwise'
    (ADR 0010). The loop's rules are worth nothing if the labels are noise."""
    prompt = delivered(workflow, "tickets")

    assert IMPLEMENTABLE in prompt
    assert NEEDS_A_HUMAN in prompt


def test_the_tickets_state_may_hand_over_without_the_loop_running_at_all(workflow):
    """A feature whose every ticket is genuinely a person's to implement is a
    real outcome, not a malformed one. Declared rather than left to Deviation,
    which is recorded as a symptom of a confused agent and would be logged as
    one on every legitimate use."""
    assert workflow.state("tickets").next_candidates == ("implement", "handover")


def test_the_tickets_state_names_the_first_ticket_when_it_starts_the_loop(workflow):
    """The loop's first iteration has no previous one to choose its ticket, so
    this State does — it has just published them all and is the only context
    that knows. Announcing `implement` bare is rejected (ADR 0009), and while
    the agent can recover from that, being told here costs nothing and a
    rejection mid-Run costs a turn."""
    prompt = delivered(workflow, "tickets")

    announcing = [line for line in prompt.split("\n") if "announce implement" in line]

    assert announcing
    assert all("subject" in line for line in announcing)


def test_the_pull_request_state_asks_the_ancestry_question_again(workflow):
    """The Predecessor may have landed during the Run — a stack of Entries is
    exactly the case where that happens — so what was true at the branch head
    is not trusted here. This State Clears as well, so it could not have
    inherited the answer even if it wanted to."""
    prompt = delivered(workflow, "pull-request")

    assert PREDECESSOR in prompt
    assert ANCESTRY_TEST in prompt


def test_the_pull_request_state_passes_the_answer_as_the_base(workflow):
    """An input to whatever opens the pull request rather than a copy of its
    logic: /hcgps-pr accepts an explicit base for stacked work, and a direct
    open through the GitHub MCP takes one too, so each needs telling and nothing
    more (ADR 0016).

    Each outcome is pinned to its own sentence, as the branch heads' are:
    inverted, this opens every stacked pull request against the base branch and
    every independent one against a branch it does not stand on."""
    prompt = delivered(workflow, "pull-request")

    assert "as the base" in only_sentence(prompt, "A non-zero exit")
    assert "say nothing about a base" in only_sentence(prompt, "A zero exit")


def test_the_pull_request_state_settles_an_absent_predecessor_before_running_any_git(workflow):
    """The commonest case at this State — a Run that stands on nothing — and the
    one an agent must meet before the command, for the reason it must at the
    branch heads."""
    prompt = delivered(workflow, "pull-request", predecessor=None)

    assert prompt.index("When no Predecessor is named above") < prompt.index(ANCESTRY_TEST)


def test_the_pull_request_state_waits_for_the_review_before_announcing(workflow):
    """The review-fix State has nothing to work from until the host's automated
    review has posted its findings, so the wait belongs before the Announcement
    rather than after it — announcing early delivers /fix-review an empty pull
    request. The wait names no particular integration, because the tail is
    project-neutral and the review a host runs is its own (ADR 0016).
    """
    prompt = delivered(workflow, "pull-request")

    assert "automated review" in prompt
    assert "declare a wait" in prompt


def test_the_pull_request_state_declares_its_wait_rather_than_blocking(workflow):
    """The blocking wait ADR 0006 prescribed is superseded: a declared Wait
    ends the turn, and its expiry is the re-check (ADR 0021). Blocking would
    burn a session slot polling, and a Prompt still saying so would have the
    agent doing both."""
    prompt = delivered(workflow, "pull-request")

    assert "end your turn" in prompt
    assert "single long-running command" not in prompt
    assert "ten-minute timeout" not in prompt


def test_the_pull_request_state_waits_only_on_the_review_check(workflow):
    """Waiting on every check would overrun the budget for a reason that has
    nothing to do with the review: a repository's build checks run far longer
    than a review does, so the wait names the review check alone."""
    prompt = delivered(workflow, "pull-request")

    assert "not every check" in prompt


def test_the_pull_request_state_announces_even_if_no_review_arrives(workflow):
    """A repository that runs no review would otherwise hold the Run at a State
    waiting for something that is never coming."""
    assert "if no review" in delivered(workflow, "pull-request").lower()


def test_the_pull_request_state_opens_on_whatever_host_can_open_one(workflow):
    """No longer GitHub-only: a Gitea repository has pull requests and an MCP
    server of its own, so the open path names the host generically rather than
    GitHub alone (ADR 0018). The one named exception stays HCGPS, whose
    conventions are rich enough to earn a skill (ADR 0016)."""
    prompt = delivered(workflow, "pull-request")

    assert "Gitea" in prompt
    assert "/hcgps-pr" in prompt


def test_the_pull_request_state_ends_at_done_when_it_opens_nothing(workflow):
    """How the tail ends is read from the project (ADR 0018): a repository that
    opts out with a naiad.toml marker, or one with no remote to open against,
    has nowhere for the work to land and announces done — already a declared
    successor of this State (ADR 0017). The check comes before the review wait,
    so a local-first Run neither opens a pull request nor waits its ten minutes
    for a review that is never coming."""
    prompt = delivered(workflow, "pull-request")

    assert "naiad.toml" in prompt
    assert "no remote" in prompt
    assert prompt.index("naiad.toml") < prompt.index("automated review")


def test_the_review_fix_state_tolerates_a_pull_request_with_no_findings(workflow):
    """The timeout path announces review-fix anyway, and Clearing means the
    Prompt arrives in a context that never heard the timeout announced. Without
    this the State is told to fetch findings that are not there, and /fix-review
    — whose contract is that its findings are handed to it — is the State most
    likely to stop and ask a human nobody is awake to be."""
    assert "no review findings" in delivered(workflow, "review-fix")


def test_no_prompt_after_a_clearing_state_refers_back_to_the_cleared_context(workflow):
    """The symptom deferred issue 02 warns about, caught where it is cheap: a
    Prompt delivered into a wiped context that says 'you just' is naming
    something the agent can no longer remember."""
    clearing = [state.name for state in workflow.states if state.clear]

    for state_name in clearing:
        assert "you just" not in delivered(workflow, state_name)


def kickoff(tmp_path, sessions, **options):
    repo = tmp_path / "repo"
    repo.mkdir()

    start_run(
        workflow_path=WORKFLOW_PATH,
        task=TASK,
        target_repo=repo,
        working_branch=BRANCH,
        store=RunStore(tmp_path / "runs"),
        sessions=sessions,
        run_id="20260720-120000-matt-pocock",
        claude_session_id="11111111-1111-1111-1111-111111111111",
        created_at="2026-07-20T12:00:00Z",
        **options,
    )

    (spawn,) = sessions.spawned
    return spawn.initial_prompt


@pytest.mark.parametrize("head", BRANCH_HEADS)
def test_a_run_can_be_started_at_either_branch_head(workflow, tmp_path, sessions, head):
    """An operator who already knows which kind of work they have starts the
    Run at the branch head, and the head's Prompt arrives with the task in it."""
    prompt = kickoff(tmp_path, sessions, start_state=head)

    assert prompt.startswith(f"{SKILLS[head]} {TASK}")
    for successor in next_states(workflow, head):
        assert f"announce {successor}" in prompt


def test_a_run_cannot_be_started_at_the_loop_without_naming_a_ticket(tmp_path, sessions):
    """ADR 0010 describes starting here against a hand-written tracker, so this
    is a path an operator will take. Refused rather than rendered empty: the
    Prompt goes on to say the ticket has been triaged as ready, so a blank one
    tells the agent to trust a decision about a ticket that was never named."""
    with pytest.raises(MissingSubject):
        kickoff(tmp_path, sessions, start_state="implement")

    assert sessions.spawned == []


def test_a_run_started_at_the_loop_with_a_ticket_is_delivered_that_ticket(tmp_path, sessions):
    """The escape hatch works once the ticket is named — which is what makes
    refusing the bare form a correction rather than a removal."""
    prompt = kickoff(tmp_path, sessions, start_state="implement", subject=SUBJECT)

    assert prompt.startswith(f"/implement the ticket at {SUBJECT}")


def test_a_run_started_with_no_state_named_begins_by_classifying_the_task(
    workflow, tmp_path, sessions
):
    """The operator says nothing about where to start and describes the task in
    their own words; the agent decides which kind of work it is. Asserted
    against the shipped file rather than a fixture, because this is the Prompt
    an operator who names nothing actually receives."""
    prompt = kickoff(tmp_path, sessions)

    assert not prompt.startswith("/")
    assert TASK in prompt
    for head in next_states(workflow, "classify"):
        assert f"announce {head}" in prompt


def test_an_unattended_run_tells_the_two_kinds_of_gate_state_apart(workflow):
    """The same file run with --skip-gates, asserted at both Gates together so
    they cannot later be conflated (ADR 0007).

    The grilling State's Prompt names the spec rather than the Gate State
    nobody is there to release: `review` is a routine checkpoint in the declared
    order, and an unattended Run may decline that review. The diagnosing State
    keeps `no-repro`, because a Gate State named as a candidate is a destination
    the agent chose — deleting it would tell a Run that could not reproduce the
    bug to open a pull request for a fix built on no diagnosis.
    """
    assert next_states(workflow, "grill", skip_gates=True) == ("spec",)
    assert next_states(workflow, "grill") == ("review",)

    assert next_states(workflow, "diagnose", skip_gates=True) == ("no-repro", "pull-request")
    assert next_states(workflow, "diagnose") == ("no-repro", "pull-request")
