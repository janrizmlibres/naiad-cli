"""The Queue on disk: the Entries waiting to become Runs, and what became of each.

An Entry is a Run that does not exist yet. What one carries is
naiad.domain.entry's to say; this is where they are kept.

No status is stored, because whether an Entry is waiting, running, parked or
done is already recorded inside its Run by the party that observed it, and a
second copy the Queue keeps can disagree with the first (ADR 0013). `status_of`
therefore asks the Run rather than reading a field.

No position is stored either, because the id is a sortable timestamp: sorting
by id *is* the Queue order, so removing an Entry renumbers nothing and stepping
over one later remains possible (ADR 0012).

One file per Entry, beside the Runs under the same Naiad-owned home, so that
adding one is a write nothing else has to be locked for.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from naiad.domain.entry import Attachment, Entry
from naiad.runtime.announcements import Announcements
from naiad.runtime.atomic import write_atomically
from naiad.runtime.home import StorageError, refuse_inside_repository
from naiad.runtime.log import RunLog
from naiad.runtime.records import Notices, Waits
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
        self._write(entry)
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

    def attach_run(self, entry: Entry, *, run_id: str) -> Entry:
        """Record which Run an Entry became, and return the Entry saying so.

        The only thing about an Entry that ever changes, and it changes by
        writing the Entry again rather than by mutating one in place, so that
        what is on disk and what the Supervisor holds never differ.

        Written before the Run is watched, because that is what a restarted
        Supervisor reads to find the same Entry again rather than starting a
        second Run for it (ADR 0013).
        """
        attached = replace(entry, run_id=run_id)
        self._write(attached)
        return attached

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

    def _write(self, entry: Entry) -> None:
        """One place that turns an Entry into its file, so that adding one and
        recording what became of it cannot come to disagree about what an Entry
        on disk looks like."""
        write_atomically(self._path(entry.id), json.dumps(_document(entry), indent=2) + "\n")

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
    def _attachment_from(mark: dict[str, Any] | None) -> Attachment | None:
        """The Session an Adoption attaches to, or nothing for the ordinary
        Entry. Read with a default, as skip_gates is: an Entry written before
        Adoption existed still loads, and simply attaches to nothing."""
        if mark is None:
            return None
        return Attachment(
            tmux_pane=mark["tmux_pane"],
            claude_session_id=mark.get("claude_session_id"),
        )

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
            attachment=Queue._attachment_from(document.get("attachment")),
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
    return _run_status(runs.root_for(entry.run_id))


def _run_status(root: Path) -> Status:
    """What a Run's directory records, never waiting: a directory exists, so the
    Run does too. One reading shared by an Entry's status and a Prune's judgment
    of an orphan (ADR 0030), so the two cannot come apart."""
    if RunLog(root).finished():
        return DONE
    # Read with the same Wait key the loop wrote it under (ADR 0021), or a Run
    # parked after its Waits ran out would show as running.
    latest = Announcements(root).latest()
    notified, _nudges = Notices(root).of(latest, wait_count=Waits(root).count(latest))
    return PARKED if notified else RUNNING


@dataclass(frozen=True)
class Pruned:
    """What a Prune took, and what it could not take.

    Two independent facts rather than one verdict per Entry. `removed` is every
    Entry that left the Queue — which is what the operator watches the listing
    shrink by — and `failures` is every refusal met on the way, each naming the
    Run directory that stayed behind. An Entry can appear in both: its file
    went and its Run would not, which leaves an orphan the operator is told
    about by path rather than a removal they were never told about at all.
    """

    removed: list[Entry]
    failures: list[str]
    # The Orphaned Runs (ADR 0030): the ids of those taken, and the paths of
    # those left because they read as running — which only the operator, who can
    # see the session, is placed to judge.
    orphans: list[str]
    skipped: list[str]


def prune(queue: Queue, runs: RunStore) -> Pruned:
    """Take every done Entry out of the Queue, and the Run each became with it.

    Done is asked of `status_of` rather than decided again here, so what the
    listing calls done and what a Prune removes cannot come apart. The other
    three are left where they are (ADR 0029).

    The Queue is read whole before anything is deleted, so an Entry nobody can
    read stops the Prune with the file named rather than partway through work
    that cannot be taken back.

    Per Entry the file goes first and the Run second, which is the order ADR
    0029 turns on: a Run gone while its Entry stayed would read as running for
    ever, and a done Entry showing as running is a listing that lies. A refusal
    is recorded and the next Entry is taken anyway, so one stuck directory
    cannot spare the whole backlog.

    After the Entries, the Orphaned Runs (ADR 0030): every Run directory no
    Entry names is judged by the same reading and taken when it is done or
    parked, left and named when it reads as running.
    """
    removed: list[Entry] = []
    failures: list[str] = []

    entries = queue.all()
    # Every Run this pass leaves a claim on: one an Entry still names must not
    # be judged an orphan, and one whose removal was already attempted must not
    # be attempted twice in the same pass.
    tended = {entry.run_id for entry in entries if entry.run_id is not None}

    for entry in entries:
        if status_of(entry, runs) != DONE:
            continue

        # Believed rather than assumed: an Entry somebody removed by name
        # between the reading and the taking was theirs to remove, and its Run
        # is one they deliberately left alone.
        if not queue.remove(entry.id):
            continue
        removed.append(entry)

        # A done Entry always names the Run it was read as done from, so the
        # guard is for the type rather than for a case: no run_id is waiting,
        # and waiting is not what we are here for.
        if entry.run_id is None:
            continue
        try:
            runs.remove(entry.run_id)
        except StorageError as error:
            failures.append(str(error))

    orphans, skipped = _take_orphans(runs, tended, failures)
    return Pruned(removed=removed, failures=failures, orphans=orphans, skipped=skipped)


def _take_orphans(
    runs: RunStore, tended: set[str], failures: list[str]
) -> tuple[list[str], list[str]]:
    """Take every Orphaned Run that reads done or parked, and name the rest.

    A Run no Entry names can never be ticked, answered or advanced, so done and
    parked alike are finished history without a line (ADR 0030). Running is the
    one reading that cannot tell a live Session from a dead one, and Naiad never
    looks at tmux to find out — so a running orphan is left and named by path,
    every Prune, until the operator who can look removes it.

    A directory that cannot be read is a failure and the next is taken anyway:
    the stop-early rule guards the Entry read, where deleting would follow a
    misreading; here not deleting is the safe act.
    """
    orphans: list[str] = []
    skipped: list[str] = []
    if not runs.root.is_dir():
        return orphans, skipped

    for directory in sorted(path for path in runs.root.iterdir() if path.is_dir()):
        if directory.name in tended:
            continue
        try:
            status = _run_status(directory)
        except (OSError, ValueError, KeyError, TypeError, StorageError) as error:
            failures.append(f"orphaned run directory {directory} cannot be read ({error})")
            continue
        if status == RUNNING:
            skipped.append(str(directory))
            continue
        try:
            runs.remove(directory.name)
            orphans.append(directory.name)
        except StorageError as error:
            failures.append(str(error))

    return orphans, skipped


def branch_of(entry: Entry, runs: RunStore) -> str | None:
    """The Working branch an Entry claims, resolved through its Run when the
    Entry's own record carries none.

    Read rather than copied back onto the Entry, for the reason status is
    (ADR 0013): a second copy could disagree with the first. An Entry queued
    without a branch starts a Run with none, and the agent at its head declares
    the name it derived on the Run — so the Run is where the fact lives, and
    until it is declared (or for a Run whose directory has gone) there is no
    name and nothing is claimed.
    """
    if entry.working_branch is not None:
        return entry.working_branch
    if entry.run_id is None:
        return None
    run = runs.load(entry.run_id)
    return run.working_branch if run is not None else None


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
        "attachment": _attachment_document(entry.attachment),
        "run_id": entry.run_id,
    }


def _attachment_document(attachment: Attachment | None) -> dict[str, Any] | None:
    if attachment is None:
        return None
    return {
        "tmux_pane": attachment.tmux_pane,
        "claude_session_id": attachment.claude_session_id,
    }


__all__ = [
    "DONE",
    "PARKED",
    "RUNNING",
    "WAITING",
    "Pruned",
    "Queue",
    "branch_of",
    "prune",
    "status_of",
]
