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

# What the agent is told to type when nobody says which naiad to name. A
# session's PATH is whatever tmux inherited, so the caller passes the absolute
# path of the naiad actually driving the Run wherever it knows it.
DEFAULT_NAIAD = "naiad"

_PREAMBLE = """\
# Naiad protocol

You are being driven through a workflow by Naiad. It cannot see your work and
never decides that a phase is finished — you do, and you say so. Two rules:

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
# stuck will not recover from being asked again.
_NUDGES = (
    "You have stopped without announcing a State, so the run is waiting on you"
    " and nothing further will happen. If the phase you were given is finished,"
    " announce the State you are entering with `{announce} <name>`. If it is"
    " not finished, carry on with it.",
    "You have still announced nothing and the run is still waiting. Announce"
    " now with `{announce} <name>`, or if you cannot proceed, say plainly in"
    " this session what is blocking you — a human is about to be called.",
)


def render_nudge(*, attempt: int, naiad: str = DEFAULT_NAIAD) -> str:
    """The reminder a silent agent is sent, worded for the attempt it is.

    naiad is the command the agent must type, for the same reason as in the
    Protocol: a session's PATH need not hold it, and a command the agent cannot
    run leaves it just as stuck as the silence did.

    There is one wording per attempt Naiad is willing to make and no clamping,
    so an attempt beyond the bound raises here rather than quietly repeating a
    reminder the agent has already ignored.
    """
    return _NUDGES[attempt - 1].format(announce=f"{naiad} {ANNOUNCE_SUBCOMMAND}")


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


__all__ = ["DEFAULT_NAIAD", "render_answer", "render_nudge", "render_protocol"]
