"""The Queue: the Entries waiting to become Runs, and what became of each.

An Entry is a Run that does not exist yet. It carries what kickoff would
otherwise be told and the id of the Run it became, and nothing else — no
status, no position (ADR 0013).

No status, because whether an Entry is waiting, running, parked or done is
already recorded inside its Run by the party that observed it, and a second
copy the Queue keeps can disagree with the first. `status_of` therefore asks
the Run rather than reading a field.

No position, because the id is a sortable timestamp: sorting by id *is* the
Queue order, so removing an Entry renumbers nothing and stepping over one
later remains possible (ADR 0012).

One file per Entry, beside the Runs under the same Naiad-owned home, so that
adding one is a write nothing else has to be locked for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from naiad.runtime.announcements import Announcements
from naiad.runtime.atomic import write_atomically
from naiad.runtime.home import StorageError, refuse_inside_repository
from naiad.runtime.log import RunLog
from naiad.runtime.records import Notices
from naiad.runtime.run import RunStore

ENTRY_SUFFIX = ".json"

# What became of an Entry, derived from its Run and never stored (ADR 0013).
# The four the glossary names and no fifth: a word the Queue invented would be
# a claim about a Run that the Run had not made — which is why the type is
# closed rather than a bare string.
Status = Literal["waiting", "running", "parked", "done"]

WAITING: Status = "waiting"
RUNNING: Status = "running"
PARKED: Status = "parked"
DONE: Status = "done"


@dataclass(frozen=True)
class Entry:
    """One piece of work waiting to be run.

    Frozen, because everything it carries was decided when it was made. The one
    thing that changes about an Entry — which Run it became — is recorded by
    writing the Entry again rather than by mutating it in place, so that what is
    on disk and what is in hand never differ.
    """

    id: str
    workflow_path: Path
    task: str
    target_repo: Path
    # Required of every Entry and refused before one exists, because Naiad
    # derives no branch name from a repository's conventions (ADR 0015).
    working_branch: str
    created_at: str
    # Optional and opaque: recorded and passed on without being read.
    pinned_base: str | None = None
    start_state: str | None = None
    subject: str | None = None
    skip_gates: bool = False
    # What became of it: absent until the Entry starts, and the only field that
    # says anything about the Run. Everything else is asked of the Run itself.
    run_id: str | None = None


class Queue:
    """The Entries on disk. Constructed with its root rather than reading a
    module-level path, so tests and a second Queue each get their own."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def add(self, entry: Entry) -> Entry:
        refuse_inside_repository(self.root, entry.target_repo, what="queue directory")

        path = self._path(entry.id)
        if path.exists():
            raise StorageError(f"entry '{entry.id}' already exists at {path}")

        self.root.mkdir(parents=True, exist_ok=True)
        write_atomically(path, json.dumps(_document(entry), indent=2) + "\n")
        return entry

    def all(self) -> list[Entry]:
        """Every Entry, in id order — which is Queue order, since an id is a
        sortable timestamp and no Entry holds a position."""
        if not self.root.is_dir():
            return []
        return [
            self._read(path)
            for path in sorted(self.root.iterdir())
            if path.suffix == ENTRY_SUFFIX and path.is_file()
        ]

    def remove(self, entry_id: str) -> bool:
        """Take an Entry out of the Queue, and touch nothing else.

        Removal is a Queue operation: any Run the Entry produced, and the
        session that Run is in, are left exactly as they were. False when there
        was no such Entry, so that the caller can say so rather than guess.
        """
        try:
            self._path(entry_id).unlink()
        except FileNotFoundError:
            return False
        return True

    def _path(self, entry_id: str) -> Path:
        return self.root / f"{entry_id}{ENTRY_SUFFIX}"

    def _read(self, path: Path) -> Entry:
        """One Entry off disk, or a refusal naming the file.

        One file per Entry is storage the operator can see, so one they have
        truncated or hand-edited is a mistake they can make — and a Queue that
        raised something the commands cannot report would answer it with a
        traceback. Reported rather than skipped: an Entry quietly dropped from
        the listing is work that would never run and nobody would be told.
        """
        try:
            document = json.loads(path.read_text())
            return self._entry_from(document)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise StorageError(f"entry file {path} cannot be read ({error})") from error

    @staticmethod
    def _entry_from(document: dict[str, Any]) -> Entry:
        return Entry(
            id=document["id"],
            workflow_path=Path(document["workflow_path"]),
            task=document["task"],
            target_repo=Path(document["target_repo"]),
            working_branch=document["working_branch"],
            created_at=document["created_at"],
            pinned_base=document.get("pinned_base"),
            start_state=document.get("start_state"),
            subject=document.get("subject"),
            skip_gates=document.get("skip_gates", False),
            run_id=document.get("run_id"),
        )


def status_of(entry: Entry, runs: RunStore) -> Status:
    """What became of an Entry, asked of its Run.

    Read rather than stored (ADR 0013), and in the order the four answers
    exclude one another: no Run at all is waiting; a Run whose log records an
    ending is done however loudly it asked for a human on the way; a Run
    notified about the Announcement it is still standing in is parked, since a
    notice against an Announcement the agent has left was re-armed by the
    announcing; anything else is running.

    A Run whose directory somebody has deleted therefore reads as running, and
    that is the honest answer rather than a gap: the Entry started it and
    nothing in what remains says it ended. Inventing a fifth word for it would
    have the Queue claiming something no Run ever recorded.
    """
    if entry.run_id is None:
        return WAITING

    # Asked of the store rather than by rebuilding its layout here: where a
    # Run's files live is the Run store's to know. Its directory rather than its
    # metadata, because every fact below is a file in it and none of them needs
    # the Run object to answer.
    root = runs.root_for(entry.run_id)
    if RunLog(root).finished():
        return DONE
    notified, _nudges = Notices(root).of(Announcements(root).latest())
    return PARKED if notified else RUNNING


def _document(entry: Entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "workflow_path": str(entry.workflow_path),
        "task": entry.task,
        "target_repo": str(entry.target_repo),
        "working_branch": entry.working_branch,
        "created_at": entry.created_at,
        "pinned_base": entry.pinned_base,
        "start_state": entry.start_state,
        "subject": entry.subject,
        "skip_gates": entry.skip_gates,
        "run_id": entry.run_id,
    }


__all__ = [
    "DONE",
    "PARKED",
    "RUNNING",
    "WAITING",
    "Entry",
    "Queue",
    "status_of",
]
