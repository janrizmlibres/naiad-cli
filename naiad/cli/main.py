"""The entry point, for the operator and for the agent.

Builds the real dependencies and hands them to the kickoff or to the agent's
command. Everything identifying a Run — its id, its Claude session id, the
moment it started — is made here and passed in, so the code under it stays
testable over plain data.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from naiad.adapters.executable import naiad_command
from naiad.adapters.notify import DesktopNotifications
from naiad.adapters.tmux import TmuxError, TmuxSessions
from naiad.cli.announce import AnnounceError, announce_state
from naiad.cli.kickoff import start_run
from naiad.cli.protocol import injection_for
from naiad.domain.decide import Deliver, Nudge
from naiad.domain.transitions import UnknownState
from naiad.domain.workflow import WorkflowError, load_workflow
from naiad.hooks.install import DEFAULT_SETTINGS_PATH, install_hooks
from naiad.runtime.announcements import Announcements
from naiad.runtime.loop import tick
from naiad.runtime.records import Turns
from naiad.runtime.resolve import NoRunError, RunResolver
from naiad.runtime.run import Run, RunStore, StorageError, default_runs_root

Handler = Callable[[argparse.Namespace], int]

# Everything a command can fail with that the operator or agent should read as
# a message rather than a traceback.
FAILURES = (AnnounceError, NoRunError, StorageError, TmuxError, UnknownState, WorkflowError)

# Fast enough that a finished turn is picked up promptly, slow enough that a
# Run waiting on a human is not spinning.
TICK_SECONDS = 2.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="naiad")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="start a Run of a Workflow against a task")
    run.add_argument("workflow", type=Path, help="path to the Workflow file")
    run.add_argument("task", help="what the Run is to do")
    run.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="the target repository (default: the working directory)",
    )
    run.add_argument(
        "--at",
        dest="start_state",
        default=None,
        help="start at this State rather than the first (default: the first)",
    )
    run.add_argument(
        "--skip-gates",
        action="store_true",
        help="resolve past Gate States, for an unattended run of a supervised Workflow",
    )
    run.set_defaults(handler=_start)

    state = subcommands.add_parser("state", help="announce the State you are in")
    state.add_argument("name", help="the State's name, as declared by the Workflow")
    state.set_defaults(handler=_announce)

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

    watch = subcommands.add_parser("watch", help="drive a Run's session until interrupted")
    watch.add_argument("run_id", nargs="?", default=None, help="which Run (default: this session)")
    watch.set_defaults(handler=_watch)

    arguments = parser.parse_args(argv)
    handler: Handler = arguments.handler
    return handler(arguments)


def _announce(arguments: argparse.Namespace) -> int:
    try:
        run = _current_run()
        announcement = announce_state(arguments.name, run=run)
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"announced {announcement.state} ({announcement.seq})")
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
    try:
        run = _named_run(arguments.run_id) if arguments.run_id else _current_run()
        workflow = load_workflow(run.workflow_path)
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    session = TmuxSessions()
    notifier = DesktopNotifications()
    # The naiad driving this Run, so a nudged agent is told to type the command
    # that exists rather than whatever the session's PATH happens to hold.
    naiad = naiad_command()

    print(f"watching {run.id} ({run.tmux_session})")
    try:
        while True:
            action = tick(
                run=run,
                workflow=workflow,
                session=session,
                notifier=notifier,
                naiad=naiad,
            )
            if isinstance(action, Deliver):
                print(f"delivered {action.state}")
            elif isinstance(action, Nudge):
                print(f"nudged the agent ({action.attempt})")
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        return 0


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


def _start(arguments: argparse.Namespace) -> int:
    workflow_path = arguments.workflow.expanduser().resolve()
    target_repo = (arguments.repo or Path.cwd()).expanduser().resolve()
    started = datetime.now(timezone.utc)

    try:
        run = start_run(
            workflow_path=workflow_path,
            task=arguments.task,
            target_repo=target_repo,
            store=RunStore(default_runs_root()),
            sessions=TmuxSessions(),
            run_id=_run_id(started, workflow_path),
            claude_session_id=str(uuid.uuid4()),
            created_at=started.isoformat().replace("+00:00", "Z"),
            start_state=arguments.start_state,
            skip_gates=arguments.skip_gates,
        )
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"run {run.id}")
    print(f"  session  {run.tmux_session}   (tmux attach -t {run.tmux_session})")
    print(f"  metadata {run.metadata_path}")
    return 0


def _run_id(started: datetime, workflow_path: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", workflow_path.stem.lower()).strip("-") or "run"
    return f"{started.strftime('%Y%m%d-%H%M%S')}-{slug}-{os.getpid()}"


if __name__ == "__main__":
    raise SystemExit(main())
