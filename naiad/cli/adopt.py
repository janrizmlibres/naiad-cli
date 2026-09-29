"""Adopting the session this command is run from.

An Adoption is for the flow that did not start with Naiad: the human opened a
session themselves, did the early States by hand, and wants the machine to
drive what remains without losing the conversation those States built — which
is exactly what the non-Clearing States feed on. Kickoff cannot serve it,
because a fresh session has none of that context.

Nothing here starts anything. The command validates, enqueues, prints and
exits: the Supervisor remains the one entrance to starting Runs and
attaches the Run on its ordinary pass, when the Lane is free. So the two things
this module holds are the mark that tells it to attach, and the text that
teaches the agent the verbs it is about to need.
"""

from __future__ import annotations

from collections.abc import Mapping

from naiad.domain.entry import Attachment, Entry
from naiad.domain.protocol import render_adoption
from naiad.domain.transitions import UnknownState, expected_next_states
from naiad.domain.workflow import WorkflowError, load_workflow

# tmux's own, set in every process running inside a pane. It is how the adopting
# process says where it stands, and there is nothing to ask: a command cannot be
# told which pane it is in by anyone but the pane.
TMUX_PANE_VARIABLE = "TMUX_PANE"

# The session id, if the session exports it. Nothing today promises that it
# does — a tool call is not a hook, and the hook payload that carries the id is
# not this process's to read — so absent is the expected answer rather than an
# unlucky one. Gathered anyway because it costs a lookup: it is the resolution
# seam's second key, and the seam is happy with whichever keys exist. Nothing is
# inferred from Claude Code's internals to find it; the pane is the
# reliable key and the one an Adoption actually turns on.
CLAUDE_SESSION_VARIABLE = "CLAUDE_SESSION_ID"


class NotInTmux(Exception):
    """Adoption asked of a session with no pane to attach to.

    Delivery is typing into a pane, so a session outside tmux is one Naiad can
    never drive; queueing an Entry marked to attach to nowhere would only defer
    the failure to an attachment that could not happen.
    """


def attachment_in(environ: Mapping[str, str]) -> Attachment:
    """Which Session this process is standing in, read from its environment.

    Taken from the environment rather than named on the command line, because
    the agent typing the command has no way to know its own pane, and one it
    guessed would attach the Run to somebody else's session.
    """
    pane = environ.get(TMUX_PANE_VARIABLE)
    if not pane:
        raise NotInTmux(
            "adoption needs a tmux pane to attach to, and this session is not in "
            "one: naiad delivers prompts by typing into a pane, so a session "
            "outside tmux is one it cannot drive; nothing has been queued"
        )
    return Attachment(
        tmux_pane=pane,
        # Empty reads as absent, as a missing variable does: a session that
        # exported the name and no value has not told us anything.
        claude_session_id=environ.get(CLAUDE_SESSION_VARIABLE) or None,
    )


def teaching_for(entry: Entry, *, supervised: bool, naiad: str) -> str:
    """What the adopting agent is told, once its Entry is on the Queue.

    The expectation is the one the SessionStart hook would render for a Run
    that has announced nothing, and the two agree by construction: an Adoption
    starts where its Entry says and has made no Announcement.

    The Workflow all but cannot fail to load here: the enqueue this follows
    parsed the same file and resolved the same State moments ago, so only an
    edit landing between those two statements reaches the fallback. It is
    caught rather than left to raise because by this point the Entry is on
    disk — a refusal would be a lie about what happened, and would leave the
    agent with no Protocol at all. Silently, unlike the hook's identical
    fallback (naiad.cli.protocol), which says so on stderr because only its
    stdout reaches the agent: here both do, so a complaint the agent cannot act
    on would land in the context this output exists to teach.
    """
    try:
        next_states = expected_next_states(
            load_workflow(entry.workflow_path),
            announced=None,
            started_at=entry.start_state,
            skip_gates=entry.skip_gates,
        )
    except (WorkflowError, UnknownState):
        next_states = ()

    return render_adoption(
        next_states=next_states,
        working_branch=entry.working_branch,
        supervised=supervised,
        naiad=naiad,
    )


__all__ = ["NotInTmux", "attachment_in", "teaching_for"]
