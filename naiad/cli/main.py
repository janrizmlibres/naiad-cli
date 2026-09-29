"""The entry point, for the operator and for the agent.

Builds the real dependencies and hands them to the Queue, to the Supervisor's
loop or to the agent's command. Everything identifying a Run — its id, its
Claude session id, the moment it started — is made here and passed in, so the
code under it stays testable over plain data.

Starting a Run goes through the Queue and nowhere else: `naiad run`
adds an Entry and then adopts or becomes the Supervisor, and nothing here opens
a session except by taking an Entry off the Queue.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from naiad.adapters.answerer import HeadlessAnswerer
from naiad.adapters.executable import naiad_command
from naiad.adapters.lock import SupervisorLock
from naiad.adapters.notify import configured_notifier
from naiad.adapters.tmux import TmuxError, TmuxSessions
from naiad.cli.adopt import NotInTmux, attachment_in, teaching_for
from naiad.cli.announce import AnnounceError, announce_state, announcement_reply
from naiad.cli.answers import render_answers
from naiad.cli.ask import AskError, ask_question
from naiad.cli.batch import BatchError, enqueue_batch, load_batch
from naiad.cli.branch import BranchError, declare_branch
from naiad.cli.doctor import Severity, diagnose, entrance_refusal, render_report
from naiad.cli.enqueue import REFUSALS, Work, enqueue
from naiad.cli.hold import HoldError, declare_hold
from naiad.cli.state import add_state_commands
from naiad.cli.library import (
    LibraryError,
    empty_library_message,
    install_starter,
    library_entries,
    new_workflow,
    remove_workflow,
    rename_workflow,
    resolve_workflow,
    workflows_in,
)
from naiad.cli.kickoff import start_entry
from naiad.cli.protocol import injection_for, standing_in
from naiad.cli.refusals import ADD_COMMAND, ADOPT_COMMAND, RUN_COMMAND, Remedy
from naiad.cli.supervisor import supervise_queue
from naiad.cli.terminal import terminal_width
from naiad.cli.wait import WaitError, declare_wait
from naiad.cli.watch import tick_once, watch
from naiad.domain.entry import Attachment, Entry
from naiad.domain.key_table import file_key_help, file_row, file_value
from naiad.domain.listing import render_states, render_workflow
from naiad.domain.protocol import ANNOUNCE_SUBCOMMAND
from naiad.domain.workflow import Workflow, WorkflowError, load_workflow
from naiad.hooks.install import install_hooks
from naiad.runtime.announcements import Announcements
from naiad.runtime.answers import AnswerLog
from naiad.runtime.log import RunLog
from naiad.runtime.home import (
    StorageError,
    default_library_root,
    default_lock_path,
    default_queue_root,
    default_runs_root,
)
from naiad.runtime.queue import Queue, cancel, prune, status_of
from naiad.runtime.records import Clears, EntryTurns, Turns
from naiad.runtime.resolve import NoRunError, RunResolver, turn_recipient
from naiad.runtime.run import Run, RunStore
from naiad.runtime.submitted import judge
from naiad.runtime.workflow_file import edit_workflow, set_file_key, unset_file_key
from naiad.skills.install import install_adopt_skill

Handler = Callable[[argparse.Namespace], int]

# Everything a command can fail with that the operator or agent should read as
# a message rather than a traceback.
FAILURES = (
    AnnounceError,
    AskError,
    BatchError,
    BranchError,
    HoldError,
    WaitError,
    LibraryError,
    NoRunError,
    NotInTmux,
    StorageError,
    TmuxError,
    # Everything describing a piece of work can be refused for, taken from the
    # enqueue rather than listed again: a refusal added there and forgotten
    # here would reach the operator as a traceback.
    *REFUSALS,
)


# Named where an operator looks when they have forgotten the name: on the
# commands that drive Runs, which are the only ones that ever notify. The
# terminal and the desktop banner need no configuring and are not listed.
NOTIFICATIONS_HELP = """\
notifications:
  Naiad tells you in the terminal and, on macOS, with a desktop banner. To be
  told on your phone as well, set NAIAD_NTFY_URL to a full ntfy topic URL
  (https://ntfy.sh/some-hard-to-guess-name) and subscribe to that topic in the
  ntfy app. Set NAIAD_NTFY_TOKEN too where the topic is access-controlled.
  Unset, nothing is pushed and nothing else changes."""


def _driving_parser(
    subcommands: "argparse._SubParsersAction[argparse.ArgumentParser]", name: str, *, help: str
) -> argparse.ArgumentParser:
    """A command that drives Runs, and so is one an operator reads to find out
    how they will be told about them."""
    return subcommands.add_parser(
        name,
        help=help,
        epilog=NOTIFICATIONS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


# Named on `set` and `unset` because the table is what an author reads to learn
# which keys exist and what each takes.
KEYS_HELP = (
    "keys (name is changed with `naiad workflow rename`, not set):\n"
    + "\n".join(f"  {line}" for line in file_key_help().splitlines())
)


def _workflow_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "workflow", help="path to the Workflow file, or the bare name of one in the library"
    )


def build_parser() -> argparse.ArgumentParser:
    """The whole command tree, each command bound to its handler and none of them
    run, so the tree can be read without a Run or a home directory."""
    parser = argparse.ArgumentParser(prog="naiad")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = _driving_parser(
        subcommands,
        "run",
        help="queue a Workflow against a task, and supervise if nothing else is",
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

    queue_watch = _driving_parser(
        queue_commands, "watch", help="take the Queue in order, and keep following it for more"
    )
    queue_watch.set_defaults(handler=_queue_watch)

    # The argument is required and nothing defaults to the latest Run: with
    # lanes in parallel "latest" is ambiguous, and reading the wrong Run's
    # Answers is worse than a refusal.
    queue_answers = queue_commands.add_parser(
        "answers", help="what became of every Question a Run asked, in the order they were asked"
    )
    queue_answers.add_argument(
        "entry_or_run", help="an Entry or a Run, as `naiad queue list` names them"
    )
    queue_answers.set_defaults(handler=_queue_answers)

    queue_rm = queue_commands.add_parser(
        "rm", help="remove an Entry, cancelling any Run it started and freeing that session"
    )
    queue_rm.add_argument("entry_id", help="which Entry, as `naiad queue list` names it")
    queue_rm.set_defaults(handler=_queue_rm)

    # No arguments and nothing to confirm: a Prune can reach nothing but done
    # work, so a flag narrowing it would guard against nothing, and `naiad
    # queue list` already shows exactly what it will take.
    queue_prune = queue_commands.add_parser(
        "prune", help="remove the done Entries, and the Runs they became, together"
    )
    queue_prune.set_defaults(handler=_queue_prune)

    adopt = subcommands.add_parser(
        "adopt", help="queue a run that adopts the session you are in, from inside it"
    )
    adopt.add_argument(
        "workflow",
        help="path to the Workflow file, or the bare name of one in the library",
    )
    # A flag rather than a positional, and required: an Adoption has no natural
    # Subject to stand in for a Task, and the agent is the one party
    # holding the conversation the operator's intent came out of, so it writes
    # the Task rather than repeating a line the operator never typed.
    adopt.add_argument(
        "--task",
        required=True,
        help="what the work is, distilled from the conversation in this session",
    )
    _describe_where_and_how(adopt)
    adopt.set_defaults(handler=_adopt)

    # Read before adopting, and by nothing else: the operator names a phase in
    # their own words, and only the Workflow says what its States are actually
    # called.
    states = subcommands.add_parser(
        "states", help="list what a Workflow declares, to choose a State to start at"
    )
    states.add_argument(
        "workflow",
        nargs="?",
        help="path to the Workflow file, or the bare name of one in the library; "
        "omit it to list every workflow the library holds",
    )
    states.set_defaults(handler=_states)

    workflow = subcommands.add_parser(
        "workflow", help="author and read the Workflows in the library"
    )
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)

    workflow_list = workflow_commands.add_parser(
        "list", help="list every Workflow the library holds, naming a broken link as broken"
    )
    workflow_list.set_defaults(handler=_workflow_list)

    workflow_new = workflow_commands.add_parser(
        "new",
        help="create a Workflow in the library: one terminal State, done, or a copy of another",
    )
    workflow_new.add_argument("name", help="the new Workflow's name, which is its file's stem")
    workflow_new.add_argument(
        "--from",
        dest="source",
        metavar="WF",
        default=None,
        help="copy this Workflow (a library name or a path) instead, its name rewritten "
        "to the new one",
    )
    workflow_new.set_defaults(handler=_workflow_new)

    workflow_rm = workflow_commands.add_parser(
        "rm",
        help="delete a Workflow file; refused while an Entry or Run addresses it",
    )
    _workflow_argument(workflow_rm)
    workflow_rm.set_defaults(handler=_workflow_rm)

    workflow_rename = workflow_commands.add_parser(
        "rename",
        help="rename a Workflow, its file and its name key together; "
        "refused while an Entry or Run addresses it",
    )
    _workflow_argument(workflow_rename)
    workflow_rename.add_argument("new", help="the new name, which is the file's new stem")
    workflow_rename.set_defaults(handler=_workflow_rename)

    workflow_set = workflow_commands.add_parser(
        "set",
        help="set a file-level key of a Workflow",
        epilog=KEYS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _workflow_argument(workflow_set)
    workflow_set.add_argument("key", help="which key, from the table below")
    workflow_set.add_argument("value", help="what to write, in the shape the table gives")
    workflow_set.set_defaults(handler=_workflow_set)

    workflow_unset = workflow_commands.add_parser(
        "unset",
        help="delete a file-level key of a Workflow, leaving it with no opinion",
        epilog=KEYS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _workflow_argument(workflow_unset)
    workflow_unset.add_argument("key", help="which key, from the table below")
    workflow_unset.set_defaults(handler=_workflow_unset)

    workflow_show = workflow_commands.add_parser(
        "show", help="print a Workflow's file-level keys and each State's kind and marks"
    )
    _workflow_argument(workflow_show)
    workflow_show.set_defaults(handler=_workflow_show)

    workflow_check = workflow_commands.add_parser(
        "check", help="load a Workflow as a Run would, and say what is wrong with it"
    )
    _workflow_argument(workflow_check)
    workflow_check.set_defaults(handler=_workflow_check)

    add_state_commands(subcommands)

    announce = subcommands.add_parser(
        ANNOUNCE_SUBCOMMAND, help="announce the State you are in"
    )
    announce.add_argument("name", help="the State's name, as declared by the Workflow")
    announce.add_argument(
        "--subject",
        default=None,
        help="what this announcement is about, for a State whose Prompt names one",
    )
    announce.set_defaults(handler=_announce)

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

    wait_parser = subcommands.add_parser(
        "wait", help="declare that you are waiting, so silence is not misread"
    )
    wait_parser.add_argument("reason", help="what you are waiting on")
    wait_parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="how long the wait may run before you are reminded (default: ten minutes)",
    )
    wait_parser.set_defaults(handler=_wait)

    hold_parser = subcommands.add_parser(
        "hold", help="relay the human's pause: park the run until they return"
    )
    hold_parser.add_argument("reason", help="why the human asked for the hold, in their words")
    hold_parser.set_defaults(handler=_hold)

    branch_parser = subcommands.add_parser(
        "branch", help="declare the working branch you created for this run"
    )
    branch_parser.add_argument("name", help="the branch's name, exactly as you created it")
    branch_parser.set_defaults(handler=_branch)

    stopped = subcommands.add_parser("stopped", help="record that a turn ended (Stop hook)")
    stopped.set_defaults(handler=_stopped)

    submitted = subcommands.add_parser(
        "submitted", help="confirm a typed Prompt arrived whole (UserPromptSubmit hook)"
    )
    submitted.set_defaults(handler=_submitted)

    protocol = subcommands.add_parser(
        "protocol", help="print the Protocol for a fresh context (SessionStart hook)"
    )
    protocol.set_defaults(handler=_protocol)

    install = subcommands.add_parser(
        "install", help="install Naiad's hooks and skills into your Claude Code configuration"
    )
    install.add_argument(
        "--settings",
        type=Path,
        default=None,
        help="which settings file to install the hooks into "
        "(default: settings.json in $CLAUDE_CONFIG_DIR, else ~/.claude)",
    )
    install.add_argument(
        "--skills",
        type=Path,
        default=None,
        help="which skills directory to install into "
        "(default: skills in $CLAUDE_CONFIG_DIR, else ~/.claude)",
    )
    install.add_argument(
        "--starter",
        action="store_true",
        help="also copy the starter workflow into the library as starter.toml",
    )
    install.add_argument(
        "--force",
        action="store_true",
        help="with --starter, overwrite a starter.toml that differs from the shipped one",
    )
    install.set_defaults(handler=_install)

    doctor = subcommands.add_parser(
        "doctor",
        help="check that this machine can run Naiad, and say how to fix what cannot",
    )
    doctor.set_defaults(handler=_doctor)

    watch_parser = _driving_parser(
        subcommands, "watch", help="drive a Run until it ends or is interrupted"
    )
    watch_parser.add_argument(
        "run_id", nargs="?", default=None, help="which Run (default: this session)"
    )
    watch_parser.set_defaults(handler=_watch)

    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    handler: Handler = arguments.handler
    return handler(arguments)


def _describe_the_work(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    """The options that describe one piece of work, shared by every command
    that creates one — because an Entry is a Run that does not exist yet, and
    two lists that drifted apart would mean queueing could not say something
    starting a Run could.

    The flags read as an operator types them — `--branch`, `--base` — while
    what they set is named as the domain names it. The translation happens
    here, at the boundary, and nowhere else.

    `required` is false where a batch file may describe the work instead, and
    it governs the workflow positional alone: the task is optional everywhere,
    because a given --subject stands in for it. Both absences are
    refused with a message rather than by argparse, as the Working branch
    already is, so that an operator is told every way of saying it rather than
    only the one they left out.
    """
    # Nothing where the work must be described here, and what makes the
    # workflow positional optional where a file may describe it instead.
    optional: dict[str, Any] = {} if required else {"nargs": "?", "default": None}
    parser.add_argument(
        "workflow",
        help="path to the Workflow file, or the bare name of one in the library",
        **optional,
    )
    # Optional everywhere, not only where a file may describe the work: a
    # given --subject stands in for an absent task, so which of the
    # two must be present is refused with a message rather than by argparse.
    parser.add_argument(
        "task",
        help="what the work is (a given --subject stands in when omitted)",
        nargs="?",
        default=None,
    )
    _describe_where_and_how(parser)


def _describe_where_and_how(parser: argparse.ArgumentParser) -> None:
    """Everything qualifying a piece of work rather than naming it: which
    repository, which branch, what it stands on, where it starts, on what, and
    whether Gates are resolved past.

    Apart from the two positionals because `naiad adopt` names its work
    differently — its task is a flag, an Adoption having no Subject to stand in
    for one — while these six mean there exactly what they mean at
    the other entrances, and two copies would drift apart.
    """
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="the target repository (default: the working directory)",
    )
    # Optional: given, it is carried verbatim and never second-guessed; absent,
    # the agent at the head of the Run derives a name from the target
    # repository's conventions and declares it. Naiad itself still
    # invents no branch name.
    parser.add_argument(
        "--branch",
        default=None,
        help="the working branch this work's commits belong on "
        "(default: the agent derives one in the repository)",
    )
    # Left under the flag's own name rather than the domain's, because the two
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
        reply = announcement_reply(announcement, run=run)
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(reply, end="")
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


def _wait(arguments: argparse.Namespace) -> int:
    try:
        run = _current_run()
        granted, remaining = declare_wait(
            arguments.reason, run=run, now=time.time(), seconds=arguments.seconds
        )
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    # The granted number is said back because a claim past the remaining
    # budget is clamped rather than refused: the agent must plan around what
    # it actually got, not what it asked for.
    print(
        f'waiting on "{arguments.reason}" for {int(granted)}s '
        f"({int(remaining)}s of wait budget left); end your turn"
    )
    return 0


def _hold(arguments: argparse.Namespace) -> int:
    try:
        run = _current_run()
        declare_hold(arguments.reason, run=run)
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    # No granted number to say back: a Hold has no clock. What the agent must
    # know is that nothing further will arrive until the human acts.
    print(
        f'held: "{arguments.reason}"; the run is parked and nothing will be '
        "sent until the human returns — end your turn"
    )
    return 0


def _branch(arguments: argparse.Namespace) -> int:
    try:
        run = _current_run()
        declare_branch(
            arguments.name,
            run=run,
            queue=Queue(default_queue_root()),
            runs=RunStore(default_runs_root()),
        )
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"declared working branch '{arguments.name}'; this run's work belongs on it")
    return 0


def _stopped(arguments: argparse.Namespace) -> int:
    """The Stop hook. Hooks are installed independently of any Run, so finding
    no Run attached is ordinary and must not be reported as a failure.

    A Turn ending through an Adoption's gap — the Entry queued, its Run not
    created yet — lands beside the Entry instead of nowhere, so the opening
    delivery it gates is not waited on for a signal that already came and went.
    Who it belongs to is the resolution seam's one answer, not two checks
    composed here.

    Guarded rather than left to raise, unlike every command: a queue file the
    operator damaged is a command's refusal to report, and this hook fires on
    every turn end in every session on the machine."""
    resolver = RunResolver(RunStore(default_runs_root()), os.environ)
    pane = os.environ.get("TMUX_PANE")
    try:
        recipient = turn_recipient(resolver, Queue(default_queue_root()).all(), tmux_pane=pane)
        if recipient is None:
            return 0
        if isinstance(recipient, Entry):
            sidecar = EntryTurns(default_queue_root(), recipient.id)
            sidecar.record_end()
            # The attach may have run between the resolution above and this
            # write, and its relocation found no sidecar to move. Resolving
            # again closes the interleaving: a Run answering for the pane now
            # existed before that relocation, so whichever side acted last
            # performs the same move.
            raced = resolver.resolve(tmux_pane=pane)
            if raced is not None:
                sidecar.relocate_into(raced.root)
            return 0

        latest = Announcements(recipient.root).latest()
        Turns(recipient.root).record_end(latest_seq=latest.seq if latest else None)
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
    return 0


def _protocol(arguments: argparse.Namespace) -> int:
    """The SessionStart hook, run on startup, on Clear and on compaction — the
    three moments a context is created or destroyed. Like the Stop hook it is
    installed independently of any Run, so a session nobody is driving prints
    nothing and succeeds rather than failing.

    A fresh context a Clear made is the one the loop is waiting on: it records
    that the /clear landed, so delivery of the next Prompt can be gated on the
    Clear being confirmed rather than hoped for. The three sources
    are told apart by the hook's own `source`, a documented field,
    so only a Clear counts — a startup or a compaction is not this State's
    Clear.

    A fresh context a Compaction made is the Session's own doing, and Naiad
    only learns of it here: it is written to the Run log as the diagnostic,
    and the injection gains the reminder of where the agent stands, since the
    summary may have lost it."""
    run = _attached_run()
    if run is None:
        return 0

    source = _hook_source()
    if source == "clear":
        Clears(run.root).record_landing()
    compacted = source == "compact"
    if compacted:
        RunLog(run.root).record_compaction(state=standing_in(run))

    print(injection_for(run, compacted=compacted))
    return 0


def _submitted(arguments: argparse.Namespace) -> int:
    """The UserPromptSubmit hook, run on every prompt submitted in any session
    on the machine. A prompt is judged against the Prompt the loop typed last,
    and one the Session took cut short is turned away — exit 2 blocks it and
    erases it — so the loop can type it whole again.

    Everything else passes untouched and prints nothing, since what a
    UserPromptSubmit hook prints is added to the agent's context: a session
    nobody is driving, a human's prompt between deliveries, and a hook run with
    no prompt to read.

    Guarded rather than left to raise, as the Stop hook is: a hook that fails
    must let the human's prompt through rather than lock them out of their own
    session."""
    try:
        run = _attached_run()
        prompt = _hook_prompt()
        if run is None or prompt is None:
            return 0
        verdict = judge(run.root, prompt, now=time.time())
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 0

    if verdict == "rejected":
        print(
            "naiad: this prompt arrived with part of it missing and was turned away; "
            "naiad will type it again in full",
            file=sys.stderr,
        )
        return 2
    return 0


def _hook_prompt() -> str | None:
    """The `prompt` this UserPromptSubmit hook was fired with, read from the
    hook's stdin JSON; None when there is none to read, which passes the
    prompt through rather than judging nothing."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        return None
    prompt = payload.get("prompt")
    return prompt if isinstance(prompt, str) else None


def _hook_source() -> str | None:
    """The `source` this SessionStart hook was fired with — 'startup', 'clear',
    'compact' or 'resume' — read from the hook's stdin JSON.

    None when there is no readable source: the command run outside a hook, or
    stdin that is empty or not JSON. None reads as no particular source and
    records nothing, which is the safe default — a Clear is only ever acted on
    when the hook says so in as many words."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        return None
    source = payload.get("source")
    return source if isinstance(source, str) else None


def _install(arguments: argparse.Namespace) -> int:
    """What one machine needs set up: the three hooks, the skill that turns the
    operator's stated intent into `naiad adopt`, and, on request, the
    starter Workflow in the library.

    Installed once for the machine rather than per Run: the hooks do nothing
    when no Run is attached to the session that fired them, and the skill is
    reached for only when the operator asks for an Adoption.

    One command rather than one per surface, because a machine with the hooks
    and not the skill is a machine where the intent phrase reaches nothing —
    and each is reported as it lands, so that a refusal on the third is read
    against what the first two already did.

    The library is touched only when asked: install is re-run without thinking
    and from scripts, and what it holds is the operator's. It takes no path of
    its own and moves with `NAIAD_HOME` as everything under the home does,
    where the hooks and the skill live in a configuration that is Claude Code's
    and needs naming.

    Ends with the doctor's report, whatever install did, so that what it just
    set up is read against what the machine still lacks. The report never
    changes install's exit code: that is install's own outcome.
    """
    if arguments.force and not arguments.starter:
        print("naiad: --force applies to --starter, and --starter was not given", file=sys.stderr)
        return 2

    try:
        settings = install_hooks(settings_path=arguments.settings)
        print(f"installed naiad's hooks into {settings}")
        skill = install_adopt_skill(skills_root=arguments.skills)
        print(f"installed the adopt skill into {skill}")
        if arguments.starter:
            starter = install_starter(library=default_library_root(), force=arguments.force)
            print(f"installed the starter workflow into {starter}")
    except (OSError, ValueError) as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2
    finally:
        # After what install did or refused to do, and never changing its exit
        # code: install is the command that fixes what the report finds, so the
        # report is the check that it did.
        print(render_report(diagnose()))

    return 0


def _doctor(arguments: argparse.Namespace) -> int:
    """Say what this machine lacks and how to fix it, and repair nothing: what
    to run is the operator's to run. Exits 1 only when a check fails, so that a
    warning never stops a script that gates on it."""
    findings = diagnose()
    print(render_report(findings))
    return 1 if any(finding.severity is Severity.FAIL for finding in findings) else 0


def _refused_at_the_door() -> bool:
    """Whether an entrance must stop, having said why. Every command that
    starts or drives Runs asks this first, and nothing else does: the commands
    an agent types inside a session, and the hooks Claude Code fires, run where
    a refusal would only add noise to work already under way."""
    refusal = entrance_refusal()
    if refusal is None:
        return False
    print(refusal, file=sys.stderr)
    return True


def _watch(arguments: argparse.Namespace) -> int:
    """Drive one named Run — and not while a Supervisor is driving the Queue.

    A held lock means the Supervisor may be ticking this very Run in one of
    its lanes, and a second ticker on one Run delivers everything twice.
    """
    if _refused_at_the_door():
        return 2

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
    Answerer — the loop `naiad watch` blocks in. The Supervisor ticks its
    Lanes through `_ticker` instead, and both go through the same tick with
    the same dependencies.
    """
    # The line the operator needs to look in on the work, printed where the Run
    # is driven rather than where it was queued: an Entry queued tonight is
    # started hours later, and the session it names does not exist until then.
    print(f"watching {run.id}   (tmux attach -t {run.tmux_session})")
    watch(
        run=run,
        workflow=load_workflow(run.workflow_path),
        session=TmuxSessions(),
        notifier=configured_notifier(),
        answerer=HeadlessAnswerer(),
        # The naiad driving this Run, so a nudged agent is told to type the
        # command that exists rather than whatever the session's PATH holds.
        naiad=naiad_command(),
        entry_id=_entry_id_of(run),
    )


def _entry_id_of(run: Run) -> str | None:
    """The Entry a Run became, so that a notification can point the operator at
    `naiad queue answers` by the id `naiad queue list` shows. The Run records no
    Entry; the Queue is asked, and a Run it does not know is pointed at by its
    own id."""
    entry = Queue(default_queue_root()).entry_of(run.id)
    return None if entry is None else entry.id


def _ticker() -> Callable[[Run], None]:
    """One tick of one lane's Run, for the Supervisor's pass.

    Runs in different lanes report into one terminal, so every narration line
    is prefixed with the Run it belongs to — interleaved lines are noise
    rather than ambiguity only while each names its Run. The attach line is
    printed the first time a Run is ticked, which is where `naiad watch`
    prints it too: where the Run is driven rather than where it was queued.
    """
    session = TmuxSessions()
    notifier = configured_notifier()
    answerer = HeadlessAnswerer()
    naiad = naiad_command()
    watching: set[str] = set()

    def tick_run(run: Run) -> None:
        if run.id not in watching:
            watching.add(run.id)
            print(f"watching {run.id}   (tmux attach -t {run.tmux_session})")
        tick_once(
            run=run,
            workflow=load_workflow(run.workflow_path),
            session=session,
            notifier=notifier,
            answerer=answerer,
            naiad=naiad,
            entry_id=_entry_id_of(run),
            report=lambda message: print(f"{run.id}  {message}"),
            lead=len(f"{run.id}  "),
        )

    return tick_run


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
    """The one entrance to starting Runs: add one Entry, then adopt
    or become.

    It spawns no session of its own. A second entrance would bypass the guard
    that matters most — nothing would stop an immediate Run putting a second
    agent into the working tree a Supervisor is already driving a Run in — and
    an invariant with two places to break it is a convention.

    So the Entry is appended rather than jumped ahead: the command stopped
    meaning 'start this now' the moment a Queue existed, and where the Entry
    lands is the honest place for that to show.
    """
    if _refused_at_the_door():
        return 2

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

    if arguments.workflow is None:
        # Refused with a message, because argparse no longer says: the
        # positional had to become optional for a file to describe the work
        # instead. A missing task is not refused here — a given Subject stands
        # in for it, and which of the two must be present is the enqueue's one
        # check to make.
        print(
            "naiad: no workflow was given, and no batch file either; "
            "try: naiad queue add <workflow> <task>, "
            "or naiad queue add --file <batch.toml>",
            file=sys.stderr,
        )
        return 2

    return 0 if _queued(arguments, remedy=ADD_COMMAND) is not None else 2


def _adopt(arguments: argparse.Namespace) -> int:
    """Adopt this session: queue an Entry marked to attach to it, teach the
    agent the Protocol, and return.

    It starts nothing, for the reason `naiad queue add` does not — a tool call
    that became a process blocking for hours is the failure the Queue exists to
    avoid — and because the Supervisor is the one entrance to starting Runs.
    What it prints is the whole of what the hitherto-undriven agent knows: the
    Protocol, what to do with the rest of this turn, and, when nothing is
    supervising, the warning to relay.
    """
    if _refused_at_the_door():
        return 2

    try:
        # Before anything is queued, because a session with no pane is one the
        # Supervisor could never attach to: an Entry marked to attach to
        # nowhere would only defer the refusal to a moment nobody is at.
        attachment = attachment_in(os.environ)
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    entry = _queued(arguments, remedy=ADOPT_COMMAND, attachment=attachment)
    if entry is None:
        return 2

    print()
    print(
        teaching_for(
            entry,
            # Asked rather than acted on: a Supervisor started as a side effect
            # of a tool call would have no terminal, no owner and no end, so
            # what is left is telling the agent to tell the human.
            supervised=SupervisorLock(default_lock_path()).held(),
            # The naiad the agent must type, for the reason the Protocol names
            # one: this session's PATH is whatever the human's shell held.
            naiad=naiad_command(),
        ),
        end="",
    )
    return 0


def _states(arguments: argparse.Namespace) -> int:
    """What a Workflow declares, for an agent turning the operator's words
    into a State to start at.

    Named or not, because an operator who says "naiad, spec this out" has
    named no Workflow: one call then answers both which Workflows exist and
    what each declares, so the agent chooses with the candidates in front of
    it rather than from memory.
    """
    library = default_library_root()
    if arguments.workflow is None:
        return _every_workflow(library)

    return _print_workflow(arguments.workflow, render_states, library=library)


def _print_workflow(
    argument: str, render: Callable[[Workflow], str], *, library: Path | None = None
) -> int:
    """A Workflow named by name or path, loaded the way a Run loads it and laid
    out by `render`, or refused in one line.

    A name asked for by name is refused rather than answered with something
    else: the reader named one thing, and printing another would answer a
    question nobody asked.
    """
    try:
        workflow = load_workflow(
            resolve_workflow(argument, library=library or default_library_root())
        )
    except (*FAILURES, WorkflowError) as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(render(workflow))
    return 0


def _workflow_show(arguments: argparse.Namespace) -> int:
    return _print_workflow(arguments.workflow, render_workflow)


def _workflow_check(arguments: argparse.Namespace) -> int:
    """Whether a Run could start from this file, decided by loading it exactly
    as a Run does: through the library's resolution, then the one loader."""
    return _print_workflow(arguments.workflow, lambda workflow: f"{workflow.name}: OK")


def _workflow_new(arguments: argparse.Namespace) -> int:
    try:
        path, workflow = new_workflow(
            arguments.name, library=default_library_root(), source=arguments.source
        )
    except (*FAILURES, WorkflowError) as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"created {workflow.name}: {path}")
    return 0


