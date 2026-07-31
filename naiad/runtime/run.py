"""The Run and the directory that holds it.

Everything Naiad tracks about a Run is reached through the Run object — its
paths, its session, its task. Nothing here is module-global, so a second
concurrent Run is a second object rather than a rewrite (ADR 0004).

A Run's directory lives outside the target repository, so nothing Naiad owns
can be committed into a pull request, and the record outlives the working copy
(PRD, 'Storage').
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from naiad.runtime.atomic import write_atomically

METADATA_FILENAME = "run.json"


class StorageError(Exception):
    """A Run's directory cannot be created where it was asked for."""


def default_runs_root() -> Path:
    """Where Runs live unless the operator says otherwise."""
    override = os.environ.get("NAIAD_HOME")
    home = Path(override) if override else Path.home() / ".naiad"
    return home / "runs"


@dataclass
class Run:
    id: str
    root: Path
    workflow_path: Path
    task: str
    target_repo: Path
    created_at: str
    tmux_session: str | None = None
    tmux_pane: str | None = None
    claude_session_id: str | None = None

    @property
    def metadata_path(self) -> Path:
        return self.root / METADATA_FILENAME

    def attach_session(
        self,
        *,
        tmux_session: str,
        tmux_pane: str,
        claude_session_id: str | None = None,
    ) -> None:
        """Record the session this Run drives, so the Run can later be resolved
        from the session rather than from an environment variable."""
        self.tmux_session = tmux_session
        self.tmux_pane = tmux_pane
        self.claude_session_id = claude_session_id
        self.save()

    def save(self) -> None:
        write_atomically(self.metadata_path, json.dumps(self._as_document(), indent=2) + "\n")

    def _as_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_path": str(self.workflow_path),
            "task": self.task,
            "target_repo": str(self.target_repo),
            "created_at": self.created_at,
            "tmux_session": self.tmux_session,
            "tmux_pane": self.tmux_pane,
            "claude_session_id": self.claude_session_id,
        }


class RunStore:
    """The directory of Runs. Constructed with its root rather than reading a
    module-level path, so tests and concurrent Runs each get their own."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def create(
        self,
        *,
        run_id: str,
        workflow_path: Path,
        task: str,
        target_repo: Path,
        created_at: str,
    ) -> Run:
        target_repo = _real(target_repo)
        root = _real(self.root)
        if root == target_repo or target_repo in root.parents:
            raise StorageError(
                f"run directory {self.root} lies inside the target repository "
                f"{target_repo}; naiad never writes into the target repository"
            )

        run_root = self.root / run_id
        if run_root.exists():
            raise StorageError(f"run '{run_id}' already exists at {run_root}")

        run_root.mkdir(parents=True)
        run = Run(
            id=run_id,
            root=run_root,
            workflow_path=Path(workflow_path),
            task=task,
            target_repo=target_repo,
            created_at=created_at,
        )
        run.save()
        return run

    def load(self, run_id: str) -> Run | None:
        metadata = self.root / run_id / METADATA_FILENAME
        if not metadata.is_file():
            return None
        return self._read(metadata)

    def all(self) -> list[Run]:
        if not self.root.is_dir():
            return []
        runs = [self.load(entry.name) for entry in sorted(self.root.iterdir()) if entry.is_dir()]
        return [run for run in runs if run is not None]

    def _read(self, metadata: Path) -> Run:
        document = json.loads(metadata.read_text())
        return Run(
            id=document["id"],
            root=metadata.parent,
            workflow_path=Path(document["workflow_path"]),
            task=document["task"],
            target_repo=Path(document["target_repo"]),
            created_at=document["created_at"],
            tmux_session=document["tmux_session"],
            tmux_pane=document["tmux_pane"],
            claude_session_id=document["claude_session_id"],
        )


def _real(path: Path) -> Path:
    """Absolute, symlinks resolved as far as they exist. The containment check
    must compare real locations, and the run directory does not exist yet."""
    return Path(os.path.realpath(path))


__all__ = ["Run", "RunStore", "StorageError", "default_runs_root"]
