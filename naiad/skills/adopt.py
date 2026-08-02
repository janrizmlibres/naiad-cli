"""The skill document that teaches the adopt contract.

Pure: a naiad in, a document out. Whoever writes the file decides where it goes
(naiad.skills.install).

The operator's half of an Adoption is one sentence — "start to-spec" — and
everything between that sentence and a queued Entry is the agent's: which
Workflow, which start State, which branch, what the work is, and what to relay
afterwards. None of it is guessable from the sentence, and an agent left to
improvise would queue something the human did not ask for. So the whole
contract lives here, in the one file Claude Code reaches for when the sentence
is said (ADR 0028).

The wording is the agent's to read rather than the operator's, apart from the
description: that is the whole of what Claude Code matches an intent against.
The intents quoted there are the operator's own words, kept verbatim because
they are match strings rather than vocabulary — the glossary's word for what
they ask for is Adoption, and `handover` is reserved for a State of the shipped
Workflow that an agent reading this must not confuse it with.
"""

from __future__ import annotations

from naiad.domain.protocol import DEFAULT_NAIAD

# The directory the skill is installed under, which is also the name Claude
# Code addresses it by.
SKILL_NAME = "naiad-adopt"

# What tells a copy Naiad wrote from a skill of the same name the operator
# wrote themselves. Installation replaces the first and refuses the second, so
# something has to distinguish them — and a marker the operator can read is
# also the warning that hand-edits here do not survive the next install.
INSTALLED_BY_NAIAD = (
    "<!-- Installed by naiad. Replaced whenever naiad is installed; edits are lost. -->"
)

_SKILL = """\
---
name: {name}
description: >-
  Adopt this Claude Code session into a Naiad run, so that Naiad drives the
  remaining phases of a workflow here, with this conversation still in context.
  Use when the human asks for Naiad to drive the rest of the work from this
  session — "start to-spec", "let naiad take over", "naiad, drive the rest from
  here", "run the rest of the workflow on this".
---

{marker}

# Adopting this session into a Naiad run

Naiad is not driving this session. Nothing you have done so far was announced
to it, and no workflow state exists yet. What follows queues a run marked to
attach to this session, so that the phases that remain are driven here rather
than in a fresh session that would hold none of this conversation.

Do all of it in one turn, in this order.

## 1. Name the workflow and the state to start at

The workflow is a bare name from the machine's workflow library, or a path to a
workflow file. The start state is the phase Naiad begins driving at — the one
after the last phase the human did by hand; starting at the workflow's first
state re-runs work that is already done.

Ask the human if either is unclear. No run is attached yet, so asking them
directly is fine here — from the moment you adopt, the protocol's rules apply
instead and questions go through `{naiad} ask`.

## 2. Settle the working branch

Naiad invents no branch name. Two cases, and only two:

- **The human named or already made the branch** this work belongs on: pass it
  as `--branch <name>` below, verbatim. Do not second-guess it.
- **No branch was named:** omit `--branch`. The command's output then tells you
  to derive a name from this repository's conventions, create the branch, and
  declare it with `{naiad} branch <name>`. Do that in this same turn, after the
  adopt command has run.

## 3. Write the task

`--task` is required, and it is yours to write: distil from this conversation
one line saying what the work is. You are the only party holding that
conversation, and the line is what the queue reader and the answerer see. Do
not quote a sentence the human never typed.

## 4. Adopt

```
{naiad} adopt <workflow> --at <state> --task "<what the work is>"
```

Add, where they apply: `--branch <name>` (above), `--repo <path>` if the target
repository is not the working directory, `--base <branch>` for what this work
stands on, `--subject <value>` where the start state's prompt names a subject,
`--skip-gates` for an unattended run of a supervised workflow.

The command validates, queues one entry, prints, and returns at once. It starts
nothing: Naiad's supervisor attaches the run to this session on its own pass,
once the lane for this repository is free.

If it refuses — an unknown workflow, an unknown start state, a branch another
entry already claims, a session outside tmux — then nothing was queued. Report
the refusal to the human as it was worded, and stop. Do not work around it.

## 5. Relay what it printed, then end your turn

What it printed is the naiad protocol, which is the verbs you are about to
need, followed by the little an adoption has to add. Read it and follow it from
here on.

Then tell the human, in your own words:

- that this session is queued to be adopted, and at which state;
- which branch the work will land on;
- if the output says no supervisor is running: that the entry will wait in the
  queue indefinitely until they start one, quoting the command it names.

Then end your turn. The first prompt arrives after your turn has ended and the
lane is free. Announce nothing until it does.
"""


def render_adopt_skill(*, naiad: str = DEFAULT_NAIAD) -> str:
    """The skill as Claude Code will read it.

    naiad is the command the agent must type, for the reason the Protocol names
    one: a session's PATH is whatever the human's shell held, and a command the
    agent cannot run leaves the session unadopted.
    """
    return _SKILL.format(name=SKILL_NAME, marker=INSTALLED_BY_NAIAD, naiad=naiad)


def installed_by_naiad(document: str) -> bool:
    """Whether this is a copy Naiad wrote, and so one it may replace."""
    return INSTALLED_BY_NAIAD in document


__all__ = ["INSTALLED_BY_NAIAD", "SKILL_NAME", "installed_by_naiad", "render_adopt_skill"]