def _workflow_list(arguments: argparse.Namespace) -> int:
    """Every entry the library holds, one line each, the ones a Run could not
    start from saying why beside their name."""
    library = default_library_root()
    held = library_entries(library)
    if not held:
        print(empty_library_message(library))
        return 0

    width = max(len(name) for name, _ in held)
    for name, problem in held:
        print(f"{name:<{width}}  {problem}" if problem else name)
    return 0


def _workflow_set(arguments: argparse.Namespace) -> int:
    try:
        value = file_value(arguments.key, arguments.value)
        path = resolve_workflow(arguments.workflow, library=default_library_root())
        edit_workflow(path, lambda document: set_file_key(document, arguments.key, value))
    except (*FAILURES, WorkflowError) as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"{path.stem}: {arguments.key} = {value}")
    return 0


def _workflow_unset(arguments: argparse.Namespace) -> int:
    removed: list[bool] = []
    try:
        file_row(arguments.key)
        path = resolve_workflow(arguments.workflow, library=default_library_root())
        edit_workflow(
            path, lambda document: removed.append(unset_file_key(document, arguments.key))
        )
    except (*FAILURES, WorkflowError) as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    if removed == [True]:
        print(f"{path.stem}: {arguments.key} removed")
    else:
        print(f"{path.stem}: {arguments.key} was not set")
    return 0


