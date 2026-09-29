"""Writing the adopt skill into the operator's Claude configuration.

User skills rather than the target repository's: Naiad writes nothing into the
repository it drives (PRD, 'Storage'), and a skill belongs to the operator's
machine rather than to any one Run — it is installed independently of a Run and
is reached for only when the operator asks for an Adoption.
"""

from __future__ import annotations

from pathlib import Path

from naiad.adapters.claude_config import default_skills_root
from naiad.adapters.executable import naiad_command
from naiad.runtime.atomic import write_atomically
from naiad.skills.adopt import SKILL_NAME, installed_by_naiad, render_adopt_skill

# Claude Code's own name for the file holding a skill.
SKILL_FILE = "SKILL.md"


def install_adopt_skill(*, skills_root: Path | None = None, naiad: str | None = None) -> Path:
    """Install the skill, leaving the rest of the operator's skills alone.

    Idempotent, because installing is something an operator will do again
    without thinking: one directory, one file, rewritten. A copy an older naiad
    wrote is stale rather than precious — the contract is Naiad's — so it is
    replaced, and replacing is what keeps a drifted copy from outliving the
    command it teaches.

    A skill of the same name that Naiad did not write is refused rather than
    replaced: overwriting it would discard something the operator wrote by hand
    in order to install something they can reinstall at any time.

    Without a root the skill goes where Claude Code reads its skills, which
    `CLAUDE_CONFIG_DIR` moves.
    """
    root = default_skills_root() if skills_root is None else Path(skills_root)
    path = root / SKILL_NAME / SKILL_FILE
    _refuse_to_overwrite_theirs(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, render_adopt_skill(naiad=naiad or naiad_command()))
    return path


def _refuse_to_overwrite_theirs(path: Path) -> None:
    if not path.exists():
        return

    if not installed_by_naiad(path.read_text()):
        raise ValueError(
            f"{path} was not installed by naiad; refusing to overwrite it. "
            "Move it aside if you want naiad's own copy of the skill."
        )


__all__ = ["install_adopt_skill"]
