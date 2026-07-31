"""The Protocol as the SessionStart hook prints it.

Composition only: which State the agent owes next was decided in
naiad.domain.transitions and the words were decided in naiad.domain.protocol
(ADR 0004). What is left is reading the Run's Workflow and its latest
Announcement.
"""

from __future__ import annotations

import json
import sys

from naiad.adapters.executable import naiad_command
from naiad.domain.protocol import render_protocol
from naiad.domain.transitions import UnknownState, expected_next_states
from naiad.domain.workflow import WorkflowError, load_workflow
from naiad.runtime.announcements import Announcements
from naiad.runtime.run import Run


def protocol_for(run: Run) -> str:
    """The Protocol this Run's agent should be holding right now.

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

    return render_protocol(
        next_states=expected,
        # The naiad running this hook, so the agent is told to type the one
        # actually driving it rather than whichever the session's PATH holds.
        naiad=naiad_command(),
    )


def injection_for(run: Run) -> str:
    """The Protocol as a SessionStart hook's structured output.

    Claude Code also adds a hook's plain stdout to the context, but saying so
    explicitly is the documented surface for injection and cannot be mistaken
    for incidental chatter from the command (ADR 0002).
    """
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": protocol_for(run),
            }
        }
    )


__all__ = ["injection_for", "protocol_for"]