def _workflow_rm(arguments: argparse.Namespace) -> int:
    try:
        path = remove_workflow(
            arguments.workflow,
            library=default_library_root(),
            queue=Queue(default_queue_root()),
            runs=RunStore(default_runs_root()),
        )
    except (*FAILURES, WorkflowError) as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"removed {path}")
    return 0


def _workflow_rename(arguments: argparse.Namespace) -> int:
    try:
        path = rename_workflow(
            arguments.workflow,
            arguments.new,
            library=default_library_root(),
            queue=Queue(default_queue_root()),
            runs=RunStore(default_runs_root()),
        )
    except (*FAILURES, WorkflowError) as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    print(f"renamed {arguments.workflow} to {arguments.new}: {path}")
    return 0


def _every_workflow(library: Path) -> int:
    """Every Workflow the library holds, as one listing.

    A file that cannot be read names itself and its problem in place, rather
    than taking the listing down with it: an agent left with nothing would go
    back to guessing at the Workflows that are perfectly fine.
    """
    held = workflows_in(library)
    if not held:
        print(empty_library_message(library))
        return 0

    blocks = []
    for path in held:
        try:
            blocks.append(render_states(load_workflow(path)))
        except WorkflowError as error:
            blocks.append(f"{path.stem}\n  {error}")
    print("\n\n".join(blocks))
    return 0


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
        works = load_batch(path, repo=Path.cwd(), library=default_library_root())
        entries = enqueue_batch(
            works,
            queue=Queue(default_queue_root()),
            runs=RunStore(default_runs_root()),
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


def _queued(
    arguments: argparse.Namespace,
    *,
    remedy: Remedy,
    # The Session this work's Run attaches to instead of one being opened for
    # it, for an Adoption alone. Threaded through the one enqueue
    # rather than given a path of its own, so that an Adoption cannot queue
    # something the other entrances would have refused.
    attachment: Attachment | None = None,
) -> Entry | None:
    """One Entry from what was typed, or nothing when it was refused.

    Shared by both entrances so that neither can queue something the other
    would have refused, and so that an Entry means the same thing whichever
    command made it. `remedy` is the vocabulary the operator described the work
    in, quoted back by every refusal so that what they read is something they
    can act on.
    """
    target_repo = (arguments.repo or Path.cwd()).expanduser().resolve()
    added = datetime.now(timezone.utc)

    try:
        # A bare name resolves through the Workflow library here, at the
        # entrance, and the Entry stores the path it resolved to.
        workflow_path = resolve_workflow(arguments.workflow, library=default_library_root())
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
                attachment=attachment,
            ),
            queue=Queue(default_queue_root()),
            runs=RunStore(default_runs_root()),
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
    print(f"  branch {_branch_shown(entry)}   in {entry.target_repo}")


