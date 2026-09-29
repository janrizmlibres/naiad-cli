"""Writing Naiad's hooks into the operator's Claude Code settings.

User settings rather than the target repository's: Naiad writes nothing into
the repository it drives, and hooks belong to the operator's
machine rather than to any one Run — they are installed independently of a Run
and do nothing when none is attached.
"""

from __future__ import annotations

import json
from pathlib import Path

from naiad.adapters.claude_config import default_settings_path
from naiad.adapters.executable import naiad_command
from naiad.hooks.settings import with_naiad_hooks
from naiad.runtime.atomic import write_atomically


def install_hooks(*, settings_path: Path | None = None, naiad: str | None = None) -> Path:
    """Install the hooks, preserving whatever else is in the file.

    A settings file that does not parse is refused rather than replaced:
    overwriting it would discard the operator's entire configuration in order
    to add two hooks.

    Without a path the hooks go where Claude Code reads its settings, which
    `CLAUDE_CONFIG_DIR` moves.
    """
    path = default_settings_path() if settings_path is None else Path(settings_path)
    existing = _read(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(
        path,
        json.dumps(with_naiad_hooks(existing, naiad=naiad or naiad_command()), indent=2) + "\n",
    )
    return path



def _read(path: Path) -> dict[str, object]:
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}

    if not text.strip():
        return {}

    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON ({error}); refusing to overwrite it") from error

    if not isinstance(document, dict):
        raise ValueError(f"{path} is not a settings object; refusing to overwrite it")
    return document


__all__ = ["install_hooks"]
