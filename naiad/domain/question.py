"""What the agent could not decide alone, as data.

A Question carries its own text and every option the agent was weighing.
Naiad reads no Claude Code internals (ADR 0002), so a Question it cannot see
does not exist — there is no conversation to lift one out of.

The options are carried for two reasons beyond that. Whoever answers should be
choosing between the same alternatives the agent faced, rather than a wider set
it had already ruled out; and the operator reading the Answer log afterwards is
judging the choice, which is unjudgeable without knowing what else was on offer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    text: str
    options: tuple[str, ...]
