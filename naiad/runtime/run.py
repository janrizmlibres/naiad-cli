"""The Run and the directory that holds it.

Everything Naiad tracks about a Run is reached through the Run object — its
paths, its session, its task. Nothing here is module-global, so a second
concurrent Run is a second object rather than a rewrite.

A Run's directory lives outside the target repository, so nothing Naiad owns
can be committed into a pull request, and the record outlives the working copy.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from naiad.runtime.atomic import write_atomically
from naiad.runtime.home import StorageError, real_path, refuse_inside_repository

METADATA_FILENAME = "run.json"


@dataclass
class Run:
    id: str
    root: Path
    workflow_path: Path
    task: str
    target_repo: Path
    created_at: str
    # The git branch this Run's work belongs on, and what that work stands on.
    # Facts of the Run like the task, so that every Prompt it delivers can name
    # them and a Cleared State still knows its branch. Opaque strings: Naiad
    # runs no git and reads neither of them.
    #
    # A Working branch is given or derived, never invented by Naiad: a Run
    # created from a branchless Entry starts with none, and the agent at its
    # head derives a name and declares it with `naiad branch`.
    working_branch: str | None = None
    predecessor: str | None = None
    # How this Run resolves its next State. Options of the Run rather than of
    # the Workflow: the same Workflow file runs supervised or unattended.
    skip_gates: bool = False
    # The name of the State the Run began at, resolved when it started: the
    # first declared State when the Entry named none. What the Standing State
    # is read from before the Run has announced anything, so that a Workflow
    # edited under a live Run changes no answer. Absent only on a Run written
    # before kickoff recorded it.
    start_state: str | None = None
    # What the Run's first Prompt is to say it is about, when the State it
    # begins at names a Subject. Kept on the Run rather than passed
    # to the delivery, because an adopted Run's first Prompt goes out in a later
    # tick — in a process that may not be the one that started it.
    start_subject: str | None = None
    # Whether this Run joined a Session that already existed instead of opening
    # one. It changes one thing: an adopted Run is owed the Prompt of
    # the State it began at, delivered once a Turn has ended, where a spawned
    # Run was handed it as its session launched.
    adopted: bool = False
    tmux_session: str | None = None
    tmux_pane: str | None = None
    claude_session_id: str | None = None
    # The Answerer's own session, one per Run and resumed across every Question
    # so that its later answers cannot contradict its earlier ones. Recorded
    # here rather than held in the loop because it must survive a watch that is
    # interrupted and restarted, and because nothing about a Run may be
    # module-global.
    answerer_session_id: str | None = None

    @property
    def metadata_path(self) -> Path:
        return self.root / METADATA_FILENAME

    def attach_answerer(self, session_id: str) -> None:
        """Record the Answerer session this Run consults, so every Question
        after the first resumes it rather than starting afresh."""
        self.answerer_session_id = session_id
        self.save()

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
            "working_branch": self.working_branch,
            "predecessor": self.predecessor,
            "skip_gates": self.skip_gates,
            "start_state": self.start_state,
            "start_subject": self.start_subject,
            "adopted": self.adopted,
            "tmux_session": self.tmux_session,
            "tmux_pane": self.tmux_pane,
            "claude_session_id": self.claude_session_id,
            "answerer_session_id": self.answerer_session_id,
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
        working_branch: str | None = None,
        predecessor: str | None = None,
        skip_gates: bool = False,
        start_state: str | None = None,
        start_subject: str | None = None,
        adopted: bool = False,
    ) -> Run:
        target_repo = real_path(target_repo)
        refuse_inside_repository(self.root, target_repo, what="run directory")

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
            working_branch=working_branch,
            predecessor=predecessor,
            skip_gates=skip_gates,
            start_state=start_state,
            start_subject=start_subject,
            adopted=adopted,
        )
        run.save()
        return run

    def root_for(self, run_id: str) -> Path:
        """Where a Run's files are, whether or not it has any yet.

        Asked for by name because several of a Run's records are read straight
        off its directory — its log, its notices — and the layout is this
        store's to know rather than each reader's to rebuild.
        """
        return self.root / run_id

    def load(self, run_id: str) -> Run | None:
        metadata = self.root / run_id / METADATA_FILENAME
        if not metadata.is_file():
            return None
        return self._read(metadata)

    def remove(self, run_id: str) -> None:
        """Take a Run's whole directory — its metadata, its log, everything it
        recorded. A Run that is not there needs no taking, and saying so would
        answer a question nobody asks.

        Destructive where every other method here is not, and asked for by one
        caller alone: a Prune, which takes a done Entry and the Run it became
        together. Nothing is checked before the directory goes,
        because whether a Run is done is read from its files by the Queue, and
        a second reading here could disagree with the first.
        """
        root = self.root_for(run_id)
        if not root.is_dir():
            return
        try:
            shutil.rmtree(root)
        except OSError as error:
            raise StorageError(f"run directory {root} cannot be removed ({error})") from error

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
            # Read with a default, as skip_gates is: a Run written before these
            # fields existed still loads, and simply never had a branch.
            working_branch=document.get("working_branch"),
            predecessor=document.get("predecessor"),
            skip_gates=document.get("skip_gates", False),
            start_state=document.get("start_state"),
            start_subject=document.get("start_subject"),
            adopted=document.get("adopted", False),
            tmux_session=document["tmux_session"],
            tmux_pane=document["tmux_pane"],
            claude_session_id=document["claude_session_id"],
            # Read with a default: a Run started before it had an Answerer is
            # still a Run, and has simply never consulted one.
            answerer_session_id=document.get("answerer_session_id"),
        )


__all__ = ["Run", "RunStore"]
