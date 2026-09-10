"""The Protocol as the SessionStart hook prints it.

Composition only: which State the agent owes next was decided in
naiad.domain.transitions and the words were decided in naiad.domain.protocol
(ADR 0004). What is left is reading the Run's Workflow and its latest
Announcement — and, after a Compaction, where the agent stands and whether a
Question of its is still owed an answer, which `naiad ask` already knows how to
read (ADR 0047).
"""

from __future__ import annotations

import json
import sys

from naiad.adapters.executable import naiad_command
from naiad.cli.ask import unanswered_question
from naiad.domain.announcement import Announcement
from naiad.domain.protocol import render_compaction, render_protocol
from naiad.domain.transitions import (
    UnknownState,
    expected_next_states,
    standing_state,
)
from naiad.domain.workflow import WorkflowError, load_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.run import Run


def standing_in(run: Run) -> str | None:
    """The State this Run's agent stands in: its latest Announcement, or the
    State the Run began at before it has made one.

    Read for the Compaction line of the Run log as well as for the reminder,
    so the two cannot name different States. An Announcement needs no Workflow
    to read; only a Run that has announced nothing consults one, and None is
    the answer when that Workflow no longer parses or declares the State the
    Run began at — which the log records as a Compaction nowhere in particular.
    """
    announcement = Announcements(run.root).latest()
    if announcement is not None:
        return announcement.state
    try:
        return standing_state(
            load_workflow(run.workflow_path), announced=None, started_at=run.start_state
        )
    except (WorkflowError, UnknownState):
        return None


def protocol_for(run: Run, *, compacted: bool = False) -> str:
    """The Protocol this Run's agent should be holding right now — and, when
    the fresh context is a Compaction's, the reminder of where it stands.

    A Workflow that no longer parses, or no longer declares the State this Run
    began at, costs the agent its expectation but not its contract: the two
    rules still apply, and an announcement of an unknown State is rejected with
    the valid names anyway. Raising here would instead interrupt the session on
    every fresh context.
    """
    announcement = Announcements(run.root).latest()
    try:
        workflow = load_workflow(run.workflow_path)
        expected = expected_next_states(
            workflow,
            announced=announcement.state if announcement else None,
            started_at=run.start_state,
            skip_gates=run.skip_gates,
        )
    except (WorkflowError, UnknownState) as error:
        # Said out loud on stderr rather than swallowed. Only stdout reaches
        # the agent's context, so this reaches the operator's hook output
        # without the agent reading a complaint it cannot act on.
        print(f"naiad: {error}", file=sys.stderr)
        expected = ()

    protocol = render_protocol(
        next_states=expected,
        # The naiad running this hook, so the agent is told to type the one
        # actually driving it rather than whichever the session's PATH holds.
        naiad=naiad_command(),
    )
    if not compacted:
        return protocol
    standing = standing_in(run)
    if standing is None:
        # Nothing to remind the agent of that would not be a guess.
        return protocol
    reminder = _reminder(run, announcement, standing)
    return f"{protocol.rstrip()}\n\n{reminder}\n"


def _reminder(run: Run, announcement: Announcement | None, standing: str) -> str:
    """The three things a summary may have lost (ADR 0047).

    The Subject is the latest Announcement's, or — before one has been made —
    the one the Run was started with, which is what its first Prompt carried
    and what an Adoption's Opening names. The Question is the one `naiad ask`
    would refuse a second for: still owed an answer, and not handed to a human
    (ADR 0044). One definition of "unanswered", read from where it lives. A
    Wait is not among them: a declared wait survives a summary or does not,
    and either way the agent finds out when it is reminded.
    """
    subject = announcement.subject if announcement is not None else run.start_subject
    pending = unanswered_question(run)
    question = pending.question.text if pending is not None and pending.question else None
    return render_compaction(state=standing, subject=subject, question=question)


def injection_for(run: Run, *, compacted: bool = False) -> str:
    """The Protocol as a SessionStart hook's structured output.

    Claude Code also adds a hook's plain stdout to the context, but saying so
    explicitly is the documented surface for injection and cannot be mistaken
    for incidental chatter from the command (ADR 0002).
    """
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": protocol_for(run, compacted=compacted),
            }
        }
    )


__all__ = ["injection_for", "protocol_for", "standing_in"]
