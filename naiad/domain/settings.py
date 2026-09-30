"""A setting an Entry names for one State of its Workflow.

Which Model a phase earns is usually a judgment about the phase, and the
Workflow file makes it. Sometimes it is a judgment about the task — a queue of
small, well-specified tickets does not need what the Workflow gives
`implement` — and the operator queueing that task is the one who knows. So an
Entry may name a Model or an Effort for a State, and for that State it beats
the State's own key and the file-level default alike.

Every setting names its State. One setting for a whole Run would reach phases
nobody meant it for, such as a planning phase a Run happens to walk through.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from naiad.domain.workflow import State, Workflow

# The settings a Switch can carry, by the name the session's command takes.
Setting = Literal["model", "effort"]

# Every Setting, in the order a State's Switches are typed.
SETTINGS: tuple[Setting, ...] = ("model", "effort")


@dataclass(frozen=True)
class StateSetting:
    """One setting an Entry names for one State. The value is opaque, as a
    Workflow's is: the session is the authority on what names a model."""

    state: str
    setting: Setting
    value: str


class UnusableSetting(Exception):
    """A setting no Switch would ever carry: its State is not one the Workflow
    declares, or is one that never delivers a Prompt. Refused rather than kept,
    because a setting doing nothing while looking as if it did is the surprise
    naming the State was meant to prevent."""


def check_settings(workflow: Workflow, settings: Sequence[StateSetting]) -> None:
    """Refuse a setting no Switch would ever carry, naming the one refused.

    A State the Run may never reach is not refused: where a Run goes is known
    only as it goes, and a setting that is never typed costs nothing."""
    seen: set[tuple[str, Setting]] = set()
    for named in settings:
        if (named.state, named.setting) in seen:
            raise UnusableSetting(
                f"a {named.setting} is named twice for '{named.state}'; "
                f"name each setting once per State"
            )
        seen.add((named.state, named.setting))

        state = workflow.state(named.state)
        if state is None:
            valid = ", ".join(declared.name for declared in workflow.states)
            raise UnusableSetting(
                f"a {named.setting} is named for '{named.state}', which is not a State "
                f"of this workflow; it declares: {valid}"
            )
        # Terminal before Gate: a Terminal State has no Prompt either, and
        # "gate" would name the wrong reason it is never typed a Switch.
        if state.terminal:
            raise UnusableSetting(
                f"a {named.setting} is named for '{state.name}', a terminal state, "
                f"where the run ends and no Switch is typed; name a State with a prompt"
            )
        if state.is_gate_state:
            raise UnusableSetting(
                f"a {named.setting} is named for '{state.name}', a gate state, "
                f"which delivers no prompt and so is never typed a Switch; "
                f"name a State with a prompt"
            )


def setting_of(state: State, setting: Setting, settings: Sequence[StateSetting]) -> str | None:
    """What this State asks of the session for one setting: the Entry's value
    where it named one for this State, and the Workflow's otherwise — which is
    the State's own key, the file-level default already applied, or nothing."""
    for named in settings:
        if named.state == state.name and named.setting == setting:
            return named.value
    return state.model if setting == "model" else state.effort


__all__ = ["SETTINGS", "Setting", "StateSetting", "UnusableSetting", "check_settings", "setting_of"]
