"""Rendering a State's Prompt for delivery.

Only the placeholders Naiad defines are substituted. Anything else that looks
like a placeholder is left alone: Prompts routinely carry JSON and code, and a
Prompt is prose sent to an agent rather than a format string.
"""

from __future__ import annotations

from collections.abc import Sequence

from naiad.domain.join import FinishedChild, render_children

# The placeholders something asks a Prompt about rather than merely
# substituting, which is what earns a placeholder a name here: the askers must
# be asking about the same string as the substitution below. Three guards
# refuse work whose Prompt names a Subject with none given, and the
# announce command refuses a branchless Run once a Prompt carrying the branch
# placeholder has gone out.
SUBJECT_PLACEHOLDER = "{subject}"
BRANCH_PLACEHOLDER = "{branch}"
# Asked about by the Workflow loader, which refuses the slot outside a Join
# State: nowhere else are Children named.
CHILDREN_PLACEHOLDER = "{children}"


def render_candidates(candidates: Sequence[str]) -> str:
    """A State's candidate successors as the agent reads them.

    Lives here rather than in each caller because three of them speak the same
    set of names — the Prompt, the Protocol, and the Run log describing what
    was delivered — and three renderings would drift into describing the same
    fork three different ways. The log reads as the agent was told, which is
    the point of a diagnostic.

    Joined as prose rather than as a list, because it is read mid-sentence:
    'announce no-repro or pull-request'.
    """
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]
    return f"{', '.join(candidates[:-1])} or {candidates[-1]}"


def render_prompt(
    prompt: str,
    *,
    task: str,
    next_states: Sequence[str],
    subject: str | None = None,
    branch: str | None = None,
    predecessor: str | None = None,
    children: Sequence[FinishedChild] = (),
    child_limit: int | None = None,
) -> str:
    """next_states is plural even though most States have exactly one: at a
    Branching State the Prompt reads as naming both exits, and the Prompt's own
    text supplies the criterion for choosing between them.

    The placeholder a Workflow author writes stays `{next_state}`, singular.
    It is the slot for whatever comes next rather than a promise of one name,
    and renaming it would invalidate every Workflow file in existence to
    describe a fork most States do not have.

    subject is whatever the agent said its Announcement was about, substituted
    without being read: that it names a ticket is known to the Workflow and to
    the agent, and to nothing here.

    A missing Subject renders as nothing rather than raising. The Prompt that
    needed one is unrenderable either way, and the useful place to say so is
    the announce command, where the agent is still in its own turn and can
    correct itself — raising here would only reach a human.

    branch and predecessor are Run-level facts like the task rather than
    Announcement-level ones like the Subject, which is why they reach every
    Prompt a Run delivers and not only its first: both heads of the shipped
    Workflow Clear, and a State that has forgotten everything can still name
    the branch it is working on.

    They stay separate arguments rather than one object grouping the four
    Run-level facts. The type that object wants to be already exists and is
    called Run — both callers pass exactly its fields — but this module is
    domain and the Run is runtime, so taking one would invert the layering
    every other rule here observes. A second type holding a copy of four of
    the Run's fields buys nothing but a place for them to drift. The Children
    a Join State names are no Run-level fact either, being decided per
    Announcement as the Subject is.

    Both are opaque. The Predecessor especially is substituted without being
    read — Naiad neither asks git whether that branch exists nor decides
    whether the Run should stand on it, which is the Prompt's judgment to make.
    An absent Predecessor is ordinary, being what the first Entry for a
    repository has, and renders as nothing. So does an absent Working branch,
    and rendering empty is the Prompt's cue to derive and declare one; a
    declaration then forgotten is refused at the next Announcement, where the
    agent can still correct it, rather than here.

    child_limit is the Run's own Child limit, a Run-level fact like the
    branch, rendered as the number or as nothing when the Entry named none.
    Naiad counts with it; what a limit means for the work — that one builds in
    the Parent's own Session rather than through Children, say — is the
    Prompt's to decide.

    children is the finished Children a Join State's delivery names, one line
    each. The loader refuses the slot anywhere else, and it renders `- none`
    when none is named.
    """
    return (
        prompt.replace("{task}", task)
        .replace("{next_state}", render_candidates(next_states))
        .replace(SUBJECT_PLACEHOLDER, subject or "")
        .replace(BRANCH_PLACEHOLDER, branch or "")
        .replace("{predecessor}", predecessor or "")
        .replace(CHILDREN_PLACEHOLDER, render_children(children))
        .replace("{child_limit}", "" if child_limit is None else str(child_limit))
    )


__all__ = [
    "BRANCH_PLACEHOLDER",
    "CHILDREN_PLACEHOLDER",
    "SUBJECT_PLACEHOLDER",
    "render_candidates",
    "render_prompt",
]
