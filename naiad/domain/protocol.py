"""The contract the agent must follow to be driven.

Naiad's responsibility and never the Workflow author's: a Workflow file
contains States and Prompts and nothing else. Were this boilerplate pasted into
every Prompt, one omission would produce a State that silently never advances.

It is text rather than a file on disk because it is injected into every fresh
context — a session starting, a Clear, a compaction — and a Run that has just
been Cleared has no memory of having read it before.
"""

from __future__ import annotations

from collections.abc import Sequence

from naiad.domain.prompt import render_candidates

ANNOUNCE_SUBCOMMAND = "state"
ASK_SUBCOMMAND = "ask"
WAIT_SUBCOMMAND = "wait"
HOLD_SUBCOMMAND = "hold"
BRANCH_SUBCOMMAND = "branch"
# Two words rather than one, because what an unsupervised Adoption is waiting
# for is a Supervisor and `naiad queue watch` is how a human starts one.
SUPERVISE_SUBCOMMAND = "queue watch"

# What the agent is told to type when nobody says which naiad to name. A
# session's PATH is whatever tmux inherited, so the caller passes the absolute
# path of the naiad actually driving the Run wherever it knows it.
DEFAULT_NAIAD = "naiad"

_PREAMBLE = """\
# Naiad protocol

You are being driven through a workflow by Naiad. It cannot see your work and
never decides that a phase is finished — you do, and you say so. Four rules:

1. **Announce, do not assume.** When you have finished the phase you are in and
   are satisfied with the result, run `{announce} <name>` to announce the
   State you are entering. Naiad reacts to that announcement by giving you the
   next thing to do. Until you announce, nothing happens and the run waits.

2. **Never ask a human directly.** No human is watching, so a question put to
   one blocks forever and the run dies having done nothing. If you need a
   decision you cannot make alone, run
   `{ask} "<your question>" --option "<one>" --option "<another>"`,
   giving every option you were weighing. The answer comes back into this
   session. Do not use AskUserQuestion, and do not stop to ask in prose.

3. **Declare your waits.** If you must wait for something before you can
   announce — background agents you launched, an external check completing —
   run `{wait} "<what you are waiting on>" --seconds <how long>`, then end
   your turn. Silence during a declared wait is left alone; undeclared, it is
   read as a forgotten announcement and you will be reminded. When the wait
   expires you will be reminded then instead: check on the thing, and either
   announce or declare a fresh wait.

4. **Relay a pause.** If the human tells you to pause or stop for now, run
   `{hold} "<their instruction, in their words>"`, then end your turn. The
   run is parked — no reminders, no time limit — until they type into this
   session and send you back to work. Do not spend waits on a pause: a wait
   expires and a pause does not.

Announcing the same State twice is legitimate — that is how a loop phase works,
once per iteration. Announcing is not a report of progress: announce when the
phase is genuinely done.

If the phase you are announcing works on one item of a series, say which with
`--subject <value>`: `{announce} <name> --subject <value>`. You are the one
choosing it, and you are choosing it now, while you can still see the whole
series — the context that receives the next phase will have been cleared. A
State that needs one is rejected without it, and the error names the invocation
to use instead, so you can correct it there and then."""

_NEXT_STATE = "When this phase is done, announce: {next_state}"

# A fork is phrased as a choice rather than an instruction: told to announce
# both, an agent standing at one would try to. Which candidate applies is the
# State's own Prompt to say — Naiad supplies the names and nothing else.
_NEXT_STATES = "When this phase is done, announce whichever applies: {next_states}"

_NO_NEXT_STATE = (
    "There is no State expected after this one. Announce whichever State the "
    "workflow calls for; an unknown name is rejected with the valid ones listed."
)


