"""The contract the agent must follow to be driven.

Naiad's responsibility and never the Workflow author's: a Workflow file
contains States and Prompts and nothing else. Were this boilerplate pasted into
every Prompt, one omission would produce a State that silently never advances.

It is text rather than a file on disk because it is injected into every fresh
context — a session starting, a Clear, a compaction — and a Run that has just
been Cleared has no memory of having read it before.
"""

from __future__ import annotations

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
phase is genuinely done."""

_NEXT_STATE = "When this phase is done, announce: {next_state}"
_NO_NEXT_STATE = (
    "There is no State expected after this one. Announce whichever State the "
    "workflow calls for; an unknown name is rejected with the valid ones listed."
)


def render_protocol(*, next_state: str | None, naiad: str = DEFAULT_NAIAD) -> str:
    """The Protocol as the agent meets it, naming the State it is expected to
    announce next. The Workflow file owns that ordering, so it is interpolated
    here rather than restated by hand.

    naiad is the command the agent must type. The caller passes the absolute
    path of the naiad driving the Run, because a session's PATH need not hold
    it and a command the agent cannot run leaves it unable to participate.
    """
    preamble = _PREAMBLE.format(
        announce=f"{naiad} {ANNOUNCE_SUBCOMMAND}",
        ask=f"{naiad} {ASK_SUBCOMMAND}",
    )
    expectation = _NEXT_STATE.format(next_state=next_state) if next_state else _NO_NEXT_STATE
    return f"{preamble}\n\n{expectation}\n"


__all__ = ["DEFAULT_NAIAD", "render_protocol"]
