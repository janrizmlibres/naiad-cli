"""Where Claude Code keeps its configuration, and so where Naiad installs.

Claude Code reads `CLAUDE_CONFIG_DIR` when it is set and `~/.claude` when it is
not, so an operator with a second account has a second configuration and Naiad
must write into the one their Claude Code reads. One function answers that, so
the hooks and the skill cannot disagree about which they mean.
"""

from __future__ import annotations

import os
from pathlib import Path

CONFIG_DIR_VARIABLE = "CLAUDE_CONFIG_DIR"


def claude_config_dir() -> Path:
    """The configuration directory, unless the operator has moved it. An empty
    variable is no override, as for `NAIAD_HOME`."""
    override = os.environ.get(CONFIG_DIR_VARIABLE)
    return Path(override) if override else Path.home() / ".claude"


def default_settings_path() -> Path:
    """The settings file the hooks are installed into."""
    return claude_config_dir() / "settings.json"


def default_skills_root() -> Path:
    """The directory the adopt skill is installed under."""
    return claude_config_dir() / "skills"


__all__ = [
    "CONFIG_DIR_VARIABLE",
    "claude_config_dir",
    "default_settings_path",
    "default_skills_root",
]