# What a silent agent is told, one wording per attempt. The second is firmer
# because the first has already been ignored; a third is not offered, because
# the bound is decided in naiad.domain.decide and an agent that is genuinely
# stuck will not recover from being asked again. The first teaches the wait
# verb — it arrives precisely when an undeclared wait is being misread as
# silence, which is the moment the lesson lands (ADR 0021) — and the second
# does not, because a wait declared only to buy off a final warning is the
# evasion the bound exists to stop. The hold verb is taught beside it, for
# the same reason at the same moment: a human's pause answered with silence
# is misread exactly like an undeclared wait (ADR 0025).
_NUDGES = (
    "You have stopped without announcing a State, so the run is waiting on you"
    " and nothing further will happen. If the phase you were given is finished,"
    " announce the State you are entering with `{announce} <name>`. If you are"
    " waiting on something — background agents, an external check — declare it"
    ' with `{wait} "<what for>" --seconds <n>` and you will be left alone until'
    " it expires. If the user told you to pause, declare it with"
    ' `{hold} "<their instruction>"` and the run will be held, unreminded,'
    " until they return. Otherwise, carry on with the phase.",
    "You have still announced nothing and the run is still waiting. Announce"
    " now with `{announce} <name>`, or if you cannot proceed, say plainly in"
    " this session what is blocking you — a human is about to be called.",
)

# What an agent whose declared Wait has lapsed is told instead. Not an
# accusation of forgetting — it followed the Protocol — so the reminder names
# the thing it said it was waiting on and sends it to look there first.
_EXPIRED_NUDGES = (
    'Your wait on "{reason}" has expired and no State has been announced. If'
    " what you were waiting for has arrived, act on it and announce with"
    " `{announce} <name>`. If it has not, check on it and declare a fresh wait"
    ' with `{wait} "<what for>" --seconds <n>`.',
    'Your wait on "{reason}" expired and you have still announced nothing.'
    " Announce now with `{announce} <name>`, or if you cannot proceed, say"
    " plainly in this session what is blocking you — a human is about to be"
    " called.",
)


def render_nudge(
    *, attempt: int, naiad: str = DEFAULT_NAIAD, expired_wait: str | None = None
) -> str:
    """The reminder a silent agent is sent, worded for the attempt it is.

    naiad is the command the agent must type, for the same reason as in the
    Protocol: a session's PATH need not hold it, and a command the agent cannot
    run leaves it just as stuck as the silence did.

    expired_wait is what the agent's lapsed Wait said it was for, when the
    silence followed one (ADR 0021); the wording then points at that thing
    rather than at a Protocol the agent did not forget.

    There is one wording per attempt Naiad is willing to make and no clamping,
    so an attempt beyond the bound raises here rather than quietly repeating a
    reminder the agent has already ignored.
    """
    wordings = _NUDGES if expired_wait is None else _EXPIRED_NUDGES
    return wordings[attempt - 1].format(
        announce=f"{naiad} {ANNOUNCE_SUBCOMMAND}",
        wait=f"{naiad} {WAIT_SUBCOMMAND}",
        hold=f"{naiad} {HOLD_SUBCOMMAND}",
        reason=expired_wait,
    )


_ANSWER = """\
Answer: {answer}"""


def render_answer(answer: str) -> str:
    """How an answer arrives in the agent's session.

    Labelled rather than sent bare, because it lands as a message in a session
    that has been working on other things: an unattributed sentence reads as a
    new instruction, and the agent would act on it instead of resuming what it
    asked about. One word carries that, so it is a label and not a preamble —
    a sentence announcing the answer and another telling the agent to carry on
    say nothing the agent does not already know, having asked the question and
    being mid-State when the reply arrives.
    """
    return _ANSWER.format(answer=answer)