def _queue_list(arguments: argparse.Namespace) -> int:
    """The Entries in id order, which is Queue order, each with what became of
    it — asked of its Run rather than read from a status the Queue keeps."""
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
    standing = [_standing_shown(entry, runs) for entry in entries]
    # Padded to the longest here rather than to a fixed width, because a State
    # is named by the Workflow and Naiad knows no name in advance.
    width = max(len(name) for name in standing)
    for entry, state in zip(entries, standing):
        print(_queue_line(entry, runs, state=f"{state:<{width}}"))
    return 0


def _standing_shown(entry: Entry, runs: RunStore) -> str:
    """The State the Entry's Run stands in, as the Run recorded it — never
    re-derived from a Workflow that may have been edited since. A dash where
    there is none: a waiting Entry has no Run, and a Run written before kickoff
    recorded its start has nothing to show until it announces."""
    run = runs.load(entry.run_id) if entry.run_id is not None else None
    return (standing_in(run) if run is not None else None) or "-"


def _queue_line(entry: Entry, runs: RunStore, *, state: str) -> str:
    """One Entry as one line: which, what became of it, the State it stands in,
    where, on what branch, and what the work is.

    The repository in full rather than by its directory's name, because one
    Queue spans every repository and two checkouts of the same project — a
    worktree, a second clone — share that name and would otherwise read as one.
    """
    became = status_of(entry, runs)
    line = (
        f"{entry.id}  {became:<7}  {state}  {_shortened(entry.target_repo)}  "
        f"{_branch_shown(entry)}  {entry.task}"
    )
    return line if entry.run_id is None else f"{line}  ({entry.run_id})"


