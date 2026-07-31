"""The operator-facing entry point.

Builds the real dependencies and hands them to the kickoff. Everything
identifying a Run — its id, its Claude session id, the moment it started — is
made here and passed in, so the code under it stays testable over plain data.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from naiad.adapters.tmux import TmuxError, TmuxSessions
from naiad.cli.kickoff import start_run
from naiad.domain.workflow import WorkflowError
from naiad.runtime.run import RunStore, StorageError, default_runs_root


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

    arguments = parser.parse_args(argv)
    return _start(arguments)


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
        )
    except (WorkflowError, StorageError, TmuxError) as error:
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