def render_protocol(*, next_states: Sequence[str], naiad: str = DEFAULT_NAIAD) -> str:
    """The Protocol as the agent meets it, naming every State it may announce
    next. The Workflow file owns that ordering, so it is interpolated here
    rather than restated by hand.

    Plural because of the fork: naming a single candidate at a Branching State
    would bias the agent toward whichever the Workflow author happened to list
    first, in precisely the case where its judgment is the point (ADR 0001).
    This matters most after a Clear, when the Protocol is all the agent has.

    naiad is the command the agent must type. The caller passes the absolute
    path of the naiad driving the Run, because a session's PATH need not hold
    it and a command the agent cannot run leaves it unable to participate.
    """
    preamble = _PREAMBLE.format(
        announce=f"{naiad} {ANNOUNCE_SUBCOMMAND}",
        ask=f"{naiad} {ASK_SUBCOMMAND}",
        wait=f"{naiad} {WAIT_SUBCOMMAND}",
        hold=f"{naiad} {HOLD_SUBCOMMAND}",
    )
    # Three sentences rather than one plural sentence covering all three
    # cases: 'announce whichever applies' offers a choice, and offering one
    # where there is a single successor invites the agent to look for the
    # alternative it was not given.
    if not next_states:
        expectation = _NO_NEXT_STATE
    elif len(next_states) == 1:
        expectation = _NEXT_STATE.format(next_state=next_states[0])
    else:
        expectation = _NEXT_STATES.format(next_states=render_candidates(next_states))
    return f"{preamble}\n\n{expectation}\n"


# What only an Adoption has to say, after the Protocol the agent has just been
# taught (ADR 0028). Three things it cannot work out for itself: that nothing
# arrives until its turn ends, that the Prompt waits on the Lane, and — where
# the Entry queued branchless — that settling the branch is its job here,
# because both of the Workflow's branch heads were skipped by starting
# mid-Workflow.
_ADOPTION_CLOSING = """\
This run is queued and is not driving you yet. Its work belongs on the branch
`{working_branch}`, which the human already made: check it out if you are not
standing on it, then end your turn."""

# The branchless wording. The ADR 0022 discipline in as many words, because the
# State that would ordinarily have prepared the branch is behind this start.
_ADOPTION_CLOSING_BRANCHLESS = """\
This run is queued and is not driving you yet. It has no working branch: derive
one from this repository's conventions, create it, and declare it with
`{branch} <name>` — Naiad invents no branch name. Then end your turn."""

_ADOPTION_LANE = """\
The first prompt arrives once the lane for this repository is free; nothing
reaches you while your turn is still running."""

# Relayed rather than acted on: a Supervisor started as a side effect of a tool
# call would have no terminal, no owner and no end, so what the agent can do is
# tell the human.
_ADOPTION_UNSUPERVISED = """\
Tell the human this: no supervisor is running, so this entry will wait in the
queue indefinitely. They start one with `{supervise}`."""

_ADOPTION_SUPERVISED = """\
A supervisor is running and will take this entry in its turn."""


def render_adoption(
    *,
    next_states: Sequence[str],
    working_branch: str | None,
    supervised: bool,
    naiad: str = DEFAULT_NAIAD,
) -> str:
    """What `naiad adopt` prints: the Protocol, and then the little an Adoption
    has to add to it.

    The Protocol arrives here rather than by being typed into the pane, because
    typing would be a second delivery with ordering rules of its own — and the
    agent has to learn the verbs before the Prompt it will answer with them
    arrives (ADR 0028).

    The branch instruction is written for the case it is in rather than
    covering both: an agent whose Entry already claims a branch and is told to
    derive one would create a second branch for the same work, and one told
    only 'settle the branch' has to guess which case it stands in.
    """
    closing = (
        _ADOPTION_CLOSING_BRANCHLESS.format(branch=f"{naiad} {BRANCH_SUBCOMMAND}")
        if working_branch is None
        else _ADOPTION_CLOSING.format(working_branch=working_branch)
    )
    supervision = (
        _ADOPTION_SUPERVISED
        if supervised
        else _ADOPTION_UNSUPERVISED.format(supervise=f"{naiad} {SUPERVISE_SUBCOMMAND}")
    )
    protocol = render_protocol(next_states=next_states, naiad=naiad).rstrip("\n")
    return f"{protocol}\n\n{closing}\n\n{_ADOPTION_LANE}\n\n{supervision}\n"


__all__ = [
    "DEFAULT_NAIAD",
    "HOLD_SUBCOMMAND",
    "WAIT_SUBCOMMAND",
    "render_adoption",
    "render_answer",
    "render_nudge",
    "render_protocol",
]
