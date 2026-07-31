"""The entry point, for the operator and for the agent.

Builds the real dependencies and hands them to the Queue, to the Supervisor's
loop or to the agent's command. Everything identifying a Run — its id, its
Claude session id, the moment it started — is made here and passed in, so the
code under it stays testable over plain data.

Starting a Run goes through the Queue and nowhere else (ADR 0014): `naiad run`
adds an Entry and then adopts or becomes the Supervisor, and nothing here opens
a session except by taking an Entry off the Queue.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from naiad.adapters.answerer import HeadlessAnswerer
from naiad.adapters.executable import naiad_command
from naiad.adapters.lock import SupervisorLock
from naiad.adapters.notify import DesktopNotifications
from naiad.adapters.tmux import TmuxError, TmuxSessions
from naiad.cli.announce import AnnounceError, announce_state
from naiad.cli.ask import AskError, ask_question
from naiad.cli.batch import BatchError, enqueue_batch, load_batch
from naiad.cli.enqueue import REFUSALS, Work, enqueue
from naiad.cli.kickoff import start_run
from naiad.cli.protocol import injection_for
from naiad.cli.refusals import ADD_COMMAND, RUN_COMMAND, Remedy
from naiad.cli.supervisor import supervise_queue
from naiad.cli.watch import watch
from naiad.domain.entry import Entry
from naiad.domain.workflow import load_workflow
from naiad.hooks.install import DEFAULT_SETTINGS_PATH, install_hooks
from naiad.runtime.announcements import Announcements
from naiad.runtime.home import (
    StorageError,
    default_lock_path,
    default_queue_root,
    default_runs_root,
)
from naiad.runtime.queue import Queue, status_of
from naiad.runtime.records import Turns
from naiad.runtime.resolve import NoRunError, RunResolver
from naiad.runtime.run import Run, RunStore

Handler = Callable[[argparse.Namespace], int]

# Everything a command can fail with that the operator or agent should read as
# a message rather than a traceback.
FAILURES = (
    AnnounceError,
    AskError,
    BatchError,
    NoRunError,
    StorageError,
    TmuxError,
    # Everything describing a piece of work can be refused for, taken from the
    # enqueue rather than listed again: a refusal added there and forgotten
    # here would reach the operator as a traceback.
    *REFUSALS,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="naiad")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser(
        "run", help="queue a Workflow against a task, and supervise if nothing else is"
    )
    _describe_the_work(run)
    run.set_defaults(handler=_run)

    queue = subcommands.add_parser("queue", help="the backlog of Entries waiting to run")
    queue_commands = queue.add_subparsers(dest="queue_command", required=True)

    queue_add = queue_commands.add_parser(
        "add", help="add Entries to the Queue, supervising nothing"
    )
    _describe_the_work(queue_add, required=False)
    queue_add.add_argument(
        "--file",
        dest="batch_file",
        type=Path,
        default=None,
        help="queue every Entry a batch file declares, instead of describing one here",
    )
    queue_add.set_defaults(handler=_queue_add)

    queue_list = queue_commands.add_parser(
        "list", help="the Entries in order, each with what became of it"
    )
    queue_list.set_defaults(handler=_queue_list)

    queue_watch = queue_commands.add_parser(
        "watch", help="take the Queue in order, and keep following it for more"
    )
    queue_watch.set_defaults(handler=_queue_watch)

    queue_rm = queue_commands.add_parser(
        "rm", help="remove an Entry, leaving any Run it started alone"
    )
    queue_rm.add_argument("entry_id", help="which Entry, as `naiad queue list` names it")
    queue_rm.set_defaults(handler=_queue_rm)

    state = subcommands.add_parser("state", help="announce the State you are in")
    state.add_argument("name", help="the State's name, as declared by the Workflow")
    state.add_argument(
        "--subject",
        default=None,
        help="what this announcement is about, for a State whose Prompt names one",
    )
    state.set_defaults(handler=_announce)

    ask = subcommands.add_parser("ask", help="ask a Question you cannot decide alone")
    ask.add_argument("question", help="what you need decided")
    ask.add_argument(
        "--option",
        dest="options",
        action="append",
        default=None,
        help="an option you were weighing; pass one per option, and pass every one",
    )
    ask.set_defaults(handler=_ask)

    stopped = subcommands.add_parser("stopped", help="record that a turn ended (Stop hook)")
    stopped.set_defaults(handler=_stopped)

    protocol = subcommands.add_parser(
        "protocol", help="print the Protocol for a fresh context (SessionStart hook)"
    )
    protocol.set_defaults(handler=_protocol)

    install = subcommands.add_parser(
        "install-hooks", help="install Naiad's hooks into your Claude Code settings"
    )
    install.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS_PATH,
        help=f"which settings file to install into (default: {DEFAULT_SETTINGS_PATH})",
    )
    install.set_defaults(handler=_install_hooks)

    watch_parser = subcommands.add_parser(
        "watch", help="drive a Run until it ends or is interrupted"
    )
    watch_parser.add_argument(
        "run_id", nargs="?", default=None, help="which Run (default: this session)"
    )
    watch_parser.set_defaults(handler=_watch)

    arguments = parser.parse_args(argv)
    handler: Handler = arguments.handler
    return handler(arguments)


def _describe_the_work(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    """The options that describe one piece of work, shared by every command
    that creates one — because an Entry is a Run that does not exist yet, and
    two lists that drifted apart would mean queueing could not say something
    starting a Run could.

    The flags read as an operator types them — `--branch`, `--base` — while
    what they set is named as the glossary names it. The translation happens
    here, at the boundary, and nowhere else.

    `required` is false where a batch file may describe the work instead. Which
    of the two is missing is then refused with a message rather than by
    argparse, as the Working branch already is, so that an operator is told
    both ways of saying it rather than only the one they left out.
    """
    # Nothing where the work must be described here, and what makes each
    # positional optional where a file may describe it instead.
    optional: dict[str, Any] = {} if required else {"nargs": "?", "default": None}
    parser.add_argument("workflow", type=Path, help="path to the Workflow file", **optional)
    parser.add_argument("task", help="what the work is", **optional)
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="the target repository (default: the working directory)",
    )
    # Required, but not by argparse: the refusal lives with the other checks
    # (naiad.cli.refusals), so that both entrances are guarded by the same one
    # and the message can say why Naiad invents no Working branch (ADR 0015).
    parser.add_argument(
        "--branch",
        default=None,
        help="the working branch this work's commits belong on (required)",
    )
    # Left under the flag's own name rather than the glossary's, because the two
    # commands make different things of it: a Run records it as its Predecessor,
    # already resolved, while an Entry records it as the pinned base a
    # Predecessor is later resolved *from*. Naming it for either here would put
    # the wrong word in the other command's mouth.
    parser.add_argument(
        "--base",
        default=None,
        help="the branch this work stands on (default: nothing)",
    )
    parser.add_argument(
        "--at",
        dest="start_state",
        default=None,
        help="start at this State rather than the first (default: the first)",
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="what the starting State is to work on, when its Prompt names a subject",
    )
    parser.add_argument(
        "--skip-gates",
        action="store_true",
        help="resolve past Gate States, for an unattended run of a supervised Workflow",
    )


def _announce(arguments: argparse.Namespace) -> int:
    try:
        run = _current_run()
        announcement = announce_state(arguments.name, run=run, subject=arguments.subject)
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"announced {announcement.state} ({announcement.seq})")
    return 0


def _ask(arguments: argparse.Namespace) -> int:
    """Missing options are rejected here rather than by argparse's own
    `required`, so that the agent is told why every option is wanted and can
    correct the call itself."""
    try:
        run = _current_run()
        announcement = ask_question(
            arguments.question, options=arguments.options or [], run=run
        )
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"asked ({announcement.seq}); the answer will arrive in this session")
    return 0


def _stopped(arguments: argparse.Namespace) -> int:
    """The Stop hook. Hooks are installed independently of any Run, so finding
    no Run attached is ordinary and must not be reported as a failure."""
    run = _attached_run()
    if run is None:
        return 0

    latest = Announcements(run.root).latest()
    Turns(run.root).record_end(latest_seq=latest.seq if latest else None)
    return 0


def _protocol(arguments: argparse.Namespace) -> int:
    """The SessionStart hook, run on startup, on Clear and on compaction — the
    three moments a context is created or destroyed. Like the Stop hook it is
    installed independently of any Run, so a session nobody is driving prints
    nothing and succeeds rather than failing."""
    run = _attached_run()
    if run is None:
        return 0

    print(injection_for(run))
    return 0


def _install_hooks(arguments: argparse.Namespace) -> int:
    """Installed once for the machine rather than per Run: the hooks do nothing
    when no Run is attached to the session that fired them."""
    try:
        path = install_hooks(settings_path=arguments.settings)
    except (OSError, ValueError) as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"installed naiad's hooks into {path}")
    return 0


def _watch(arguments: argparse.Namespace) -> int:
    """Drive one named Run — and not while a Supervisor is driving the Queue.

    The Queue is sequential, so a held lock means the Supervisor is driving the
    only live Run, and a second ticker on one Run delivers everything twice.
    """
    if SupervisorLock(default_lock_path()).held():
        print(
            "naiad: a supervisor is already driving the queue's live run; "
            "a second watch would deliver everything twice",
            file=sys.stderr,
        )
        return 2

    try:
        run = _named_run(arguments.run_id) if arguments.run_id else _current_run()
        _drive(run)
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        # The operator giving up on a Run that has not ended. The session is
        # left alive exactly as a finished Run's is.
        pass
    return 0


def _drive(run: Run) -> None:
    """Drive one Run until it ends, with the real session, notifier and
    Answerer.

    One place, so that the Run an operator named and the Run the Supervisor
    took off the Queue are driven by the same loop with the same dependencies.
    """
    # The line the operator needs to look in on the work, printed where the Run
    # is driven rather than where it was queued: an Entry queued tonight is
    # started hours later, and the session it names does not exist until then.
    print(f"watching {run.id}   (tmux attach -t {run.tmux_session})")
    watch(
        run=run,
        workflow=load_workflow(run.workflow_path),
        session=TmuxSessions(),
        notifier=DesktopNotifications(),
        answerer=HeadlessAnswerer(),
        # The naiad driving this Run, so a nudged agent is told to type the
        # command that exists rather than whatever the session's PATH holds.
        naiad=naiad_command(),
    )


def _named_run(run_id: str) -> Run:
    """The Run the operator named. Falling back to whichever Run this session
    belongs to would silently drive a different one than the one asked for."""
    run = RunStore(default_runs_root()).load(run_id)
    if run is None:
        raise StorageError(f"no run '{run_id}' under {default_runs_root()}")
    return run


def _current_run() -> Run:
    run = _attached_run()
    if run is None:
        raise NoRunError("no run is attached to this session")
    return run


def _attached_run() -> Run | None:
    """Which Run this session belongs to, asked through the one seam that knows
    (naiad.runtime.resolve) rather than read from the environment here."""
    store = RunStore(default_runs_root())
    return RunResolver(store, os.environ).resolve(tmux_pane=os.environ.get("TMUX_PANE"))


def _run(arguments: argparse.Namespace) -> int:
    """The one entrance to starting Runs (ADR 0014): add one Entry, then adopt
    or become.

    It spawns no session of its own. A second entrance would bypass the guard
    that matters most — nothing would stop an immediate Run putting a second
    agent into the working tree a Supervisor is already driving a Run in — and
    an invariant with two places to break it is a convention.

    So the Entry is appended rather than jumped ahead: the command stopped
    meaning 'start this now' the moment a Queue existed, and where the Entry
    lands is the honest place for that to show.
    """
    queued = _queued(arguments, remedy=RUN_COMMAND)
    if queued is None:
        return 2

    with SupervisorLock(default_lock_path()).taken() as mine:
        if not mine:
            # Fire-and-forget. Adding work never blocks on work already
            # running, and the Supervisor holding the lock takes this Entry in
            # its turn.
            print("a supervisor is already running; it will take this in turn")
            return 0
        return _supervise(following=False)


def _queue_add(arguments: argparse.Namespace) -> int:
    """Adds Entries and returns. It supervises nothing — no lock, no session,
    no watching — because this is the command an agent inside a session uses,
    and a tool call that became a process blocking for hours is the failure the
    Queue exists to avoid.

    One Entry described in flags, or as many as a batch file declares. The two
    are refused together rather than one silently ignoring the other, since an
    operator who typed both believes both were read.
    """
    if arguments.batch_file is not None:
        if _describes_one_entry(arguments):
            print(
                "naiad: --file describes the work itself, so the options that "
                "describe one entry belong in the file; drop them or drop --file",
                file=sys.stderr,
            )
            return 2
        return _queued_from_file(arguments)

    if arguments.workflow is None or arguments.task is None:
        # Which half is missing, because argparse no longer says: the
        # positionals had to become optional for a file to describe them
        # instead, and an operator who typed a Workflow and forgot the task
        # should not be told they described nothing.
        missing = "no task" if arguments.workflow is not None else "no workflow and no task"
        print(
            f"naiad: {missing} was given, and no batch file either; "
            "try: naiad queue add <workflow> <task> --branch <branch>, "
            "or naiad queue add --file <batch.toml>",
            file=sys.stderr,
        )
        return 2

    return 0 if _queued(arguments, remedy=ADD_COMMAND) is not None else 2


def _describes_one_entry(arguments: argparse.Namespace) -> bool:
    """Whether anything on the command line describes a single piece of work.
    Every option `_describe_the_work` adds, because a batch file says all of
    them and each has a key of its own to say it with."""
    return any(
        said not in (None, False)
        for said in (
            arguments.workflow,
            arguments.task,
            arguments.repo,
            arguments.branch,
            arguments.base,
            arguments.start_state,
            arguments.subject,
            arguments.skip_gates,
        )
    )


def _queued_from_file(arguments: argparse.Namespace) -> int:
    """Every Entry a batch file declares, or none of them.

    The whole file is read and validated before anything is written, because a
    file with one bad Entry leaving a partial Queue behind gives no signal that
    the rest is missing.
    """
    path = arguments.batch_file.expanduser().resolve()
    added = datetime.now(timezone.utc)

    try:
        works = load_batch(path, repo=Path.cwd())
        entries = enqueue_batch(
            works,
            queue=Queue(default_queue_root()),
            entry_ids=_batch_ids(added, works),
            # One moment for the whole file, because one command wrote them
            # all. Only the ids are spaced, and spacing them is how they sort
            # rather than a claim that the Entries were added at four times.
            created_at=_timestamp(added),
            source=str(path),
        )
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    for entry in entries:
        _report(entry)
    return 0


def _queued(arguments: argparse.Namespace, *, remedy: Remedy) -> Entry | None:
    """One Entry from what was typed, or nothing when it was refused.

    Shared by both entrances so that neither can queue something the other
    would have refused, and so that an Entry means the same thing whichever
    command made it. `remedy` is the vocabulary the operator described the work
    in, quoted back by every refusal so that what they read is something they
    can act on.
    """
    workflow_path = arguments.workflow.expanduser().resolve()
    target_repo = (arguments.repo or Path.cwd()).expanduser().resolve()
    added = datetime.now(timezone.utc)

    try:
        entry = enqueue(
            Work(
                workflow_path=workflow_path,
                task=arguments.task,
                target_repo=target_repo,
                working_branch=arguments.branch,
                pinned_base=arguments.base,
                start_state=arguments.start_state,
                subject=arguments.subject,
                skip_gates=arguments.skip_gates,
            ),
            queue=Queue(default_queue_root()),
            entry_id=_entry_id(added, workflow_path),
            created_at=_timestamp(added),
            remedy=remedy,
        )
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return None

    _report(entry)
    return entry


def _report(entry: Entry) -> None:
    """What an Entry looks like once it is queued. One place, so that a batch
    reports each of its Entries exactly as a single one is reported."""
    print(f"queued {entry.id}")
    print(f"  branch {entry.working_branch}   in {entry.target_repo}")


def _queue_list(arguments: argparse.Namespace) -> int:
    """The Entries in id order, which is Queue order, each with what became of
    it — asked of its Run rather than read from a status the Queue keeps
    (ADR 0013)."""
    try:
        entries = Queue(default_queue_root()).all()
    except FAILURES as error:
        # An Entry file the operator has damaged. They can see these files, so
        # they can break one, and a traceback is not something they can act on.
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    if not entries:
        print(f"the queue is empty ({default_queue_root()})")
        return 0

    runs = RunStore(default_runs_root())
    for entry in entries:
        print(_queue_line(entry, runs))
    return 0


def _queue_line(entry: Entry, runs: RunStore) -> str:
    """One Entry as one line: which, what became of it, where, on what branch,
    and what the work is.

    The repository in full rather than by its directory's name, because one
    Queue spans every repository and two checkouts of the same project — a
    worktree, a second clone — share that name and would otherwise read as one.
    """
    became = status_of(entry, runs)
    line = (
        f"{entry.id}  {became:<7}  {_shortened(entry.target_repo)}  "
        f"{entry.working_branch}  {entry.task}"
    )
    return line if entry.run_id is None else f"{line}  ({entry.run_id})"


def _shortened(path: Path) -> str:
    """A path with the operator's home written the way they would write it, so
    that a line naming the repository in full still fits on one."""
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)


def _queue_watch(arguments: argparse.Namespace) -> int:
    """Supervise: take the Queue in order, and keep following it once it is
    empty so that Entries added later are picked up.

    A second Supervisor is refused rather than queued behind the first, because
    two of them each take the first waiting Entry and put two agents in one
    working tree — which is the single thing one-at-a-time exists to prevent.
    """
    with SupervisorLock(default_lock_path()).taken() as mine:
        if not mine:
            print(
                "naiad: a supervisor is already running, and only one may drive "
                "the queue; queue work with `naiad run` or `naiad queue add` instead",
                file=sys.stderr,
            )
            return 2
        return _supervise(following=True)


def _supervise(*, following: bool) -> int:
    """Drive the Queue, with the lock already in hand.

    One loop for both entrances, differing only in what it does with nothing to
    do: `naiad run` drains and gives the operator their prompt back, while
    `naiad queue watch` follows so that Entries added later are picked up.

    It holds no rules of its own. Which Entry is next, whether it is started or
    resumed, and what its work stands on are naiad.domain.supervise's to say;
    this builds the real dependencies and hands them over.
    """
    try:
        supervise_queue(
            queue=Queue(default_queue_root()),
            runs=RunStore(default_runs_root()),
            start=_start_entry,
            drive=_drive,
            following=following,
        )
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        # The operator stopping the night. The Queue is on disk and every
        # session is left alive, so there is nothing to clean up — and a
        # Supervisor started again picks up the Entry it was in the middle of.
        # The lock goes with the process, so nothing is left to reconcile.
        pass
    return 0


def _start_entry(entry: Entry, predecessor: str | None) -> Run:
    """Turn one Entry into the Run it always described.

    Everything identifying the Run — its id, its Claude session, the moment it
    started — is made here rather than carried on the Entry, because an Entry
    queued last night is started now. The Predecessor comes from the Action
    rather than from the Entry, since what an Entry stands on is resolved when
    it starts (ADR 0015).
    """
    started = datetime.now(timezone.utc)
    return start_run(
        workflow_path=entry.workflow_path,
        task=entry.task,
        target_repo=entry.target_repo,
        working_branch=entry.working_branch,
        predecessor=predecessor,
        store=RunStore(default_runs_root()),
        sessions=TmuxSessions(),
        run_id=_run_id(started, entry.workflow_path),
        claude_session_id=str(uuid.uuid4()),
        created_at=_timestamp(started),
        start_state=entry.start_state,
        skip_gates=entry.skip_gates,
        subject=entry.subject,
    )


def _queue_rm(arguments: argparse.Namespace) -> int:
    """Removes an Entry and nothing else. Any Run it produced, and the session
    that Run is in, are left exactly as they were: removal is a Queue operation
    rather than a destructive one."""
    if not Queue(default_queue_root()).remove(arguments.entry_id):
        print(
            f"naiad: no entry '{arguments.entry_id}' in the queue at {default_queue_root()}",
            file=sys.stderr,
        )
        return 2

    print(f"removed {arguments.entry_id}")
    return 0


def _run_id(started: datetime, workflow_path: Path) -> str:
    return f"{started.strftime('%Y%m%d-%H%M%S')}-{_slug(workflow_path)}-{os.getpid()}"


def _entry_id(added: datetime, workflow_path: Path) -> str:
    """Sortable, so that sorting by id *is* Queue order and no Entry holds a
    position of its own.

    Told apart by the microsecond as well as by the process id a Run's id
    carries, because two collisions are possible rather than one: two Entries
    in the same second are routinely one process — an agent queueing a night's
    work in a single turn — and two `naiad queue add` calls are two.
    """
    return f"{added.strftime('%Y%m%d-%H%M%S-%f')}-{_slug(workflow_path)}-{os.getpid()}"


def _batch_ids(added: datetime, works: Sequence[Work]) -> list[str]:
    """One id per Entry a file declares, in the order it writes them.

    An id's whole job is to sort, and Queue order has to follow the file
    because that is what the Predecessor rule reads. Every Entry in one file is
    added at one moment by one process, so the clock cannot tell them apart —
    hence a microsecond apiece, which is the smallest thing an id can say and
    exactly what asking the clock again would have said had it advanced.

    The ids are the shape a single Entry's is, carrying no position and no mark
    of the file: the Queue does not know a batch arrived, so nothing it holds
    may be readable as saying so.
    """
    return [
        _entry_id(added + timedelta(microseconds=place), work.workflow_path)
        for place, work in enumerate(works)
    ]


def _slug(workflow_path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", workflow_path.stem.lower()).strip("-") or "run"


def _timestamp(when: datetime) -> str:
    """The moment a Run or an Entry was made, as its record spells it."""
    return when.isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
