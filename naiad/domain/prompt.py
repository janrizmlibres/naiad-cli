"""Rendering a State's Prompt for delivery.

Only the placeholders Naiad defines are substituted. Anything else that looks
like a placeholder is left alone: Prompts routinely carry JSON and code, and a
Prompt is prose sent to an agent rather than a format string.
"""

from __future__ import annotations


def render_prompt(prompt: str, *, task: str, next_state: str | None) -> str:
    return prompt.replace("{task}", task).replace("{next_state}", next_state or "")
