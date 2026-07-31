"""What the Answerer is asked, and what its reply means. Pure.

The Answerer is a separate headless Claude session, one per Run, resumed across
every Question so that later answers cannot contradict earlier ones. The
operator reads them together as a single log, and an Answerer re-deriving the
architecture from scratch each time will disagree with itself between entries.

Its authority is bounded by whether the answer is discoverable in the
repository. Architecture, conventions, naming, which module owns a concern are
inferable from the code and its docs, and are the Answerer's to settle.
Credentials, external spend and business priorities are not in the repository,
so answering them would be invention dressed as inference. Those it escalates,
and an Escalation is mechanically the notify-and-wait of a Gate State.

Everything here is text in and data out: the adapter runs the session and holds
no rules of its own (ADR 0004).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from naiad.domain.question import Question

# The Answerer's reply is prose ending in one of two markers. Markers rather
# than JSON because the reply is written by a model into a terminal: prose that
# fails to parse as JSON loses the whole answer, whereas a marked line survives
# any preamble the model puts before it.
ANSWER_MARKER = "ANSWER:"
ESCALATE_MARKER = "ESCALATE:"

# How long the Answerer may take over one Question. A bound rather than none
# because a consultation that never returns stalls the whole Run in silence,
# and an operator woken by an Escalation can act where one woken by nothing
# cannot. It lives here beside the other bounds Naiad decides by, rather than
# in the adapter that happens to enforce it (ADR 0004).
CONSULTATION_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class Answered:
    """The Answerer settled it. The text is sent into the Run's session."""

    text: str


@dataclass(frozen=True)
class Escalated:
    """The Answerer declined: the answer is not in the repository. The reason
    is what the operator is woken with, so it says what is missing."""

    reason: str


# What has come back from the Answerer about the Question at hand. None means it
# has not been consulted yet, which is the signal that it should be.
Consultation = Answered | Escalated | None


@dataclass(frozen=True)
class ConsultationSpec:
    """One consultation of the Answerer, as data.

    cwd is the target repository, because an Answerer whose authority is what
    the repository says must be standing in it: answers drawn from generic good
    practice rather than from the conventions actually in use are the failure
    this design exists to avoid.

    resume says whether the session already exists. The id is pinned by Naiad
    rather than discovered afterwards, for the same reason the Run's own session
    id is — discovering it would mean reading Claude Code's internals (ADR 0002).
    """

    cwd: Path
    claude_session_id: str
    text: str
    resume: bool


_BRIEF = """\
You are Naiad's Answerer for an unattended run in this repository.

An agent working here has hit a decision it cannot make alone and no human is
awake to ask. You answer in their stead. You are working in the repository
itself: read it before answering, and answer from what is actually there rather
than from generic good practice.

Your authority is bounded by one test:
**is the answer discoverable in this repository?**

- Architecture, conventions, naming, which module owns a concern, how something
  here is already done — discoverable. These are yours to settle, and you should
  settle them rather than deferring.
- Credentials, external spend, vendor choice, business priorities, anything
  about people or deadlines — not in the repository. Answering these would be
  invention dressed as inference. Escalate them.

Choose from the options given unless every one of them is wrong, in which case
say so and say what should happen instead.

The task this run is working on:
{task}

The question:
{question}

The options the agent was weighing:
{options}

Reply with your reasoning, then end with ONE final line. Choose which of these
two it is — emit exactly one of them, never both. If you settled the question,
the answer line is the only line; there is no "nothing to escalate" to report.

{answer_marker} <the answer, stated so the agent can act on it directly>

or, if and only if you did not settle it:

{escalate_marker} <what a human must decide, and why it is not in this repository>
"""


def render_consultation(question: Question, *, task: str) -> str:
    """What the Answerer is sent for one Question.

    The authority boundary is restated on every consultation rather than only
    on the first. The session is resumed and so has read it before, but a
    resumed session may have been compacted, and a boundary the Answerer has
    forgotten is one it will quietly overstep.
    """
    return _BRIEF.format(
        task=task,
        question=question.text,
        options="\n".join(f"- {option}" for option in question.options),
        answer_marker=ANSWER_MARKER,
        escalate_marker=ESCALATE_MARKER,
    )


def parse_outcome(reply: str) -> Answered | Escalated:
    """What the Answerer's reply amounts to.

    An answer beats an escalation in the same reply, and the last of either
    marker beats the earlier ones. Position alone is not enough: the two
    markers are printed above as a pair, and a reply that fills the pair in
    rather than choosing between them ends on the escalation. Reading that by
    position discards a settled answer and wakes the operator to be told that
    nothing needs them.

    Answer over escalation rather than the reverse, because an Escalation
    asserts 'I cannot settle this' and a reply that also states an answer has
    settled it. It is also the recoverable direction: a needless Escalation
    stalls the Run in silence until a human notices, whereas an answer the
    agent doubts is one it can argue back against.

    A reply with no marked line at all is an Escalation rather than an error.
    Naiad cannot tell an unparseable answer from a wrong one, and sending
    something it does not understand into the session is worse than waking the
    operator — Escalation is already the answer to 'nobody here can settle this'.
    """
    escalation: Escalated | None = None
    for line in reversed(reply.splitlines()):
        line = line.strip()
        if line.startswith(ANSWER_MARKER):
            answer = line[len(ANSWER_MARKER) :].strip()
            if answer:
                return Answered(text=answer)
        if line.startswith(ESCALATE_MARKER) and escalation is None:
            escalation = Escalated(reason=line[len(ESCALATE_MARKER) :].strip() or "no reason given")
    if escalation is not None:
        return escalation
    return Escalated(reason="the Answerer's reply did not end with an answer or an escalation")


__all__ = [
    "ANSWER_MARKER",
    "CONSULTATION_TIMEOUT_SECONDS",
    "ESCALATE_MARKER",
    "Answered",
    "Consultation",
    "ConsultationSpec",
    "Escalated",
    "parse_outcome",
    "render_consultation",
]