def _branch_shown(entry: Entry) -> str:
    """A branchless Entry has no name yet — the agent derives one inside the
    Run — and `None` on an operator's screen would read as a branch called
    None rather than as the absence of one."""
    return entry.working_branch or "-"


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
    two of them each take a lane's first waiting Entry and put two agents in
    one working tree — which is the single thing one Run per working tree
    exists to prevent.
    """
    if _refused_at_the_door():
        return 2

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

    It holds no rules of its own. Which Entry is next in each lane, whether it
    is started or resumed, and what its work stands on are
    naiad.domain.supervise's to say; this builds the real dependencies and
    hands them over.
    """
    try:
        supervise_queue(
            queue=Queue(default_queue_root()),
            runs=RunStore(default_runs_root()),
            start=_start_entry,
            tick=_ticker(),
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
    """Hand one Entry the dependencies turning it into a Run.

    Everything identifying the Run — its id, its Claude session, the moment it
    started — is made here rather than carried on the Entry, because an Entry
    queued last night is started now. Which way that Run meets its session is
    not decided here: an Entry marked to attach joins one and every other opens
    one, and that choice lives with the two functions it chooses between.
    """
    started = datetime.now(timezone.utc)
    return start_entry(
        entry,
        predecessor=predecessor,
        store=RunStore(default_runs_root()),
        sessions=TmuxSessions(),
        queue_root=default_queue_root(),
        run_id=_run_id(started, entry.workflow_path),
        claude_session_id=str(uuid.uuid4()),
        created_at=_timestamp(started),
    )


def _queue_answers(arguments: argparse.Namespace) -> int:
    """Print a Run's Answer log, for the Entry or the Run the operator named.

    An Entry id and a Run id are both what `naiad queue list` prints, so either
    is taken. An Entry not yet started has no Run to read and says so, rather
    than printing the empty block of a Run that was asked nothing.
    """
    named = arguments.entry_or_run
    runs = RunStore(default_runs_root())
    try:
        entry = Queue(default_queue_root()).find(named)
        run_id = named if entry is None else entry.run_id
        if entry is not None and run_id is None:
            print(f"{entry.id} has not started, so it has no answers yet")
            return 0
        run = runs.load(run_id) if run_id is not None else None
    except FAILURES as error:
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    if run is None:
        print(
            f"naiad: no entry '{named}' in the queue at {default_queue_root()}, "
            f"and no run under {default_runs_root()}",
            file=sys.stderr,
        )
        return 2

    print(
        render_answers(run.id, AnswerLog(run.root).entries(), width=terminal_width()),
        end="",
    )
    return 0


def _queue_rm(arguments: argparse.Namespace) -> int:
    """Removes an Entry and cancels the Run it became.

    Which Runs are ended and in what order is naiad.runtime.queue's to say;
    this reports what came back. The Session is named because nothing is typed
    into it: the agent there learns at its next Protocol verb, from the
    refusal, and the operator is the one who can go and read what it was doing.
    """
    try:
        cancelled = cancel(
            Queue(default_queue_root()), RunStore(default_runs_root()), arguments.entry_id
        )
    except FAILURES as error:
        # The ending goes first, so a Run that would not take it leaves the
        # Entry in the Queue rather than orphaning a Run that still drives its
        # session.
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    if cancelled is None:
        print(
            f"naiad: no entry '{arguments.entry_id}' in the queue at {default_queue_root()}",
            file=sys.stderr,
        )
        return 2

    print(f"removed {arguments.entry_id}")
    # Only a Run this act actually ended. An Entry that never started one, and
    # one whose Run was already over, release no Session — and a line offering
    # the operator a session in either case would be a claim, not a report.
    if cancelled.run is not None:
        print(_cancellation_line(cancelled.run))
    return 0


def _cancellation_line(run: Run) -> str:
    """What was cancelled, and where to go and read what the agent was doing.

    A Run cancelled between its directory being made and its session being
    recorded has no pane. Offering its session anyway would send the operator
    looking for one that was never opened.
    """
    if run.tmux_pane is None:
        return f"cancelled run {run.id}; it had no session yet"
    return f"cancelled run {run.id}; its session at pane {run.tmux_pane} is yours"


def _queue_prune(arguments: argparse.Namespace) -> int:
    """Take the done Entries out, each with the Run it became, and
    the finished Orphaned Runs after them.

    Which Entries and orphans qualify is naiad.runtime.queue's to say; this
    reports what came back. A Run that would not go is a failure with a
    message, although the Queue was still tidied: the orphan left behind is one
    the operator can act on only if they are told its path — and the next Prune
    will meet it again.
    """
    try:
        pruned = prune(Queue(default_queue_root()), RunStore(default_runs_root()))
    except FAILURES as error:
        # A damaged Entry, met before anything was deleted.
        print(f"naiad: {error}", file=sys.stderr)
        return 2

    if not (pruned.removed or pruned.orphans or pruned.skipped or pruned.failures):
        print(
            "nothing to prune: no entry in the queue is done and no run is orphaned"
            f" ({default_queue_root()})"
        )
        return 0

    for entry in pruned.removed:
        print(f"pruned {entry.id}  {entry.task}")
    # An orphan has no line in the listing, so this printed line is the only
    # record its removal ever gets.
    for run_id in pruned.orphans:
        print(f"pruned orphaned run {run_id}")
    if pruned.removed or pruned.orphans:
        print(f"{len(pruned.removed) + len(pruned.orphans)} pruned")

    # Left rather than failed: whether a running orphan is truly live is the
    # operator's fact, so naming it defers the judgment without alarming them.
    for path in pruned.skipped:
        print(f"left orphaned run {path}: reads as running, yours to judge")

    for failure in pruned.failures:
        print(f"naiad: {failure}", file=sys.stderr)
    return 2 if pruned.failures else 0


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
